# Урок 11: регистрация, логин и список юзеров в GraphQL

## Context

Урок 11 видеокурса «Python на практике» переносит на GraphQL три эндпоинта, которые уже работают в REST: регистрацию, логин и получение списка пользователей. Смысл упражнения — показать, что слоистая архитектура из урока 10 окупается: меняется только транспортный слой, `core` и менеджеры остаются нетронутыми.

Сейчас `src/api/graphql/` — учебная заглушка: тип `User` с полем `id`, одна query `user(id: int)` поверх захардкоженного словаря `USERS` (`src/api/graphql/resolvers.py:5-8`), схема без мутаций. К сервисам GraphQL не обращается вообще.

Часть шагов урока в нашей кодовой базе уже сделана и повторять их не нужно:

- **Хеширование пароля** автор урока переносит из REST-обработчика в сервис (2:19–2:41) — у нас оно с самого начала в `UserService.register_user` (`src/core/user/services.py:19`).
- **Замена `HTTPException` на `ValueError` в резолвере логина** (4:34) — у нас сервисы уже кидают доменные исключения (`InvalidCredentialsError`, `UserAlreadyExistsError`), `HTTPException` живёт только в REST-декораторах.

Решения, согласованные с пользователем:

- `allUsers` — **без защиты**, как в уроке. Расхождение с REST (`GET /users` требует `Permission.VIEW_USER`) осознанное: разбор аутентификации в GraphQL-контексте — тема отдельного шага.
- `UserManager.get_all_users()` начинает возвращать **сущности**, как в уроке, но `BaseUser.get_info()` остаётся, и REST-обработчик маппит через него сам. В видео REST после этой правки отдаёт сущности напрямую, а FastAPI сериализует их через `vars()` — вместе с хешем пароля; у нас ответ `GET /users` не меняется.
- Объём — **три операции урока**: `register`, `login`, `allUsers`. `refreshToken` и `me` в GraphQL не переносим.

## Изменения

### 1. `src/api/graphql/types.py` — типы схемы

Убрать `id` из `User` (сущности проекта id не имеют), добавить `Token`:

```python
@strawberry.type
class User:
    username: str
    email: str


@strawberry.type
class Token:
    access_token: str
    refresh_token: str
```

Strawberry сам переведёт поля в camelCase: в схеме будет `accessToken` / `refreshToken`.

### 2. `src/user/managers.py` — менеджер отдаёт сущности

```python
    def get_all_users(self):
        return list(self.users.values())
```

`get_info()` в `src/core/user/entities.py` не трогаем — на нём остаётся REST-представление.

### 3. `src/api/rest/user/views.py` — маппинг переезжает в транспорт

```python
@user_router.get("")
@require_permissions(Permission.VIEW_USER)
async def get_all_users(current_user=Depends(get_current_user)):
    return [user.get_info() for user in UserService.get_all_users()]
```

Единственная правка в REST; тело ответа остаётся прежним.

### 4. `src/api/graphql/decorators.py` — новый файл

Симметрия с `src/api/rest/user/decorators.py`: единственное место, где доменные исключения превращаются в ошибки транспорта. Без него всё тоже работало бы (graphql-core сам ловит исключение резолвера и кладёт его текст в `errors`), но тогда каждое ожидаемое доменное исключение попадает в логи с traceback как сбой сервера.

```python
from functools import wraps

from graphql import GraphQLError

from core.user.exceptions import InvalidCredentialsError, UserAlreadyExistsError


def handle_users_errors(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except (UserAlreadyExistsError, InvalidCredentialsError) as error:
            raise GraphQLError(str(error)) from error

    return wrapper
```

`GraphQLError` — из `graphql` (graphql-core 3.2.11, уже в зависимостях как транзитивная зависимость strawberry).

### 5. `src/api/graphql/resolvers.py` — Query и Mutation поверх сервиса

Словарь `USERS` и резолвер `user(id)` удаляются целиком.

```python
@strawberry.type
class Query:
    @strawberry.field
    async def all_users(self) -> list[User]:
        return [User(username=user.username, email=user.email) for user in UserService.get_all_users()]


@strawberry.type
class Mutation:
    @strawberry.mutation
    @handle_users_errors
    async def register(self, username: str, password: str, email: str) -> User:
        UserService.register_user(username, password, email, is_admin=False, permissions=[])
        return User(username=username, email=email)

    @strawberry.mutation
    @handle_users_errors
    async def login(self, username: str, password: str) -> Token:
        return Token(**UserService.login(username, password))
```

Два момента:

- Порядок декораторов важен: `@strawberry.mutation` обязан быть **внешним**. Он возвращает `StrawberryField`, а не функцию, поэтому обернуть его нашим декоратором нельзя. `functools.wraps` сохраняет сигнатуру и аннотации, так что strawberry разберёт параметры корректно — тот же контракт, что у FastAPI в REST-слое.
- Регистрация через GraphQL всегда создаёт обычного юзера без прав (`is_admin=False`, `permissions=[]`), как в уроке. Админов по-прежнему заводят через REST.

### 6. `src/api/graphql/schema.py` — подключить мутации

```python
schema = strawberry.Schema(query=Query, mutation=Mutation)
```

`src/main.py` не меняется — роутер уже смонтирован на `/v1/gql`.

## Verification

1. `uv run ruff format .`
2. `uv run ruff check .`
3. `uvx pyright`
4. `docker compose up -d` (зависимости не менялись, пересборка образа не нужна; `./src` смонтирован), логи — `docker compose logs -f web_app`
5. GraphiQL — http://127.0.0.1:8010/v1/gql, прогнать сценарий урока:
   - `mutation { register(username: "john", password: "123", email: "john@example.com") { username email } }` → юзер создан;
   - повторить тот же запрос → в `errors` сообщение `User john already exists`;
   - `mutation { login(username: "john", password: "123") { accessToken refreshToken } }` → пара токенов; запросить только `accessToken` — вернётся одно поле;
   - `mutation { login(username: "john", password: "wrong") { accessToken } }` → `Invalid username or password`;
   - `query { allUsers { username email } }` → список; убрать `email` — останется только `username`.
6. Регрессия REST: завести админа `POST /v1/api/users?username=admin&password=123&email=a@b.c&is_admin=true`, залогиниться через `GET /v1/api/users/login`, дёрнуть `GET /v1/api/users` с заголовком `Authorization: <access_token>`. Ответ должен остаться прежним — `username`, `email`, `is_admin`, `permissions` и **без** `password`.
