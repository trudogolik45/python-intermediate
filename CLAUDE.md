## Project
python-intermediate — учебное FastAPI-приложение с каталогом товаров и пользователями, на котором разбираются принципы ООП и слоистая архитектура.

## Stack
- Python 3.10, FastAPI 0.140, Pydantic v2
- Хранение: словари в памяти (`ProductManager`, `UserManager`); планируется SQLAlchemy + PostgreSQL
- Auth: JWT (python-jose, HS256) — пара access/refresh, тип токена в payload полем `type`; пароли через bcrypt. Права — `Permission` (строковый Enum), проверка зависимостью `check_permissions`
- Task queue: нет; планируется Kafka

## Architecture
Слои, сверху вниз. Каждый слой обращается только к следующему, снизу вверх обращений нет.

1. **Endpoints** (`*/views.py`) — роутеры FastAPI. Разбор запроса, зависимости (аутентификация, права), формирование ответа. Логики нет, вызывают сервис.
2. **Services** (`*/services.py`) — бизнес-логика и правила. Единственное место, где рождаются `HTTPException`: сервис переводит результат менеджера в HTTP-семантику (нет товара → 404, дубликат → 400).
3. **ORM / Data access** (`*/managers.py`) — доступ к хранилищу. Сейчас словари в памяти, менеджеры возвращают объекты или `bool`/`None`, про HTTP не знают. При переезде на SQLAlchemy сюда встанут сессия и запросы, слои выше не меняются.
4. **Database** — пока `dict` внутри менеджеров-синглтонов (`product_manager`, `user_manager`), состояние живёт до перезапуска процесса. Дальше — PostgreSQL.

Модели (`*/models.py`) и права (`users/permissions.py`) — общие для всех слоёв, зависимостей на слои у них нет.

## Structure
- `main.py` — сборка приложения, роутеры под префиксом `/v1/api`
- `products/views.py`, `users/views.py` — эндпоинты
- `products/services.py`, `users/services.py` — бизнес-логика
- `products/managers.py`, `users/managers.py` — хранилища
- `products/models.py`, `users/models.py` — модели `Product`, `BaseUser`/`AdminUser`/`RegularUser`
- `users/permissions.py` — Enum `Permission`
- `users/dependencies.py` — `get_current_user`, `check_permissions`
- `docs/plans/` — планы задач

## Commands
- Dev: `uv run fastapi dev`
- Test: тестов пока нет
- Lint: `uv run ruff check .`
- Format: `uv run ruff format .`

## Conventions
- Pydantic-модели для тел запросов и ответов
- Права на эндпоинт задаются через `dependencies=[Depends(check_permissions(Permission.X))]` — минимальный необходимый набор
- Новое право — значение в `Permission`, не строка в коде
- Обработчики async
- Зависимости FastAPI для всего, что берётся из запроса: токен, текущий пользователь, в будущем сессия БД

## Don't
- Не класть бизнес-логику в обработчики — она в сервисах
- Не поднимать `HTTPException` в менеджерах — это дело сервисов
- Не обращаться к менеджерам напрямую из эндпоинтов
- Не ловить голый `Exception` — только конкретные исключения
- Не писать `# type: ignore` без комментария с причиной
