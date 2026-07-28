---
name: run-python-intermediate
description: Запустить, собрать, проверить и продиагностировать python-intermediate — FastAPI-приложение с REST (/v1/api) и GraphQL (/v1/gql) поверх PostgreSQL. Используй, когда просят run, start, build, launch, smoke-test, прогнать тесты, дёрнуть эндпоинт, получить токен, поднять docker compose или разобраться, почему приложение отвечает 500/401.
---

# Запуск python-intermediate

FastAPI-приложение: REST на `/v1/api`, GraphQL на `/v1/gql`, PostgreSQL через асинхронный SQLAlchemy, файлы на диске в `media/`. Живого GUI нет — приложение драйвится по HTTP.

Драйвер: **`.claude/skills/run-python-intermediate/driver.py`** — поднимает стек, накатывает схему и прогоняет 21 проверку через реальные HTTP-запросы (регистрация, JWT, права, товары, GraphQL, загрузка файла, раздача `/media`).

Все пути ниже — от корня репозитория. Все команды выполняются с хоста, не из контейнера.

## Предварительно

Нужны `docker` (с `docker compose` v2) и `uv`. Больше ничего — Python и зависимости живут в контейнере и в `.venv`.

```bash
uv sync
```

`.env` в корне драйверу не нужен: `DATABASE_URL` он передаёт явно. Для ручных `uv run alembic ...` `.env` нужен — там та же одна переменная.

## Запуск (путь агента)

```bash
# поднять стек, дождаться готовности, накатить миграции
uv run python .claude/skills/run-python-intermediate/driver.py up

# полный e2e-прогон по живому приложению
uv run python .claude/skills/run-python-intermediate/driver.py smoke
```

`smoke` печатает `OK` / `FAIL` по каждой проверке и завершается с ненулевым кодом при провале. Ожидаемый хвост вывода:

```
=== пройдено 21, провалено 0 ===
```

Остальные команды драйвера:

| Команда | Что делает |
|---|---|
| `up` | `docker compose up -d --build`, ожидание `/docs`, `alembic upgrade head` |
| `smoke` | 21 проверка по REST и GraphQL, уникальные имена на каждый прогон |
| `reset` | `docker compose down -v` + `up` — чистая БД с нуля |
| `token [user] [pass]` | печатает access-токен для ручных curl |
| `logs` | последние 50 строк лога приложения |
| `down` | гасит стек |

Ручной запрос поверх поднятого стека — токен идёт в `Authorization` **без** `Bearer`:

```bash
TOKEN=$(uv run python .claude/skills/run-python-intermediate/driver.py token admin pass)
curl -s -H "Authorization: $TOKEN" http://127.0.0.1:8010/v1/api/users/me
```

## Прямой вызов кода (без HTTP)

Для правок в сервисе, репозитории или UoW полное приложение не нужно — сервис собирается поверх сессии одной строкой. Запись реально коммитится через `UnitOfWork`, поэтому нужен поднятый Postgres (`driver.py up`):

```bash
DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/mydatabase" uv run python -c '
import asyncio, uuid
from core.user.services import UserService
from infrastructure.database import SessionLocal

async def main():
    name = f"direct_{uuid.uuid4().hex[:8]}"
    async with SessionLocal() as session:
        service = UserService.with_session(session)
        await service.register_user(name, "pass", f"{name}@example.com", False, ["view_user"])
        print(f"создан {name}, всего пользователей: {len(await service.get_all_users())}")

asyncio.run(main())
'
```

Имя генерируется: `username` и `email` уникальны в БД, и повторный запуск с фиксированным именем упадёт `UserAlreadyExistsError` (исключение долетает наружу как есть — `HTTPException` рождается только в слое эндпоинтов).

## Тесты

```bash
make test
```

