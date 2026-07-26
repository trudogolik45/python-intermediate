# Урок 10: чистая архитектура + GraphQL в FastAPI

## Context

Разбираем урок 10 видеокурса «Python на практике» (GraphQL в FastAPI) на своей кодовой базе. Урок делится на две части: сначала бизнес-логика отделяется от инфраструктуры, потом рядом с REST поднимается второй транспорт — GraphQL.

Проблема, с которой начинает автор, у нас ровно та же: в `src/users/` и `src/products/` вперемешку лежат доменные объекты, бизнес-правила, обработчики FastAPI и хранилище. Пока API один, это терпимо; как только рядом появляется GraphQL, становится непонятно, что переиспользовать. Смысл перекладки — зафиксировать, что бизнес-правила не зависят ни от типа API, ни от БД, и что оба транспорта дёргают одно ядро.

Каркас уже начат: `src/core/`, `src/core/product/`, `src/core/user/` существуют, но все файлы в них пустые.

**Отличия от видео** (кодовая база другая):

- Пакетный менеджер — **uv**, не poetry. Пакеты ставятся в venv editable-режимом через hatchling, список — `packages` в `[tool.hatch.build.targets.wheel]` (`pyproject.toml:20`).
- Python уже 3.10, а `strawberry-graphql` 0.323 требует `>=3.10,<4.0`. Пересоздавать venv и править `requires-python` не нужно — в видео это делалось только ради версии.
- Имена доменов приводим к единственному числу **везде**, включая переименование `src/products/` → `src/product/` и `src/users/` → `src/user/`. В видео единственное число только под `core`, из-за чего остаётся разнобой.
- `BaseUser.get_info()` оставляем. Автор выкинул из сущности `get_user_info` как «действие, а не объект», но у нас на этот метод завязан `UserManager.get_all_users()` и ответ `GET /users`; выпиливание тянет за собой правки, к теме урока не относящиеся.

Решения, согласованные с пользователем:

- единственное число в именах доменов везде;
- `Product` переезжает в core как есть, Pydantic-моделью — core получает зависимость от Pydantic, это осознанный компромисс в пользу простоты;
- менеджеры остаются на месте (в переименованных `src/product/`, `src/user/`), отдельный слой БД пока не выделяем;
- GraphQL — как в видео: одна query поверх захардкоженного словаря, без выхода на сервисы.

## Целевая структура

```
src/
  main.py
  core/                      бизнес-правила, про HTTP и БД не знают
    permissions.py           ← users/permissions.py   (общее для обоих доменов)
    product/
      entities.py            ← products/models.py
      exceptions.py          ← products/exceptions.py
      services.py            ← products/services.py
    user/
      entities.py            ← users/models.py
      exceptions.py          ← users/exceptions.py
      services.py            ← users/services.py
  api/                       транспорт
    rest/
      product/
        decorators.py        ← products/decorators.py
        views.py             ← products/views.py
      user/
        decorators.py        ← users/decorators.py
        dependencies.py      ← users/dependencies.py
        views.py             ← users/views.py
    graphql/                 новое
      types.py
      resolvers.py
      schema.py
  product/
    managers.py              ← products/managers.py
  user/
    managers.py              ← users/managers.py
```

Каждой новой директории нужен `__init__.py`: `src` пакетом не является, а всё внутри — является (см. `src/core/__init__.py`).

## Реализация

### 1. Перенос файлов

Файлы отслеживаются git — двигать через `git mv`, чтобы не потерять историю. Пустые заготовки в `src/core/product/` и `src/core/user/` перезаписываются переносимыми файлами.

Переименования `src/products/` → `src/product/` и `src/users/` → `src/user/` делать до переноса остального — иначе на macOS легко получить путаницу с полупустыми директориями.

Содержимое файлов не меняется, кроме импортов (следующий шаг) — это чистая перекладка.

### 2. Правка импортов

Все внутренние импорты переписываются по таблице выше. Характерные примеры:

`src/core/user/entities.py`
```python
from core.permissions import Permission
```

`src/core/user/services.py`
```python
from core.user.entities import AdminUser, RegularUser
from core.user.exceptions import InvalidCredentialsError, InvalidTokenError, UserAlreadyExistsError
from user.managers import user_manager
```

`src/api/rest/product/views.py`
```python
from api.rest.product.decorators import handle_products_errors
from api.rest.user.decorators import require_permissions
from api.rest.user.dependencies import get_current_user
from core.permissions import Permission
from core.product.entities import Product
from core.product.services import ProductService
```

`src/user/managers.py`
```python
from core.user.entities import BaseUser
```

