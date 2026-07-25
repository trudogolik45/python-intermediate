# Авторизация эндпоинтов продуктов по правам пользователя

## Context

Аутентификация уже сделана: `/users/login` выдаёт пару JWT, `get_current_user` (`users/dependencies.py:8`) достаёт пользователя из заголовка `Authorization`. Но эндпоинты в `products/views.py` открыты полностью — токен там не спрашивается вообще, а поле `permissions` у пользователя (`users/models.py`) существует, но ни на что не влияет.

Текущий спринт в README: доступ к операциям над товарами определяется правами пользователя. Список прав сейчас — обычный список строк `PERMISSIONS` в `users/models.py:1`, из-за чего опечатка в праве нигде не ловится. Заменяем его на Enum и вводим зависимость, которая проверяет наличие нужного права у текущего пользователя.

Решения, согласованные с пользователем:
- модуль прав — `users/permissions.py`;
- `is_admin` не даёт обхода проверки: у `AdminUser` и так полный набор прав, проверка одна для всех;
- `get_current_user` отдаёт 401, если токен валиден, а пользователя нет в `user_manager`.

## Реализация

### 1. `users/permissions.py` (новый файл)

```python
from enum import Enum


class Permission(str, Enum):
    VIEW_PRODUCT = "view_product"
    ADD_PRODUCT = "add_product"
    UPDATE_PRODUCT = "update_product"
    DELETE_PRODUCT = "delete_product"
```

Наследование от `str` обязательно: значения приходят из query-параметров и уходят в JSON `get_info()`, а сравнение `Permission.VIEW_PRODUCT == "view_product"` должно работать.

### 2. `users/models.py`

- Удалить константу `PERMISSIONS`.
- `AdminUser` передаёт в `super().__init__` `permissions=list(Permission)`.
- `RegularUser`: нормализовать `permissions or []` — в `/users` параметр опциональный, и `None` иначе развалит проверку вхождения.

### 3. `users/views.py`

В `add_user` заменить `Optional[List[str]]` с ручными `examples`/`enum` на `Optional[List[Permission]] = Query(default=None, title="Permissions")` — FastAPI сам соберёт список допустимых значений в OpenAPI. Импорт `PERMISSIONS` из `users.models` убрать.

### 4. `users/dependencies.py`

- В `get_current_user` после `user_manager.users.get(username)`: если пользователя нет — `HTTPException(401, "User not found")`.
- Добавить фабрику зависимости:

```python
def check_permissions(*required: Permission):
    def dependency(current_user=Depends(get_current_user)):
        if not all(permission in current_user.permissions for permission in required):
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return current_user

    return dependency
```

Возвращает пользователя, чтобы эндпоинт при желании мог его использовать.

### 5. `products/views.py`

Минимальный набор прав на операцию, через `dependencies=[...]` в декораторе (пользователь в теле обработчиков не нужен):

| Эндпоинт | Право |
|---|---|
| `POST /products` | `Permission.ADD_PRODUCT` |
| `GET /products/{product_id}` | `Permission.VIEW_PRODUCT` |
| `PUT /products/{product_id}` | `Permission.UPDATE_PRODUCT` |
| `DELETE /products/{product_id}` | `Permission.DELETE_PRODUCT` |

Пример:

```python
@products_router.post("", dependencies=[Depends(check_permissions(Permission.ADD_PRODUCT))])
async def create_product(product: Product): ...
```

### 6. README

Обновить раздел «Структура» (добавить `users/permissions.py`), описать проверку прав в задачах и перенести пункт из «Текущего спринта» в выполненные.

## Проверка

1. `uv run fastapi dev`, дальше через `/docs` или curl:
2. Создать админа: `POST /v1/api/users?username=admin&password=1&email=a@a.a&is_admin=true`.
3. Создать обычного пользователя только с правом просмотра: `POST /v1/api/users?...&is_admin=false&permissions=view_product`.
4. `GET /v1/api/users` — убедиться, что у админа четыре права, у обычного одно.
5. Получить токены обоих через `GET /v1/api/users/login`.
6. С токеном админа в заголовке `Authorization`: `POST/GET/PUT/DELETE /v1/api/products` — все проходят.
7. С токеном обычного: `GET /v1/api/products/{id}` — 200; `POST`, `PUT`, `DELETE` — 403 `Not enough permissions`.
8. Без заголовка — 403 от `APIKeyHeader`; с мусорным токеном — 401.
9. `uv run ruff check .` и `uv run ruff format --check .`.

Тестов в проекте нет — проверка ручная.
