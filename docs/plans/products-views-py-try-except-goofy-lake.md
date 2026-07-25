# Доменные исключения и декораторы вместо HTTP-логики в сервисах

## Context

Сейчас HTTP-семантика размазана по слою бизнес-логики: `products/services.py` поднимает `HTTPException(400/404)`, `users/services.py` — `HTTPException(400/401)`. Сервис знает про протокол, хотя это дело эндпоинта: тот же `ProductService.get_product` из консольной команды или из воркера Kafka не должен кидать HTTP-ошибку.

Разносим ответственность:
- сервисы поднимают свои исключения из `*/exceptions.py`;
- слой эндпоинтов (`*/views.py`, `*/decorators.py`, `users/dependencies.py`) переводит их в HTTP через декораторы `handle_products_errors` / `handle_users_errors` — вместо try/except в каждом обработчике;
- проверка прав переезжает с зависимости `check_permissions` на декоратор `require_permissions` в `users/decorators.py` и применяется в обоих модулях views.

Решения, согласованные с пользователем:
- декоратор прав применяется и в `products/views.py` (взамен `dependencies=[Depends(check_permissions(...))]`), и в `users/views.py` — `GET /users` закрывается новым правом `VIEW_USER`, регистрация остаётся открытой (иначе первого админа некому создать);
- текущий пользователь приходит в декоратор через объявленный в обработчике параметр `current_user=Depends(get_current_user)` — без правки сигнатур через `inspect`;
- `users` получает такой же набор (`exceptions.py` + `handle_users_errors`), чтобы правило было одно на весь проект.

Ключевой момент, на котором всё держится: `functools.wraps` проставляет `__wrapped__`, а `inspect.signature` (его и зовёт FastAPI в `get_typed_signature`) разворачивает цепочку до исходной функции. Поэтому FastAPI видит настоящие параметры обработчика, а не `*args, **kwargs` обёртки. Декораторы обязаны быть под декоратором роутера и обязаны использовать `@wraps`.

## Реализация

### 1. `products/exceptions.py` (новый)

```python
class ProductError(Exception):
    pass


class ProductNotFoundError(ProductError):
    def __init__(self, product_id):
        super().__init__(f"Product {product_id} not found")


class ProductAlreadyExistsError(ProductError):
    def __init__(self, product_id):
        super().__init__(f"Product {product_id} already exists")
```

Сообщение живёт в исключении, декоратор отдаёт его в `detail` — тексты не дублируются по коду.

### 2. `products/decorators.py` (новый)

```python
from functools import wraps

from fastapi import HTTPException, status

from products.exceptions import ProductAlreadyExistsError, ProductNotFoundError


def handle_products_errors(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ProductNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except ProductAlreadyExistsError as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    return wrapper
```

### 3. `products/services.py`

`HTTPException` убрать целиком, вместо него доменные исключения:

- `create_product` → `raise ProductAlreadyExistsError(product.id)`;
- `get_product` / `update_product` / `delete_product` → `raise ProductNotFoundError(product_id)`.

Импорт `fastapi` из файла уходит — сервис перестаёт знать про HTTP.

### 4. `users/exceptions.py` (новый)

```python
class UserError(Exception):
    pass


class UserAlreadyExistsError(UserError):
    def __init__(self, username):
        super().__init__(f"User {username} already exists")


class InvalidCredentialsError(UserError):
    def __init__(self):
        super().__init__("Invalid username or password")


class InvalidTokenError(UserError):
    def __init__(self, message="Invalid or expired token"):
        super().__init__(message)
```

Отдельного `UserNotFoundError` нет: в `get_current_user` пропавший пользователь при валидном токене — это тоже негодный токен, `InvalidTokenError("User not found")` сохраняет текущий текст ответа.

### 5. `users/decorators.py` (новый)

Два декоратора.

```python
def handle_users_errors(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except UserAlreadyExistsError as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
        except (InvalidCredentialsError, InvalidTokenError) as error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error

    return wrapper


def require_permissions(*required: Permission):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user, **kwargs):
            if not all(permission in current_user.permissions for permission in required):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
            return await func(*args, current_user=current_user, **kwargs)

        return wrapper

    return decorator
```

`require_permissions` поднимает `HTTPException` напрямую — он уже часть слоя эндпоинтов, доменного исключения здесь нет.

Импорт `Permission` в `users/decorators.py` из `users.permissions`; на `users.services` файл не завязан — циклов не будет.

### 6. `users/services.py`

- `register_user` → `UserAlreadyExistsError(username)`;
- `login` → `InvalidCredentialsError()`;
- `verify_token` → `InvalidTokenError()` в обеих ветках (проверка payload и `except JWTError`), причём `raise InvalidTokenError() from error` в блоке `except JWTError`;
- импорты `HTTPException`, `status` убрать.