Остальные файлы (`core/product/services.py`, `api/rest/user/{decorators,dependencies,views}.py`, `api/rest/product/decorators.py`) правятся по тому же принципу.

**Известное нарушение слоёв, оставляем как есть:** `core/*/services.py` импортирует менеджеры из `product`/`user`, то есть ядро зависит от инфраструктуры. В строгой чистой архитектуре зависимость должна быть развёрнута (протокол репозитория в core, реализация снаружи). Автор видео это откладывает — «чуть попозже поработаем и над этим уровнем». Здесь тоже откладываем: соответствует текущему описанию слоёв в `CLAUDE.md` (сервисы → менеджеры).

Туда же: `core/user/services.py` тянет bcrypt, jose и держит `SECRET_KEY` — тоже инфраструктура в ядре. Вне объёма урока.

### 3. `pyproject.toml`

```toml
dependencies = [
    ...
    "strawberry-graphql[fastapi]>=0.323.2",
]

[tool.hatch.build.targets.wheel]
packages = ["src/api", "src/core", "src/product", "src/user"]
```

`packages` обновить обязательно и до синка: если там останется несуществующий `src/products`, сборка пакета упадёт.

Установка: `uv add 'strawberry-graphql[fastapi]'` — обновит `dependencies`, `uv.lock` и venv одной командой. Кавычки нужны, иначе zsh съест квадратные скобки.

### 4. GraphQL

`src/api/graphql/types.py`
```python
import strawberry


@strawberry.type
class User:
    id: int
    username: str
    email: str
```

`src/api/graphql/resolvers.py` — фейковое хранилище, как в видео: реальные пользователи живут в `user_manager` и заводятся через REST, ядро мы здесь сознательно не трогаем.
```python
import strawberry

from api.graphql.types import User

USERS = {
    1: User(id=1, username="john", email="john@example.com"),
    2: User(id=2, username="jane", email="jane@example.com"),
}


@strawberry.type
class Query:
    @strawberry.field
    def user(self, id: int) -> User:
        user = USERS.get(id)
        if not user:
            raise ValueError(f"User {id} not found")
        return user
```

`src/api/graphql/schema.py`
```python
import strawberry
from strawberry.fastapi import GraphQLRouter

from api.graphql.resolvers import Query

schema = strawberry.Schema(query=Query)
graphql_router = GraphQLRouter(schema)
```

Mutation в схему пока не добавляем — в видео её тоже только упоминают.

Если pyright ругнётся на непараметризованный дженерик `GraphQLRouter`, аннотировать явно: `graphql_router: GraphQLRouter = GraphQLRouter(schema)`.

### 5. `src/main.py`

```python
from fastapi import APIRouter, FastAPI

from api.graphql.schema import graphql_router
from api.rest.product.views import products_router
from api.rest.user.views import user_router

app = FastAPI()

api_v1_router = APIRouter(prefix="/v1/api")
api_v1_router.include_router(products_router)
api_v1_router.include_router(user_router)

app.include_router(api_v1_router)
app.include_router(graphql_router, prefix="/v1/gql")
```

REST остаётся на `/v1/api`, GraphQL встаёт рядом на `/v1/gql` — два транспорта поверх одного ядра, ради чего вся перекладка и делалась.

### 6. `CLAUDE.md`

Раздел **Architecture** описывает старую раскладку (`*/views.py`, `*/services.py`, `*/managers.py`) — переписать под `core` / `api` / менеджеры и упомянуть второй транспорт. В **Stack** добавить strawberry.

## Verification

1. `uv run ruff format .`
2. `uv run ruff check .`
3. `uvx pyright`
4. `docker compose up -d --build` — пересборка обязательна: зависимости вшиты в образ, монтирования `./src` тут не хватит.

Дымовой прогон на http://127.0.0.1:8010:

- `/docs` открывается, эндпоинты products и users на месте;
- завести пользователя (`POST /v1/api/users` с `is_admin=true`), залогиниться (`GET /v1/api/users/login`), дёрнуть `GET /v1/api/users/me` с токеном в заголовке `Authorization`, создать товар — REST работает как до перекладки;
- `/v1/gql` отдаёт GraphiQL. Проверить в нём, открыв консоль разработчика (в видео этот момент — главный):
  - `{ user(id: 1) { username email } }` → оба поля;
  - `{ user(id: 1) { email } }` → только email, тело ответа меньше — форму ответа задаёт клиент, а запрос всегда POST на один URL;
  - `{ user(id: 3) { email } }` → HTTP 200, а ошибка внутри тела в поле `errors`; отличие от REST, где это был бы 404.
