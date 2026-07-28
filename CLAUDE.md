## Project
python-intermediate — учебное FastAPI-приложение с каталогом товаров и пользователями, на котором разбираются принципы ООП и слоистая архитектура.

## Stack
- Python 3.10, FastAPI 0.140, Pydantic v2
- API: REST на `/v1/api` и GraphQL на `/v1/gql` (strawberry-graphql 0.323, `GraphQLRouter`)
- Хранение: PostgreSQL + SQLAlchemy 2.0 (асинхронный, asyncpg — им же ходит Alembic), схема — миграциями Alembic; пользователи лежат в БД, товары пока в словаре в памяти. Загруженные файлы — на диске в `media/` (`FileManager`), наружу раздаются `StaticFiles` по `/media`
- Auth: JWT (python-jose, HS256) — пара access/refresh, тип токена в payload полем `type`; пароли через bcrypt. Права — `Permission` (строковый Enum), проверка декоратором `require_permissions`
- Task queue: нет; планируется Kafka
- Тесты: pytest + pytest-asyncio (`asyncio_mode = "auto"`), интеграционные — в `tests/integration/`

## Architecture
Код в `src/` — это корень пакетов `api`, `core`, `file`, `infrastructure`, `product` и `user`, сам он пакетом не является (`__init__.py` в нём нет), поэтому импорты начинаются с имени пакета: `from core.user.services import UserService`. Пакеты установлены в venv editable-режимом (hatchling, `packages` в `[tool.hatch.build.targets.wheel]`), так что импорт работает из любой директории; новый пакет в `src/` нужно дописать в этот список и выполнить `uv sync`. `src/main.py` собирает приложение. Домены везде в единственном числе. Планы задач — в `docs/plans/`.

Слои, сверху вниз; каждый обращается только к следующему, снизу вверх обращений нет.

1. **API / транспорт** (`api/`) — всё, что знает про протокол. `api/rest/{product,user}/` — роутеры (`views.py`), декораторы, зависимости: разбор запроса, аутентификация (`get_current_user`), права, ответ. Логики нет, вызывают сервис. Единственное место, где рождаются `HTTPException`: `handle_products_errors` / `handle_users_errors` переводят исключения сервисов в коды (нет товара → 404, дубликат → 400, негодный токен → 401), `require_permissions` — 403; тело запроса Pydantic валидирует раньше, чем отработает декоратор, поэтому 422 может опередить 403. `api/graphql/` — второй транспорт поверх тех же сервисов, разложен по доменам как `api/rest/`; доменные исключения переводит в `GraphQLError`. Текущего пользователя кладёт в контекст схемы `get_context` (`dependencies.py`), доступ к резолверу закрывает декоратор `require_permissions` (`api/graphql/decorators.py`) — он же отвечает и за аутентификацию, потому что `get_current_user` здесь возвращает `None` вместо исключения. Приём файлов включается флагом `multipart_uploads_enabled` у `GraphQLRouter`.
2. **Core / бизнес-правила** (`core/`) — `core/{file,product,user}/` с сущностями (`entities.py`), бизнес-логикой (`services.py`) и доменными исключениями (`exceptions.py`), плюс общий для доменов `core/permissions.py` (Enum `Permission`). Про HTTP не знает и не должен знать: смена или добавление типа API его не касается.
3. **ORM / Data access** (`user/repositories.py`, `file/managers.py`, `product/managers.py`) — доступ к хранилищу, возвращают объекты или `bool`/`None`, про HTTP не знают. Тут же ORM-модели (`models.py` в тех же пакетах). `UserRepository` принимает `AsyncSession` в `__init__`, читает через `await session.execute(select(...))` и на границе конвертирует строки таблицы в доменные сущности, чтобы наверх не утекал SQLAlchemy; транзакцией он не управляет — не коммитит и не откатывает. `product`/`file` до сих пор на менеджерах.
4. **Database** — PostgreSQL, подключение и настройки в `infrastructure/`. URL один на всех — `DATABASE_URL` (asyncpg), в контейнере из compose, на хосте из `.env`. Метаданные отделены от подключения: `Base` объявлен в `infrastructure/base.py`, движок и сессия — в `infrastructure/database.py`, поэтому импорт моделей или метаданных не создаёт движок побочно. Alembic на том же asyncpg: `migrations/env.py` поднимает собственный движок с `NullPool` и крутит миграции через `connection.run_sync` (канонический async-шаблон). Сессия создаётся на запрос генератором `get_session` (`infrastructure/database.py`), сервис собирается зависимостью `get_user_service` (`api/dependencies.py`, общая для REST и GraphQL). Границу транзакции держит сервис через `UnitOfWork` (`infrastructure/unit_of_work.py`) — асинхронный контекстный менеджер (`async with`) поверх той же сессии: выход без ошибки коммитит, ошибка откатывает, `SQLAlchemyError` превращается в `UnitOfWorkError`, а сервис отдаёт наверх `ServiceError` (`core/exceptions.py`), чтобы транспорт не знал про SQLAlchemy. Миграции Alembic лежат в корне, а не в `src/`, потому что запускаются с хоста. Товары при этом всё ещё в `dict` в памяти, их состояние живёт до перезапуска процесса. Файлы — отдельно: `file_manager` пишет их на диск в `MEDIA_ROOT`.

Известные упрощения в `core`, сознательные: сервисы импортируют репозитории и менеджеры напрямую (зависимость ядра на инфраструктуру не развёрнута через протокол), `core/product/entities.py` — Pydantic-модель, `core/user/services.py` тянет bcrypt и jose.

## Commands
- Dev: `make build` (или `docker compose up -d --build`) — REST-доки http://127.0.0.1:8010/docs, GraphiQL http://127.0.0.1:8010/v1/gql, hot-reload через монтирование `./src`; логи `docker compose logs -f`, остановка `docker compose down`. Правка зависимостей требует пересборки образа — `./src` смонтирован, а пакеты вшиты внутрь
- Миграции: `uv run alembic upgrade head` — с хоста, не из контейнера; ревизии нумеруются вручную, `--rev-id NNN`
- Test: `make test` — поднимает изолированный тестовый стек (`docker-compose.test.yml`) и гоняет pytest внутри контейнера; таблицы создаются через `Base.metadata.create_all`, Alembic в тестах не участвует

## Verification
Любая правка кода не закончена, пока не прошла по порядку и без замечаний:
1. `uv run ruff format .`
2. `uv run ruff check .`
3. `uvx pyright`
4. `make test`

## Conventions
- Pydantic-модели для тел запросов и ответов
- Права на эндпоинт задаются декоратором `@require_permissions(Permission.X)` — минимальный необходимый набор; такой обработчик обязан принимать `current_user=Depends(get_current_user)`
- Новое право — значение в `Permission`, не строка в коде
- Обработка ошибок — декоратором над обработчиком, не `try/except` в теле; декораторы пишутся с `functools.wraps`, иначе FastAPI не разберёт сигнатуру
- Обработчики async
- Зависимости FastAPI для всего, что берётся из запроса: токен, текущий пользователь, сессия БД и собранный поверх неё сервис

## Don't
- Не класть бизнес-логику в обработчики — она в сервисах
- Не поднимать `HTTPException` в сервисах и менеджерах — это дело слоя эндпоинтов
- Не обращаться к менеджерам напрямую из эндпоинтов
- Не ловить голый `Exception` — только конкретные исключения
- Не писать `# type: ignore` без комментария с причиной
