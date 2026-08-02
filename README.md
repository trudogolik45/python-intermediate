# python-intermediate

Учебный проект на FastAPI, который я писал, чтобы разобрать четыре принципа ООП на живом коде, а не на абстрактных примерах. Начинался он с хранилища в памяти, а дорос до слоистой архитектуры: пользователи лежат в PostgreSQL, поверх сервисов работают два транспорта — REST и GraphQL, всё поднимается docker compose.

Товары и загруженные файлы в базу пока не переехали: товары живут в словаре до перезапуска процесса, файлы пишутся на диск в `media/`.

## Задачи

### 1. Управление товарами

Класс `ProductManager` с методами добавления, получения, обновления и удаления товаров плюс один protected-метод `_is_product_exists`, который проверяет, есть ли продукт в хранилище. На каждый метод менеджера заведён свой эндпоинт.

### 2. Пользователи и наследование

Базовый класс `BaseUser` с общими атрибутами (`id`, `username`, `email`, `is_admin`, `permissions`, `created_at`, `updated_at`). От него унаследованы:

- `AdminUser` — всегда `is_admin=True` и полный набор разрешений;
- `RegularUser` — всегда `is_admin=False`, разрешения передаются списком значений `Permission`.

Метод `get_info` объявлен в `BaseUser` и отдаёт описание пользователя.

### 3. Аутентификация по JWT

`UserService` собирает работу с учётными данными: пароль хешируется через bcrypt при регистрации и проверяется при логине, а `/users/login` выдаёт пару токенов. Access живёт минуту, refresh — десять; тип записан в payload полем `type`, поэтому refresh не пройдёт туда, где нужен access, и наоборот. Обменять refresh на новый access можно через `/users/refresh`. Защищённые эндпоинты получают пользователя зависимостью `get_current_user`, которая читает токен из заголовка `Authorization`.

### 4. Авторизация по правам

Разрешения собраны в `Permission` — строковый Enum, поэтому опечатка в праве ловится на входе, а не молча превращается в отказ доступа. Каждому эндпоинту задан минимальный набор прав декоратором `require_permissions`: просмотру товара нужен `view_product`, созданию — `add_product`, обновлению — `update_product`, удалению — `delete_product`; списку пользователей — `view_user`, изменению чужих админских прав — `update_user`, списку файлов — `view_file`, загрузке — `upload_file`. Декоратор берёт пользователя из параметра `current_user`, который приходит зависимостью `get_current_user`, и сверяет требуемые права с его `permissions`; не хватает хотя бы одного — 403. Отдельной ветки для администратора нет: `AdminUser` создаётся с полным набором прав и проходит ту же проверку, что и все.

### 5. Исключения и декораторы

Сервисы не знают про HTTP: `ProductService` поднимает `ProductNotFoundError` и `ProductAlreadyExistsError`, `UserService` — `UserAlreadyExistsError`, `InvalidCredentialsError` и `InvalidTokenError`. В коды ответа их переводят декораторы `handle_products_errors` и `handle_users_errors` на эндпоинтах, так что try/except не расползается по обработчикам. Декораторы обёрнуты `functools.wraps`, поэтому FastAPI по цепочке `__wrapped__` видит настоящую сигнатуру обработчика и собирает схему как обычно.

### 6. Второй транспорт: GraphQL

Схема на strawberry-graphql висит на `/v1/gql` и ходит в те же сервисы, что и REST, — доказательство того, что бизнес-логика от протокола не зависит. `Query` и `Mutation` собираются из доменных кусков (`UserQuery`, `FileQuery`, `UserMutation`, `FileMutation`). Текущего пользователя резолверы берут из контекста схемы, доменные исключения превращаются в `GraphQLError`. Списки отдаются страницами через дженерик `Page[T]` с `limit`/`offset`.

### 7. Загрузка файлов

`FileManager` пишет файлы на диск в `media/` и отдаёт список имён, `FileService` держит правила поверх него. Загрузка сделана мутацией GraphQL: приём multipart включается флагом `multipart_uploads_enabled` у роутера, а раздаёт сохранённое `StaticFiles` по `/media`.

### 8. PostgreSQL, репозиторий и Unit of Work

Пользователи переехали из словаря в PostgreSQL. Доступ к таблице закрыт `UserRepository`: он получает `AsyncSession` снаружи и на границе конвертирует строки в `AdminUser`/`RegularUser`, поэтому SQLAlchemy не протекает в сервисы. Транзакцией репозиторий не управляет — границу держит сервис через `UnitOfWork`: выход из `async with` без ошибки коммитит, ошибка откатывает, а `SQLAlchemyError` превращается в `UnitOfWorkError` и дальше в `ServiceError`. Схему таблиц ведёт Alembic (`migrations/`), подключение — асинхронное, на asyncpg.

