## Project
python-intermediate — учебное FastAPI-приложение с каталогом товаров и пользователями, на котором разбираются принципы ООП и слоистая архитектура.

## Stack
- Python 3.10, FastAPI 0.140, Pydantic v2
- Хранение: словари в памяти (`ProductManager`, `UserManager`); планируется SQLAlchemy + PostgreSQL
- Auth: JWT (python-jose, HS256) — пара access/refresh, тип токена в payload полем `type`; пароли через bcrypt. Права — `Permission` (строковый Enum), проверка зависимостью `check_permissions`
- Task queue: нет; планируется Kafka

## Architecture
Код в `src/` — это корень пакетов `products` и `users`, сам он пакетом не является (`__init__.py` в нём нет), поэтому импорты начинаются с имени пакета: `from users.services import UserService`. Пакеты установлены в venv editable-режимом (hatchling, `packages` в `[tool.hatch.build.targets.wheel]`), так что импорт работает из любой директории; новый пакет в `src/` нужно дописать в этот список и выполнить `uv sync`. `src/main.py` собирает приложение, роутеры под префиксом `/v1/api`. Планы задач — в `docs/plans/`.

Слои, сверху вниз; каждый обращается только к следующему, снизу вверх обращений нет.

1. **Endpoints** (`*/views.py`, `*/decorators.py`, `users/dependencies.py`) — роутеры, декораторы, зависимости: разбор запроса, аутентификация (`get_current_user`), права, ответ. Логики нет, вызывают сервис. Единственное место, где рождаются `HTTPException`: `handle_products_errors` / `handle_users_errors` переводят исключения сервисов в коды (нет товара → 404, дубликат → 400, негодный токен → 401), `require_permissions` — 403.
2. **Services** (`*/services.py`) — бизнес-логика. Про HTTP не знает, поднимает свои исключения из `*/exceptions.py` (`ProductNotFoundError`, `UserAlreadyExistsError` и прочие).
3. **ORM / Data access** (`*/managers.py`) — доступ к хранилищу, возвращают объекты или `bool`/`None`, про HTTP не знают. При переезде на SQLAlchemy сюда встанут сессия и запросы, слои выше не меняются.
4. **Database** — пока `dict` внутри менеджеров-синглтонов (`product_manager`, `user_manager`), состояние живёт до перезапуска процесса. Дальше — PostgreSQL.

Общие для всех слоёв, зависимостей на слои не имеют: модели `*/models.py` (`Product`, `BaseUser`/`AdminUser`/`RegularUser`), исключения `*/exceptions.py`, права `users/permissions.py` (Enum `Permission`).

## Commands
- Dev: `docker compose up -d --build` — http://127.0.0.1:8010/docs, hot-reload через монтирование `./src`; логи `docker compose logs -f`, остановка `docker compose down`
- Test: тестов пока нет

## Verification
Любая правка кода не закончена, пока не прошла по порядку и без замечаний:
1. `uv run ruff format .`
2. `uv run ruff check .`
3. `uvx pyright`

## Conventions
- Pydantic-модели для тел запросов и ответов
- Права на эндпоинт задаются декоратором `@require_permissions(Permission.X)` — минимальный необходимый набор; такой обработчик обязан принимать `current_user=Depends(get_current_user)`
- Новое право — значение в `Permission`, не строка в коде
- Обработка ошибок — декоратором над обработчиком, не `try/except` в теле; декораторы пишутся с `functools.wraps`, иначе FastAPI не разберёт сигнатуру
- Обработчики async
- Зависимости FastAPI для всего, что берётся из запроса: токен, текущий пользователь, в будущем сессия БД

## Don't
- Не класть бизнес-логику в обработчики — она в сервисах
- Не поднимать `HTTPException` в сервисах и менеджерах — это дело слоя эндпоинтов
- Не обращаться к менеджерам напрямую из эндпоинтов
- Не ловить голый `Exception` — только конкретные исключения
- Не писать `# type: ignore` без комментария с причиной
