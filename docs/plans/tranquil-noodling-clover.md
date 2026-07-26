# Alembic и модель User на SQLAlchemy

## Context

Урок 15 курса — подключение Alembic и первая миграция. Проект уже подготовлен предыдущими уроками: в `docker-compose.yml` подняты `db` (postgres:16) и `pgadmin`, наружу проброшен порт 5432, в сервис `web_app` прокинут `DATABASE_URL` (`docker-compose.yml:11`), а `sqlalchemy>=2.0.51` и `psycopg2-binary` лежат в зависимостях (`pyproject.toml:10-12`). Не хватает всего, что между БД и кодом: настроек, `engine`/`Base`, модели и самого Alembic.

Хранение при этом остаётся прежним — `dict` внутри `UserManager`/`ProductManager`. Этот шаг создаёт таблицу `users` и механизм миграций, но приложение в неё ещё не пишет; переезд менеджеров — следующий урок. Такое расхождение сознательное, чтобы шаги совпадали с курсом.

Решения, согласованные с пользователем:
- объём — строго урок 15: настройки, инфраструктура БД, модель `User`, Alembic, первая миграция;
- Alembic запускается **с хоста** через `uv run`, а не изнутри контейнера. Порт 5432 уже проброшен, поэтому проблема из видео (файлы, созданные root в контейнере, не редактируются на хосте, лечится `chown -R`) не возникает вовсе;
- SQLAlchemy синхронный (psycopg2), как в уроке;
- `permissions` кладём в таблицу сразу — колонкой JSON, чтобы схема совпадала с `BaseUser` (`core/user/entities.py:5`) и на следующем шаге не понадобилась вторая миграция;
- `.env` коммитим — учебный проект, пароли и так открыты в `docker-compose.yml`.

Отступления от видео и их причина:
- `DeclarativeBase` + `Mapped`/`mapped_column` вместо `declarative_base()` и `Column`. Это штатный стиль SQLAlchemy 2.0; старый работает, но типы колонок в нём не видны pyright, а он у нас в обязательной проверке.
- `pydantic-settings` **не** добавляем отдельной зависимостью — он уже приходит транзитивно с `fastapi[standard]` (`uv.lock:233`), ровно как `python-multipart` в прошлом уроке.
- `alembic init` запускается на хосте, поэтому шага с `chown` в плане нет.

## Реализация

### 1. Зависимость

```
uv add alembic
```

В `pyproject.toml` в `[tool.hatch.build.targets.wheel].packages` дописать `"src/infrastructure"`, затем `uv sync` — иначе `import infrastructure.database` не разрешится (`src` сам пакетом не является, работают только перечисленные подпакеты).

### 2. Новый пакет `src/infrastructure/`

`config.py` — настройки из окружения:

```python
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    database_url: str = ""


settings = Settings()
```

Путь к `.env` абсолютный — считается от файла, как `MEDIA_ROOT` в `file/managers.py:3`. Относительный путь резолвится от рабочей директории и сломался бы при запуске Alembic не из корня. Внутри контейнера `.env` нет (Dockerfile копирует только `pyproject.toml`, `uv.lock`, `README.md` и `src/`), и это правильно: переменная окружения из compose имеет приоритет над dotenv, так что контейнер ходит на `db:5432`, а хост — на `localhost:5432`.

`database.py` — подключение:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from infrastructure.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass
```

Плюс пустой `__init__.py`, как у остальных пакетов.

По слоям из `CLAUDE.md` это низ: `infrastructure` знает про БД и ничего не знает про `core` и `api`. Ни `main.py`, ни сервисы его пока не импортируют — на этом шаге он нужен только моделям и Alembic.

### 3. Модель — `src/user/models.py`

Ложится рядом с `user/managers.py`, в слой 3 (data access), туда, где `CLAUDE.md` и обещал сессию с запросами.

```python
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    permissions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

`username` уникален — сейчас он ключ словаря в `UserManager` (`user/managers.py:11`) и по нему же идёт вход (`core/user/services.py:50`). `server_default=func.now()` считает время на стороне PostgreSQL, `onupdate` — на стороне SQLAlchemy при UPDATE через сессию.

### 4. Alembic

Инициализация с хоста, из корня проекта:

```
uv run alembic init migrations
```

Появятся `alembic.ini` и `migrations/` (`env.py`, `script.py.mako`, `versions/`).

Правки в `alembic.ini`: значение `sqlalchemy.url` оставить пустым — URL подставляется в `env.py` из настроек, чтобы адрес БД жил в одном месте.

