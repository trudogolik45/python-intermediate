# Урок 12: аутентификация в GraphQL

## Context

Урок 11 закрыт с сознательным пропуском: `allUsers` в GraphQL отдаёт список кому угодно, тогда как REST-аналог `GET /v1/api/users` требует токен и `Permission.VIEW_USER`. Урок 12 этот пропуск закрывает — показывает, как в GraphQL устроены аутентификация и защищённые эндпоинты: `register` и `login` остаются публичными, `allUsers` закрывается access-токеном.

Механизм тот же, что и в REST: зависимость FastAPI достаёт пользователя из заголовка `Authorization`, результат кладётся в контекст схемы через `context_getter` у `GraphQLRouter`, а решение «пускать или нет» принимает декоратор резолвера — как `require_permissions` в `src/api/rest/user/decorators.py`.

Заодно урок наводит порядок в структуре: `api/graphql/` разбивается на домены по образцу `api/rest/{product,user}/`, а сборные `Query` / `Mutation` собираются наследованием из доменных.

Решения, согласованные с пользователем:

- **Модульная разбивка делается сейчас**, как в уроке, — структура GraphQL совпадёт с REST.
- Проверяется **только аутентификация**, без прав. Расхождение с REST по `Permission.VIEW_USER` остаётся.
- **Зависимость для GraphQL отдельная.** Автор урока переносит `get_current_user` в корень `src/` и ставит ей `auto_error=False`; у нас на существующую зависимость завязаны все защищённые REST-эндпоинты, и менять их поведение ради второго транспорта незачем.

Отличие от видео, которое экономит нам отладку: на 7:52 у автора падает `IndexError: tuple index out of range`, потому что декоратор достаёт `info` из `args[1]`. В strawberry 0.323 `info` всегда передаётся **kwarg'ом** по имени параметра (`strawberry/schema/schema_converter.py`, `_get_arguments`), поэтому берём его именованным аргументом — костыль `kwargs.get("info") or args[1]` не нужен.

## Целевая структура

```
src/api/graphql/
  decorators.py        require_authentication — общий для всех доменов
  dependencies.py      get_current_user (мягкая) + get_context
  resolvers.py         сборные Query(UserQuery), Mutation(UserMutation)
  schema.py            schema + graphql_router с context_getter
  user/
    types.py           ← api/graphql/types.py
    resolvers.py       UserQuery, UserMutation ← api/graphql/resolvers.py
    decorators.py      handle_users_errors ← api/graphql/decorators.py
```

Общий декоратор остаётся на уровне `api/graphql/`, доменный уезжает в домен — та же логика, что в `api/rest/`.

## Изменения

### 1. `src/core/user/services.py` — получение юзера по токену

Сейчас `get_current_user` в REST сам ходит в `user_manager` (`src/api/rest/user/dependencies.py:7`) — обращение к менеджеру из слоя API мимо сервиса. Второй транспорт эту строчку продублировал бы, поэтому логика уезжает в сервис, как в уроке:

```python
    @classmethod
    def get_current_user(cls, token):
        username = cls.verify_token(token, "access")
        user = user_manager.get_user(username)
        if not user:
            raise InvalidTokenError("User not found")
        return user
```

### 2. `src/api/rest/user/dependencies.py` — переход на сервис

```python
@handle_users_errors
async def get_current_user(token: str = Depends(APIKeyHeader(name="Authorization"))):
    return UserService.get_current_user(token)
```

Поведение не меняется: негодный токен по-прежнему даёт `InvalidTokenError` → 401 через `handle_users_errors`, отсутствие заголовка — 401 от `APIKeyHeader`. Импорт `user_manager` из файла уходит.

### 3. `src/api/graphql/dependencies.py` — новый файл

```python
async def get_current_user(token=Depends(APIKeyHeader(name="Authorization", auto_error=False))):
    if not token:
        return None
    try:
        return UserService.get_current_user(token)
    except InvalidTokenError:
        return None


async def get_context(current_user=Depends(get_current_user)):
    return {"current_user": current_user}
```

Зависимость мягкая: она обслуживает и публичные операции, поэтому не решает, годен ли запрос, — только сообщает, кто пришёл. Следствие, которое принимаем: истёкший и отсутствующий токен для GraphQL неотличимы, оба дают `Authentication required`.

### 4. `src/api/graphql/decorators.py` — `require_authentication`

`handle_users_errors` отсюда переезжает в `user/decorators.py` без изменений, на его место встаёт общий декоратор:

```python
def require_authentication(func):
    @wraps(func)
    async def wrapper(*args, info, **kwargs):
        if not info.context.get("current_user"):
            raise GraphQLError("Authentication required")
        return await func(*args, info=info, **kwargs)

    return wrapper
```

`info` объявлен именованным параметром — тот же приём, что у `require_permissions` в REST с `current_user`.

### 5. `src/api/graphql/user/resolvers.py` — доменные резолверы

Содержимое нынешнего `api/graphql/resolvers.py` переезжает сюда, классы переименовываются в `UserQuery` / `UserMutation`, `all_users` закрывается:

```python
@strawberry.type
class UserQuery:
    @strawberry.field
    @require_authentication
    async def all_users(self, info: strawberry.Info) -> list[User]:
        return [User(username=user.username, email=user.email) for user in UserService.get_all_users()]
```

`info: strawberry.Info` обязателен в сигнатуре — без него strawberry не передаст контекст, и декоратору нечего будет проверять. `register` и `login` не трогаем, они остаются публичными.

### 6. `src/api/graphql/resolvers.py` — сборные схемы

```python
@strawberry.type
class Query(UserQuery):
    pass


@strawberry.type
class Mutation(UserMutation):
    pass
```

Сюда позже добавятся `ProductQuery` / `ProductMutation`.

### 7. `src/api/graphql/schema.py` — контекст в роутер

```python
graphql_router = GraphQLRouter(schema, context_getter=get_context)
```

`src/main.py` не меняется.

### 8. `CLAUDE.md`

В описании `api/graphql/` снять «Аутентификации и прав в нём пока нет»: аутентификация появилась, прав по-прежнему нет.

## Verification

1. `uv run ruff format .`
2. `uv run ruff check .`
3. `uvx pyright`
4. `docker compose up -d`, логи — `docker compose logs -f web_app`
5. GraphiQL http://127.0.0.1:8010/v1/gql, сценарий урока:
   - `query { allUsers { username email } }` без заголовка → в `errors` `Authentication required`;
   - `mutation { register(...) { username email } }` без заголовка → работает, регистрация публична;
   - `mutation { login(username: "john", password: "123") { accessToken } }` → токен;
   - тот же `allUsers` с заголовком `Authorization: <accessToken>` → список пользователей;
   - `allUsers` с мусорным токеном → `Authentication required`.
6. Регрессия REST: `GET /v1/api/users` с валидным токеном админа → прежний ответ; без заголовка → 401; с мусорным токеном → 401.
