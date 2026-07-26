# python-intermediate

Учебный проект на FastAPI, который я писал, чтобы разобрать четыре принципа ООП на живом коде, а не на абстрактных примерах. Данные хранятся в памяти — база намеренно не подключена, вся суть в устройстве классов и в том, как менеджеры прокидываются в эндпоинты.

## Задачи

### 1. Управление товарами

Класс `ProductManager` с методами добавления, получения, обновления и удаления товаров плюс один protected-метод `_is_product_exists`, который проверяет, есть ли продукт в хранилище. На каждый метод менеджера заведён свой эндпоинт.

### 2. Пользователи и наследование

Базовый класс `BaseUser` с общими атрибутами (`username`, `email`, `is_admin`, `permissions`). От него унаследованы:

- `AdminUser` — всегда `is_admin=True` и полный набор разрешений;
- `RegularUser` — всегда `is_admin=False`, разрешения передаются списком значений `Permission`.

Метод `get_info` объявлен в `BaseUser` и отдаёт описание пользователя. `UserManager` добавляет пользователей и возвращает список их описаний.

### 3. Аутентификация по JWT

`UserService` собирает работу с учётными данными: пароль хешируется через bcrypt при регистрации и проверяется при логине, а `/users/login` выдаёт пару токенов. Access живёт минуту, refresh — десять; тип записан в payload полем `type`, поэтому refresh не пройдёт туда, где нужен access, и наоборот. Обменять refresh на новый access можно через `/users/refresh`. Защищённые эндпоинты получают пользователя зависимостью `get_current_user`, которая читает токен из заголовка `Authorization`.

### 4. Авторизация по правам

Разрешения собраны в `Permission` — строковый Enum, поэтому опечатка в праве ловится на входе, а не молча превращается в отказ доступа. Каждому эндпоинту товаров задан минимальный набор прав декоратором `require_permissions`: просмотру нужен `view_product`, созданию — `add_product`, обновлению — `update_product`, удалению — `delete_product`; списку пользователей — `view_user`. Декоратор берёт пользователя из параметра `current_user`, который приходит зависимостью `get_current_user`, и сверяет требуемые права с его `permissions`; не хватает хотя бы одного — 403. Отдельной ветки для администратора нет: `AdminUser` создаётся с полным набором прав и проходит ту же проверку, что и все.

### 5. Исключения и декораторы

Сервисы не знают про HTTP: `ProductService` поднимает `ProductNotFoundError` и `ProductAlreadyExistsError`, `UserService` — `UserAlreadyExistsError`, `InvalidCredentialsError` и `InvalidTokenError`. В коды ответа их переводят декораторы `handle_products_errors` и `handle_users_errors` на эндпоинтах, так что try/except не расползается по обработчикам. Декораторы обёрнуты `functools.wraps`, поэтому FastAPI по цепочке `__wrapped__` видит настоящую сигнатуру обработчика и собирает схему как обычно.

## Концепции

**Инкапсуляция.** Атрибуты `BaseUser` инициализируются через `__init__`, наружу отдаётся только `get_info()` — внутреннее устройство объекта не торчит в эндпоинтах. Так же и с `UserManager`: словарь `self.users` меняется через `add_user`, а читается через `get_user` и `get_all_users`. В обоих менеджерах проверка существования вынесена в protected `_is_product_exists` и `_is_user_exists`, наружу эти методы не предназначены.

**Наследование.** `AdminUser` и `RegularUser` берут от `BaseUser` конструктор и `get_info`, а сами задают только то, чем отличаются — флаг `is_admin` и правила выдачи разрешений. Общий код не дублируется.

**Полиморфизм.** `get_all_users` вызывает `get_info()` у каждого объекта, не проверяя его тип: администратор и обычный пользователь обрабатываются одинаково.

**Абстракция.** `BaseUser` собирает то, что верно для любого пользователя, а подклассы доопределяют роль. Из-за этого при добавлении нового типа пользователя менять `UserManager` и эндпоинты не придётся.

## Структура

```
src/main.py                — сборка приложения, роутеры под префиксом /v1/api
src/products/models.py     — модель Product
src/products/managers.py   — ProductManager: хранилище товаров
src/products/services.py   — ProductService: логика операций над товарами
src/products/exceptions.py — исключения товаров: не найден, уже существует
src/products/decorators.py — handle_products_errors: перевод исключений товаров в HTTP-ответы
src/products/views.py      — эндпоинты товаров
src/users/models.py        — BaseUser, AdminUser, RegularUser
src/users/permissions.py   — Permission: перечисление прав
src/users/managers.py      — UserManager: хранилище пользователей
src/users/services.py      — UserService: регистрация, хеширование пароля, выпуск и проверка JWT
src/users/exceptions.py    — исключения пользователей: дубликат, неверные учётные данные, негодный токен
src/users/decorators.py    — handle_users_errors и require_permissions
src/users/dependencies.py  — get_current_user
src/users/views.py         — эндпоинты пользователей
```

## Эндпоинты

| Метод | Путь | Что делает | Требует права |
|---|---|---|---|
| POST | `/v1/api/products` | добавить товар | `add_product` |
| GET | `/v1/api/products/{product_id}` | получить товар | `view_product` |
| PUT | `/v1/api/products/{product_id}` | обновить товар | `update_product` |
| DELETE | `/v1/api/products/{product_id}` | удалить товар | `delete_product` |
| POST | `/v1/api/users` | добавить пользователя | — |
| GET | `/v1/api/users` | список пользователей | `view_user` |
| GET | `/v1/api/users/login` | получить пару access- и refresh-токенов | — |
| GET | `/v1/api/users/refresh` | обменять refresh-токен на новый access | — |
| GET | `/v1/api/users/me` | текущий пользователь по токену | только токен |

## Запуск
- `uv run fastapi dev`