Правки в `migrations/env.py` — три вставки в сгенерированный шаблон:

```python
from infrastructure.config import settings
from infrastructure.database import Base
from user import models  # noqa: F401 — импорт регистрирует User в Base.metadata

config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata
```

Импорт `user.models` обязателен: без него `Base.metadata` пустая и `--autogenerate` выдаст миграцию без таблиц. `prepend_sys_path` в `alembic.ini` трогать не нужно — пакеты стоят в venv в editable-режиме, импорт работает из любой директории.

Заодно из `env.py` стоит убрать шаблонные комментарии Alembic — файл проходит через `ruff` и `pyright` вместе с остальным кодом.

Первая миграция:

```
uv run alembic revision --autogenerate -m "create users" --rev-id 001
uv run alembic upgrade head
```

`--rev-id 001` — ручной номер вместо хэша, как в уроке: файлы в `versions/` читаются по порядку.

### 5. Файлы окружения и ignore

`.env` в корне (коммитим):

```
DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/mydatabase
```

Отличается от значения в `docker-compose.yml:11` только хостом: `localhost` вместо `db`. Внутри контейнера имени `localhost` для БД нет, снаружи — нет имени `db`.

`.gitignore`: ничего добавлять не нужно, `migrations/versions/*.py` — код, который должен быть в репозитории.

### 6. `CLAUDE.md`

Коротко, без пересказа кода:
- **Stack** — хранение больше не «планируется SQLAlchemy»: схема `users` живёт в PostgreSQL, миграции Alembic, менеджеры пока на словарях;
- **Architecture** — слой 3 упомянуть `user/models.py`, слой 4 — что `infrastructure/` держит `engine`, `SessionLocal` и `Base`, а `migrations/` лежит в корне;
- **Commands** — как накатить и откатить миграцию.

## Verification

Обязательный прогон из `CLAUDE.md`: `uv run ruff format .` → `uv run ruff check .` → `uvx pyright`. Отдельно проследить за сгенерированным `migrations/env.py` — под линтер он попадает наравне с остальным кодом.

Дальше сквозной сценарий:

1. `docker compose up -d --build` — пересборка обязательна, менялись `pyproject.toml` и `uv.lock`. Приложение должно подняться как раньше: http://127.0.0.1:8010/docs открывается.
2. `uv run alembic upgrade head` с хоста → в выводе `Running upgrade -> 001, create users`.
3. pgAdmin http://127.0.0.1:5050 (admin@admin.com / admin), БД `mydatabase`: в схеме `public` появились `users` и `alembic_version`; в `alembic_version` лежит `001`; у `users` есть колонки `id`, `username`, `email`, `password`, `is_admin`, `permissions`, `created_at`, `updated_at` и индексы по `id`, `username`, `email`.
4. `uv run alembic downgrade -1` → таблица и индексы удалены, `alembic_version` пуста, файл миграции на месте. Затем `uv run alembic upgrade head` — состояние вернулось.
5. `uv run alembic revision --autogenerate -m "check"` сразу после upgrade должен дать **пустую** миграцию (`pass` в `upgrade`/`downgrade`) — значит модель и схема БД сошлись. Файл после проверки удалить.
6. Проверка изнутри контейнера, что настройки читаются и там:
   `docker compose exec web_app python -c "from infrastructure.config import settings; print(settings.database_url)"` → адрес с хостом `db`, а не `localhost`.
7. Регрессия: старые сценарии не задеты, данные по-прежнему в памяти.
   - `curl -X POST "http://127.0.0.1:8010/v1/api/users?username=admin&password=secret&email=a@b.c&is_admin=true"`
   - `curl "http://127.0.0.1:8010/v1/api/users/login?username=admin&password=secret"` → пара токенов
   - `curl -H "Authorization: $TOKEN" http://127.0.0.1:8010/v1/api/users` → список пользователей
   - GraphiQL http://127.0.0.1:8010/v1/gql — `{ allUsers(limit: 5) { items { username } } }` под тем же токеном
   - в pgAdmin таблица `users` при этом остаётся пустой — ожидаемо, менеджеры ещё не переехали.

## Известные упрощения

- Таблица создана, но приложением не используется — до переезда менеджеров на сессию.
- Драйвер синхронный: когда запросы к БД появятся в async-обработчиках, они будут блокировать event loop, как сейчас bcrypt в `UserService`.
- `permissions` в JSON-колонке — без внешних ключей и без проверки значений на стороне БД; валидация остаётся за `Permission` в коде.
