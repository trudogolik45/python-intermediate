# Alembic на asyncpg: один DATABASE_URL вместо двух

## Context

Skill `/run-python-intermediate` документирует граблю, а `CLAUDE.md` повторяет её в Gotchas: Alembic с хоста требует **обе** переменные окружения, и при пустой любой из них падает `ArgumentError: Could not parse SQLAlchemy URL`, не сообщая, какая именно пуста.

У грабли две причины, и снимать нужно обе:

1. Миграции ходят через psycopg2, приложение — через asyncpg, поэтому URL два: `SYNC_DATABASE_URL` и `ASYNC_DATABASE_URL`.
2. `migrations/env.py:7` тянет `Base` из `infrastructure/database.py`, а тот на импорте создаёт движок приложения (`database.py:6`) — из-за чего синхронному инструменту нужен ещё и async-URL, хотя он им не пользуется.

Переводим Alembic на asyncpg и разрываем связку `Base` ↔ `engine`. На выходе: один `DATABASE_URL`, `sync_database_url` уходит из `Settings`, `psycopg2-binary` — из зависимостей, грабля исчезает вместе с причиной, а не с формулировкой.

Решения, согласованные с пользователем:
- `env.py` — по каноническому шаблону Alembic (`async_engine_from_config` + `connection.run_sync`), со своим одноразовым движком на `NullPool`;
- `Base` выносится из `database.py` в отдельный модуль, чтобы импорт метаданных не тянул за собой движок.

Вне объёма: `test_database_url` остаётся отдельным полем — он не дублирует подключение, а страхует от `drop_all` по рабочей БД в `tests/conftest.py:17`.

## Реализация

### 1. `src/infrastructure/base.py` (новый файл)

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

Единственное назначение модуля — держать метаданные без единой строчки про подключение. Всё, что импортирует `Base`, больше не создаёт движок побочно.

### 2. `src/infrastructure/database.py`

Убрать объявление `Base` и импорт `DeclarativeBase`. Остаются `engine`, `SessionLocal`, `get_session`; движок читает `settings.database_url` (переименованное поле, см. п. 5).

### 3. Точки импорта `Base` → `infrastructure.base`

Их всего две (плюс `env.py`, который переписывается целиком в п. 4):

- `src/user/models.py:6`
- `tests/conftest.py:6` — оттуда же продолжает импортироваться `get_session`, но уже отдельной строкой из `infrastructure.database`

### 4. `migrations/env.py` — канонический async-шаблон

`infrastructure.database` здесь больше не импортируется вообще: нужны только метаданные и URL.

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from infrastructure.base import Base
from infrastructure.config import settings
from user import models  # noqa: F401 — импорт регистрирует User в Base.metadata

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
```

Ревизия `migrations/versions/001_create_users.py` не меняется — она на SQLAlchemy Core и от драйвера не зависит.

### 5. `src/infrastructure/config.py` — одно поле подключения

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    database_url: str = ""
    test_database_url: str = ""
```

`async_database_url` → `database_url`, `sync_database_url` удаляется.

### 6. Зависимости

```
uv remove psycopg2-binary
```

После этого `grep -rn psycopg2` по репозиторию (кроме `uv.lock`) должен быть пуст.

### 7. Переменные окружения

- `docker-compose.yml` — вместо двух строк одна: `DATABASE_URL: postgresql+asyncpg://postgres:password@db:5432/mydatabase`.
- `docker-compose.test.yml` — остаются `DATABASE_URL` и `TEST_DATABASE_URL` (обе на `test_db`), `SYNC_DATABASE_URL` уходит.
- **`.env` в корне правит пользователь** — доступа к файлу у меня нет. Нужно: `SYNC_DATABASE_URL` удалить, `ASYNC_DATABASE_URL` переименовать в `DATABASE_URL`, `TEST_DATABASE_URL` оставить.

### 8. Skill `/run-python-intermediate`

- `.claude/skills/run-python-intermediate/driver.py` — в `HOST_DB_ENV` остаётся одна строка `DATABASE_URL`. `SYNC_DATABASE_URL` и `TEST_DATABASE_URL` оттуда уходят: словарь используется только в `migrate()`, тестовая БД к миграциям отношения не имеет.
- `SKILL.md`: абзац про «драйвер передаёт обе переменные» (строка 22) и пример прямого вызова (строка 63) — на один `DATABASE_URL`; пункт Гроблей про две переменные удалить целиком; строку Troubleshooting про `ArgumentError` переписать на «в `.env` нет `DATABASE_URL`».

### 9. `CLAUDE.md`

- Stack: убрать «psycopg2 остаётся под Alembic».
- Слой 4: один `DATABASE_URL` на всех, `Base` живёт в `infrastructure/base.py` отдельно от движка, Alembic поднимает свой движок на asyncpg.
- Gotchas: удалить пункт про две переменные Alembic.

## Проверка

1. `uv sync` — psycopg2 ушёл из окружения.
2. Обновить `.env` (п. 7).
3. `uv run python .claude/skills/run-python-intermediate/driver.py reset` — стек с нуля, чистая БД, миграция накатывается уже по asyncpg.
4. `uv run alembic downgrade base && uv run alembic upgrade head` — обе стороны миграции на новом драйвере.
5. `uv run alembic revision --autogenerate --rev-id 002 -m probe` — должен получиться пустой upgrade (метаданные видны, расхождений нет). Файл ревизии после проверки удалить.
6. `uv run python .claude/skills/run-python-intermediate/driver.py smoke` — ожидается `пройдено 21, провалено 0`.
7. `make test` — `1 passed`.
8. `uv run ruff format .`, `uv run ruff check .`, `uvx pyright`.
9. `grep -rn "psycopg2\|sync_database_url\|SYNC_DATABASE_URL\|async_database_url\|ASYNC_DATABASE_URL" --include="*.py" --include="*.yml" --include="*.toml" --include="*.md" .` мимо `uv.lock` и `docs/plans/` — пусто.
