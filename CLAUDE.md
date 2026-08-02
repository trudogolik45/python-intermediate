## Project

`python-intermediate` — учебное FastAPI-приложение с каталогом товаров и пользователями для изучения ООП и слоистой архитектуры.

## Stack

- Python 3.10, FastAPI, Pydantic v2
- REST `/v1/api`
- GraphQL `/v1/gql` на Strawberry
- PostgreSQL, SQLAlchemy 2.0 async, asyncpg, Alembic
- JWT access/refresh, bcrypt, `Permission`
- pytest, pytest-asyncio
- Task queue временно отсутствует

## Structure

- `src/main.py` — сборка приложения; `src/` — корень пакетов `api`, `core`, `file`, `infrastructure`, `product`, `user`. Сам `src` не пакет; импорты начинаются с имени пакета, домены — в единственном числе.
- `api/rest/{product,user}/`, `api/graphql/`, `api/dependencies.py` — REST, GraphQL и общие зависимости транспорта.
- `core/{file,product,user}/{entities,services,exceptions}.py`, `core/exceptions.py`, `core/permissions.py` — сущности, бизнес-логика, ошибки и права.
- `user/{repositories,models}.py`, `product/{managers,models}.py`, `file/{managers,models}.py` — доступ к данным и ORM-модели.
- `infrastructure/{base,database,unit_of_work}.py` — `Base`, движок, сессии и транзакции; используются `DATABASE_URL` и `TEST_DATABASE_URL`.
- `migrations/` — Alembic с хоста; `tests/integration/` — интеграционные тесты; `media/` — файлы по `/media`.

## Commands

- Dev: `make build`
- Migrate: `uv run alembic upgrade head`
- Manual smoke: `uv run python .claude/skills/run-python-intermediate/driver.py up|smoke|reset|logs|token`
- После каждого изменения запускай по порядку:
  1. `uv run ruff format .`
  2. `uv run ruff check .`
  3. `uvx pyright`
  4. `make test`

## Conventions

- Используй Pydantic-схемы, async-обработчики и FastAPI dependencies.
- Права задавай через `Permission` и `@require_permissions(...)`.
- Новый пакет в `src/` добавляй в editable-установку и синхронизируй окружение.
- REST и GraphQL используют одни сервисы: после изменения их контракта проверяй оба транспорта, GraphQL — дополнительно вручную.

## Don't

- Не клади бизнес-логику в роутеры и резолверы.
- Не вызывай repositories/managers напрямую из API.
- Не поднимай `HTTPException` или `GraphQLError` вне транспортного слоя.
- Не выпускай ORM-модели и SQLAlchemy-ошибки выше data-access слоя.
- Не управляй транзакциями внутри repository — используй `UnitOfWork` в сервисе.
- Не лови голый `Exception`.
- Не используй `# type: ignore` без комментария с причиной.