### 9. Docker и тесты

Приложение, база и pgAdmin поднимаются одним `docker compose`; `./src` смонтирован внутрь, поэтому правки подхватываются без пересборки. Тесты гоняются в отдельном стеке (`docker-compose.test.yml`) на своей базе: таблицы создаются из метаданных, регистрация пользователя проверяется интеграционным тестом, который ходит по HTTP и читает результат из базы.

## Концепции

**Инкапсуляция.** Атрибуты `BaseUser` инициализируются через `__init__`, наружу отдаётся только `get_info()` — внутреннее устройство объекта не торчит в эндпоинтах. У `ProductManager` и `FileManager` та же идея: хранилище меняется методами, а проверка существования вынесена в protected `_is_product_exists` и `_is_file_exists`, наружу они не предназначены.

**Наследование.** `AdminUser` и `RegularUser` берут от `BaseUser` конструктор и `get_info`, а сами задают только то, чем отличаются — флаг `is_admin` и правила выдачи разрешений. Общий код не дублируется.

**Полиморфизм.** Эндпоинт списка пользователей вызывает `get_info()` у каждого объекта, не проверяя его тип: администратор и обычный пользователь обрабатываются одинаково.

**Абстракция.** `BaseUser` собирает то, что верно для любого пользователя, а подклассы доопределяют роль. Из-за этого при добавлении нового типа пользователя менять репозиторий и эндпоинты не придётся.

## Структура

`src/` — корень пакетов, сам он пакетом не является, поэтому импорты идут от имени пакета: `from core.user.services import UserService`.

```
src/main.py                    — сборка приложения: REST под /v1/api, GraphQL на /v1/gql, media
src/api/dependencies.py        — get_user_service: сессия и сервис поверх неё
src/api/rest/product/          — views, decorators: эндпоинты товаров
src/api/rest/user/             — views, decorators, dependencies, models: эндпоинты пользователей
src/api/graphql/               — schema, resolvers, pagination, dependencies, decorators
src/api/graphql/user/          — типы и резолверы пользователей
src/api/graphql/file/          — типы и резолверы файлов
src/core/permissions.py        — Permission: перечисление прав
src/core/product/              — entities, services, exceptions
src/core/user/                 — entities (BaseUser, AdminUser, RegularUser), services, exceptions
src/core/file/                 — services, exceptions
src/core/exceptions.py         — ServiceError
src/user/                      — ORM-модель User и UserRepository
src/product/managers.py        — ProductManager: товары в памяти
src/file/managers.py           — FileManager: файлы на диске в media/
src/infrastructure/            — base, database, config, unit_of_work, exceptions
migrations/                    — ревизии Alembic
tests/integration/             — интеграционные тесты
```

## Эндпоинты

REST:

| Метод | Путь | Что делает | Требует права |
|---|---|---|---|
| POST | `/v1/api/products` | добавить товар | `add_product` |
| GET | `/v1/api/products/{product_id}` | получить товар | `view_product` |
| PUT | `/v1/api/products/{product_id}` | обновить товар | `update_product` |
| DELETE | `/v1/api/products/{product_id}` | удалить товар | `delete_product` |
| POST | `/v1/api/users` | добавить пользователя | — |
| GET | `/v1/api/users` | список пользователей | `view_user` |
| PATCH | `/v1/api/users/{user_id}` | выдать или снять админские права | `update_user` |
| POST | `/v1/api/users/login` | получить пару access- и refresh-токенов | — |
| GET | `/v1/api/users/refresh` | обменять refresh-токен на новый access | — |
| GET | `/v1/api/users/me` | текущий пользователь по токену | только токен |

GraphQL на `/v1/gql`:

| Операция | Что делает | Требует права |
|---|---|---|
| `allUsers(limit, offset)` | страница пользователей | `view_user` |
| `files(limit, offset)` | страница загруженных файлов | `view_file` |
| `register(username, password, email)` | регистрация | — |
| `login(username, password)` | пара токенов | — |
| `uploadFile(file)` | загрузка файла | `upload_file` |

## Запуск

- `make build` — поднять стек: REST-доки http://127.0.0.1:8010/docs, GraphiQL http://127.0.0.1:8010/v1/gql, pgAdmin http://127.0.0.1:5050
- `make down` — остановить
- `uv run alembic upgrade head` — накатить миграции, с хоста
- `make test` — прогнать тесты в изолированном стеке
