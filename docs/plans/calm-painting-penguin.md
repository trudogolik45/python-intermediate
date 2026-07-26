# Урок 13: пагинация в GraphQL

## Context

`allUsers` отдаёт всех пользователей одним списком (`src/api/graphql/user/resolvers.py:13`). Пока юзеров десяток — не проблема, но это единственный запрос-коллекция в схеме, и на нём разбирается offset/limit-пагинация: клиент передаёт, сколько элементов взять и сколько пропустить, а сервер отвечает страницей плюс общим количеством. Такой ответ одинаково закрывает и постраничную навигацию, и infinite scroll на фронте.

Урок делает три вещи: заводит тип страницы (`items`, `total`, `offset`, `limit`), выносит нарезку в переиспользуемый код и подключает всё к `allUsers`. Итог в схеме — `allUsers(limit: Int! = 10, offset: Int! = 0): UserPage!`.

Решения, согласованные с пользователем:

- **Хелпер-функция, а не декоратор.** В видео пагинация — декоратор `@paginate` над резолвером. У нас так не выходит без `# type: ignore`: strawberry берёт тип поля из аннотации самого резолвера (`Signature.from_callable(..., follow_wrapped=True)` в `strawberry/types/fields/resolver.py:242`, `@wraps` протаскивает аннотацию оригинала). Значит резолвер обязан быть объявлен как `-> Page[User]`, а тело под декоратором возвращает список — pyright это завернёт. Обойти можно только подменой `wrapper.__signature__`, что дороже пользы. Вызов хелпера из резолвера типизируется честно и читается проще.
- **Срез в API-слое, как в уроке.** `UserService.get_all_users()` по-прежнему отдаёт всё, core про пагинацию не знает. При переезде на SQLAlchemy `limit`/`offset` придётся спустить в сервис и менеджер, чтобы получился настоящий `LIMIT/OFFSET` — это отдельная задача.
- **Значения клампятся.** В видео проверок нет, и `offset=-5` тихо даёт `items[-5:5]` — неверную страницу вместо ошибки. Зажимаем `offset` снизу нулём, `limit` — в диапазон 1..100.

`Page` делается дженериком: strawberry сам назовёт `Page[User]` как `UserPage` в схеме (`name_converter.from_generic` склеивает имена аргументов с именем типа), так что имя совпадёт с уроком, а для будущего GraphQL-домена товаров ничего дописывать не придётся.

## Изменения

### 1. `src/api/graphql/pagination.py` — новый файл

Кросс-доменный код живёт в корне `api/graphql/` (как `decorators.py` и `dependencies.py`), доменный — в `api/graphql/user/`. Тип страницы и нарезка нужны обоим доменам, поэтому файл общий.

```python
from typing import Generic, TypeVar

import strawberry

DEFAULT_LIMIT = 10
MAX_LIMIT = 100

T = TypeVar("T")


@strawberry.type
class Page(Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


def paginate(items: list[T], limit: int, offset: int) -> Page[T]:
    limit = min(max(limit, 1), MAX_LIMIT)
    offset = max(offset, 0)
    return Page(items=items[offset : offset + limit], total=len(items), limit=limit, offset=offset)
```

`total` считается по полному списку — это общее количество, а не размер страницы. В ответ кладутся уже зажатые `limit`/`offset`, чтобы клиент видел, что реально применилось.

Python 3.10 — синтаксис дженериков из PEP 695 недоступен, нужен явный `TypeVar` и `Generic[T]`.

### 2. `src/api/graphql/user/resolvers.py` — подключение к `allUsers`

```python
@strawberry.field
@require_authentication
async def all_users(self, info: strawberry.Info, limit: int = DEFAULT_LIMIT, offset: int = 0) -> Page[User]:
    users = [User(username=user.username, email=user.email) for user in UserService.get_all_users()]
    return paginate(users, limit, offset)
```

Порядок декораторов прежний: `strawberry.field` снаружи, `require_authentication` под ним. Его wrapper пробрасывает `*args, **kwargs`, так что `limit`/`offset` доедут до резолвера без правок в `src/api/graphql/decorators.py`.

Дефолты объявлены в сигнатуре резолвера — strawberry прочитает их через `inspect.signature` и выставит в схеме как `limit: Int! = 10, offset: Int! = 0`. Дублировать их в `paginate` не нужно: функция получает уже готовые значения.

`schema.py` и сборный `resolvers.py` не трогаем — тип поля меняется, состав `Query` нет.

## Чего этот урок не делает

`GET /v1/api/users` (`src/api/rest/user/views.py:29`) остаётся без пагинации — расхождение транспортов, такое же как с `Permission.VIEW_USER`, который в GraphQL не проверяется.

## Verification

1. `uv run ruff format .`
2. `uv run ruff check .`
3. `uvx pyright`
4. `docker compose up -d --build`, дальше GraphiQL на http://127.0.0.1:8010/v1/gql

Тестов в проекте нет, проверка ручная. Зарегистрировать заведомо больше десяти юзеров:

```graphql
mutation { register(username: "john1", password: "pass", email: "john1@mail.com") { username } }
```

Залогиниться и положить `accessToken` в заголовки GraphiQL — `get_current_user` ждёт голый токен без префикса `Bearer`:

```json
{ "Authorization": "<accessToken>" }
```

Прогнать запрос с разными аргументами:

```graphql
query { allUsers(limit: 10, offset: 10) { items { username email } total limit offset } }
```

Что должно получиться при 20 зарегистрированных:

| Аргументы | Ожидание |
|---|---|
| `limit: 10, offset: 0` | юзеры 1–10, `total: 20` |
| `limit: 10, offset: 10` | юзеры 11–20, `total: 20` |
| `limit: 1, offset: 5` | один юзер, шестой по счёту |
| аргументы не переданы | первые 10, дефолты из схемы |
| `offset: -5` | то же, что `offset: 0`; в ответе `offset: 0` |
| `limit: 1000` | 100 элементов, в ответе `limit: 100` |
| `offset: 999` | `items: []`, `total: 20` |

Заодно убедиться, что схема в GraphiQL показывает тип `UserPage`, а не `PageUser` или `Page`.