Поднимает `docker-compose.test.yml` (своё имя проекта, Postgres в tmpfs), гоняет `pytest` внутри контейнера, гасит стек и сохраняет код возврата. Тесты пересоздают таблицы через `Base.metadata.create_all` — миграции в них не участвуют, и рабочей БД они не касаются.

## Запуск (человеческий путь)

`make build` → http://127.0.0.1:8010/docs (Swagger UI), http://127.0.0.1:8010/v1/gql (GraphiQL), pgAdmin на http://127.0.0.1:5050 (`admin@admin.com` / `admin`). `make down` — остановить. Схему всё равно нужно накатить руками: `uv run alembic upgrade head`.

## Грабли

- **`Authorization` без `Bearer`.** Аутентификация на `APIKeyHeader`, токен кладётся в заголовок голым. Привычное `Bearer <token>` даёт 401.
- **Access-токен живёт 60 секунд** (`ACCESS_TOKEN_EXPIRE_MINUTES = 1` в `src/core/user/services.py`). Проверено: через 61 секунду тот же токен отдаёт 401. Скрипт длиннее минуты обязан перелогиниваться — драйвер логинится в начале каждой секции.
- **Логин — это `GET` с query-параметрами**, не POST с телом: `GET /v1/api/users/login?username=...&password=...`. Регистрация при этом POST с JSON-телом.
- **Без миграций приложение стартует, а запись падает 500.** `/docs` открывается, но `POST /v1/api/users` отдаёт `{"detail":"Failed to register user"}` — отсутствующая таблица заворачивается в `UnitOfWorkError` → `ServiceError`, и настоящая причина видна только в `driver.py logs`. Первое, что стоит проверить при 500 на запись.
- **Правка зависимостей требует пересборки образа.** `./src` смонтирован и hot-reload работает, но пакеты вшиты в образ: `docker compose up -d` без `--build` после `uv add` даёт `ModuleNotFoundError` в логе, а контейнер молча остаётся не-running.
- **Товары живут в памяти процесса.** Проверено: после `docker compose restart web_app` товар отдаёт 404, а пользователь по тому же токену — 200. Не считать пропажу товара багом после рестарта.
- **Загруженные файлы переживают всё.** `media/` смонтирован с хоста, повторная загрузка того же имени даёт GraphQL-ошибку `File ... already exists`. Драйвер поэтому генерирует имена с суффиксом.
- **GraphQL отвечает 200 даже на отказ.** Без токена `allUsers` возвращает HTTP 200 с `errors[0].message == "Authentication required"`. Проверять статус бесполезно — надо смотреть в `errors`.
- **422 опережает 403.** FastAPI валидирует тело до входа в обработчик, а права проверяет декоратор внутри него. Кривое тело от пользователя без прав даст 422, и это легко принять за проблему с правами.
- **`POST /v1/api/products` требует `id` в теле** — идентификатор задаёт клиент, сервер его не генерирует.

## Разбор ошибок

| Симптом | Причина и что делать |
|---|---|
| `{"detail":"Failed to register user"}`, HTTP 500 | Схема не накатана. `uv run python .claude/skills/run-python-intermediate/driver.py up` (в нём есть `alembic upgrade head`) |
| `ModuleNotFoundError: No module named 'asyncpg'` в логе, контейнер не в `running` | Образ старее зависимостей. `make build` или `driver.py up` — оба с `--build` |
| `sqlalchemy.exc.ArgumentError: Could not parse SQLAlchemy URL from given URL string` при `alembic` | В `.env` нет `DATABASE_URL`. Обходной путь без `.env` — передать её в окружении команды |
| 401 на любой запрос с токеном | Либо префикс `Bearer`, либо токен старше минуты. Взять свежий: `driver.py token` |
| 403 там, где ждёшь 200 | У пользователя нет права. Права выдаются при регистрации полем `permissions`, админ (`is_admin: true`) получает все |
| `driver.py smoke` пишет «сначала подними стек» | Приложение не отвечает на 8010. `driver.py logs` покажет, упало ли оно на старте |
