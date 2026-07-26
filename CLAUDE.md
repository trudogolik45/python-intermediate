## Project
python-intermediate — учебное FastAPI-приложение с каталогом товаров и пользователями, на котором разбираются принципы ООП и слоистая архитектура.

## Stack
- Python 3.10, FastAPI 0.140, Pydantic v2
- API: REST на `/v1/api` и GraphQL на `/v1/gql` (strawberry-graphql 0.323, `GraphQLRouter`)
- Хранение: словари в памяти (`ProductManager`, `UserManager`); планируется SQLAlchemy + PostgreSQL
- Auth: JWT (python-jose, HS256) — пара access/refresh, тип токена в payload полем `type`; пароли через bcrypt. Права — `Permission` (строковый Enum), проверка декоратором `require_permissions`
- Task queue: нет; планируется Kafka

## Architecture
Код в `src/` — это корень пакетов `api`, `core`, `product` и `user`, сам он пакетом не является (`__init__.py` в нём нет), поэтому импорты начинаются с имени пакета: `from core.user.services import UserService`. Пакеты установлены в venv editable-режимом (hatchling, `packages` в `[tool.hatch.build.targets.wheel]`), так что импорт работает из любой директории; новый пакет в `src/` нужно дописать в этот список и выполнить `uv sync`. `src/main.py` собирает приложение. Домены везде в единственном числе. Планы задач — в `docs/plans/`.

Слои, сверху вниз; каждый обращается только к следующему, снизу вверх обращений нет.

1. **API / транспорт** (`api/`) — всё, что знает про протокол. `api/rest/{product,user}/` — роутеры (`views.py`), декораторы, зависимости: разбор запроса, аутентификация (`get_current_user`), права, ответ. Логики нет, вызывают сервис. Единственное место, где рождаются `HTTPException`: `handle_products_errors` / `handle_users_errors` переводят исключения сервисов в коды (нет товара → 404, дубликат → 400, негодный токен → 401), `require_permissions` — 403. `api/graphql/` (`types.py`, `resolvers.py`, `schema.py`, `decorators.py`) — второй транспорт поверх тех же сервисов; доменные исключения переводит в `GraphQLError`. Аутентификации и прав в нём пока нет.
2. **Core / бизнес-правила** (`core/`) — `core/{product,user}/` с сущностями (`entities.py`), бизнес-логикой (`services.py`) и доменными исключениями (`exceptions.py`), плюс общий для обоих доменов `core/permissions.py` (Enum `Permission`). Про HTTP не знает и не должен знать: смена или добавление типа API его не касается.
3. **ORM / Data access** (`product/managers.py`, `user/managers.py`) — доступ к хранилищу, возвращают объекты или `bool`/`None`, про HTTP не знают. При переезде на SQLAlchemy сюда встанут сессия и запросы, слои выше не меняются.
4. **Database** — пока `dict` внутри менеджеров-синглтонов (`product_manager`, `user_manager`), состояние живёт до перезапуска процесса. Дальше — PostgreSQL.

Известные упрощения в `core`, сознательные: сервисы импортируют менеджеры напрямую (зависимость ядра на инфраструктуру не развёрнута через протокол репозитория), `core/product/entities.py` — Pydantic-модель, `core/user/services.py` тянет bcrypt и jose.

## Commands
- Dev: `docker compose up -d --build` — REST-доки http://127.0.0.1:8010/docs, GraphiQL http://127.0.0.1:8010/v1/gql, hot-reload через монтирование `./src`; логи `docker compose logs -f`, остановка `docker compose down`. Правка зависимостей требует пересборки образа — `./src` смонтирован, а пакеты вшиты внутрь
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