### 7. `users/dependencies.py`

- `check_permissions` удалить — его роль забирает `require_permissions`;
- `get_current_user` сделать `async def` и обернуть `@handle_users_errors`: тогда `InvalidTokenError` из `verify_token` и отсутствие пользователя в `user_manager` превращаются в 401 тем же декоратором.

```python
@handle_users_errors
async def get_current_user(token: str = Depends(APIKeyHeader(name="Authorization"))):
    username = UserService.verify_token(token, "access")
    user = user_manager.get_user(username)
    if not user:
        raise InvalidTokenError("User not found")
    return user
```

Зависимости FastAPI разбирает той же `get_typed_signature`, поэтому обёртка над зависимостью работает так же, как над обработчиком.

### 8. `users/permissions.py`

Добавить `VIEW_USER = "view_user"`. `AdminUser` строится с `permissions=list(Permission)`, так что админ получает право автоматически, а обычному пользователю его надо явно запросить при регистрации.

### 9. `products/views.py`

`dependencies=[...]` из декораторов роутера убрать, `check_permissions` не импортировать. Каждый обработчик — три декоратора сверху вниз: роутер, права, обработка ошибок; и параметр `current_user`.

```python
@products_router.post("")
@require_permissions(Permission.ADD_PRODUCT)
@handle_products_errors
async def create_product(product: Product, current_user=Depends(get_current_user)):
    ProductService.create_product(product)
    return {"result": f"Product created: {product.name}"}
```

Так же для `GET` (`VIEW_PRODUCT`), `PUT` (`UPDATE_PRODUCT`), `DELETE` (`DELETE_PRODUCT`).

### 10. `users/views.py`

| Эндпоинт | Декораторы |
|---|---|
| `POST /users` | `@handle_users_errors` |
| `GET /users` | `@require_permissions(Permission.VIEW_USER)` + `current_user=Depends(get_current_user)` |
| `GET /users/login` | `@handle_users_errors` |
| `GET /users/refresh` | `@handle_users_errors` |
| `GET /users/me` | без изменений (401 отдаёт сам `get_current_user`) |

### 11. Документация

- `README.md`: в «Структуру» добавить четыре новых файла и поправить описание `products/services.py` (логика операций, без HTTP-ошибок) и `users/dependencies.py` (только `get_current_user`); в разделе 4 заменить `check_permissions` на декоратор `require_permissions`; в таблице эндпоинтов у `GET /v1/api/users` проставить право `view_user`; коротко описать перевод доменных исключений в HTTP декораторами.
- `CLAUDE.md`: в слое 2 (Services) — сервисы поднимают исключения из `*/exceptions.py`, `HTTPException` рождается в слое эндпоинтов (`views.py`, `decorators.py`, `dependencies.py`); в Structure добавить новые файлы; в Conventions заменить правило про `dependencies=[Depends(check_permissions(...))]` на `@require_permissions(...)` с обязательным `current_user=Depends(get_current_user)`; в Don't заменить «не поднимать HTTPException в менеджерах» на «не поднимать HTTPException в сервисах и менеджерах».

## Проверка

Тестов в проекте нет — проверка ручная, `uv run fastapi dev` и `/docs` либо curl.

1. `GET /docs` открывается, у эндпоинтов товаров в схеме остались их параметры (`product`, `product_id`) — значит `@wraps` отработал и FastAPI не увидел `*args/**kwargs`.
2. Создать админа: `POST /v1/api/users?username=admin&password=1&email=a@a.a&is_admin=true`; повторный тот же запрос — 400 `User admin already exists`.
3. Создать обычного пользователя с `is_admin=false&permissions=view_product`.
4. `GET /v1/api/users` без токена — 403 от `APIKeyHeader`; с токеном обычного — 403 `Not enough permissions`; с токеном админа — список.
5. `GET /v1/api/users/login` с неверным паролем — 401 `Invalid username or password`.
6. Токен админа: `POST /v1/api/products` → 200, повтор с тем же `id` → 400 `Product 1 already exists`; `GET /v1/api/products/999` → 404 `Product 999 not found`; `PUT`/`DELETE` несуществующего → 404.
7. Токен обычного: `GET /v1/api/products/{id}` → 200, `POST`/`PUT`/`DELETE` → 403.
8. Мусорный токен → 401 `Invalid or expired token`; подождать больше минуты и повторить с истёкшим access → тоже 401; `GET /v1/api/users/refresh` с refresh-токеном выдаёт новый access, с access-токеном → 401.
9. `uv run ruff check .` и `uv run ruff format --check .`.
