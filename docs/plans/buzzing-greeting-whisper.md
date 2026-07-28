# Пользователи из PostgreSQL: репозиторий вместо менеджера в памяти

## Context

SQLAlchemy, Alembic и ORM-модель `User` (`src/user/models.py`) уже подключены, таблица `users` создана миграцией `migrations/versions/001_create_users.py`. Но данные до сих пор живут в словаре: `UserManager` (`src/user/managers.py:6`) хранит `self.users = {}`, и `UserService` (`src/core/user/services.py:8`) работает только с ним. После перезапуска процесса все пользователи пропадают, а созданная таблица стоит пустой.

Серия видеокурса, на которой основан план, вводит паттерн **Repository** — прослойку между бизнес-логикой и источником данных. Смысл: если завтра PostgreSQL меняется на другую БД, переписываются только ORM-модель и тела методов репозитория, а набор методов (`get_by_username`, `get_all`, `add`) и весь код выше по слоям остаются прежними.

Отличия от видео, согласованные с пользователем:

1. **Раскладка по доменам.** В видео всё сворачивается в пакет `infrastructure/database/` с подпакетами `models/` и `repositories/`. У нас слой 3 уже разложен по доменам (`user/`, `product/`, `file/`), поэтому `src/user/models.py` остаётся на месте, а `managers.py` заменяется на `src/user/repositories.py`. `infrastructure/database.py` не переезжает — значит, не трогаем `migrations/env.py` и `pyproject.toml`.
2. **Сессия — зависимость FastAPI, а не модульный синглтон.** В видео `SessionLocal()` вызывается один раз на уровне модуля и одна сессия обслуживает все запросы. Это уже записано в CLAUDE.md как планируемое («Зависимости FastAPI для всего, что берётся из запроса: токен, текущий пользователь, в будущем сессия БД»), и у синглтона есть конкретная поломка: любой упавший `commit` (например, дубль по уникальному `email`, который проверка по `username` не ловит) оставляет сессию в состоянии «нужен rollback» — до перезапуска процесса ломаются все последующие запросы.
3. **Репозиторий отдаёт доменные сущности,** а не ORM-строки. Тогда `core` не начинает зависеть от SQLAlchemy в своих возвращаемых типах, а `user.get_info()` во views и `current_user.permissions` в декораторах прав продолжают работать без правок.

Объём итерации — только домен `user`. `product/managers.py` и `file/managers.py` остаются в памяти до следующей серии.

## Реализация

### 1. `src/infrastructure/database.py` — сессия на запрос

Добавить генератор рядом с `engine` и `SessionLocal`:

```python
def get_session():
    with SessionLocal() as session:
        yield session
```

Обычный генератор без импорта FastAPI — годится как зависимость и для REST, и для GraphQL, инфраструктурный слой при этом про HTTP не узнаёт.

### 2. `src/user/repositories.py` (новый) — вместо `managers.py`

`UserRepository` принимает сессию в `__init__` и держит три метода, ровно как в уроке:

```python
class UserRepository:
    def __init__(self, session):
        self.session = session

    def add(self, user: BaseUser):
        self.session.add(
            User(
                username=user.username,
                password=user.password,
                email=user.email,
                is_admin=user.is_admin,
                permissions=[Permission(permission).value for permission in user.permissions],
            )
        )
        self.session.commit()

    def get_by_username(self, username):
        row = self.session.query(User).filter(User.username == username).first()
        return self._to_entity(row) if row else None

    def get_all(self):
        return [self._to_entity(row) for row in self.session.query(User).all()]

    @staticmethod
    def _to_entity(row: User) -> BaseUser:
        if row.is_admin:
            return AdminUser(username=row.username, password=row.password, email=row.email)
        return RegularUser(
            username=row.username,
            password=row.password,
            email=row.email,
            permissions=[Permission(value) for value in row.permissions],
        )
```

`Permission` — `str`-Enum, так что в JSON-колонку кладутся строки, а на чтении собираются обратно в члены Enum: сущности остаются однородными, и `Permission.VIEW_USER in user.permissions` работает как раньше.

Файл `src/user/managers.py` удалить.

### 3. `src/core/user/services.py` — сервис поверх репозитория

- Добавить `__init__(self, repository)`, сохраняющий репозиторий в атрибут.
- Добавить фабрику, чтобы имя репозитория не утекало в слой API:

  ```python
  @classmethod
  def with_session(cls, session):
      return cls(UserRepository(session))
  ```

  Импорт `from user.repositories import UserRepository` в `core` — продолжение уже задокументированного упрощения «сервисы импортируют менеджеры напрямую».
- Методы, которым нужен репозиторий, становятся обычными (`self`): `register_user`, `get_all_users`, `get_current_user`, `authenticate_user`, `login`. Чистые криптофункции (`verify_password`, `create_token`, `verify_token`) остаются `@staticmethod` — они ни от чего не зависят и вызываются через `self.` без изменений.
- `register_user` меняет порядок: сначала `if self.repository.get_by_username(username): raise UserAlreadyExistsError(username)`, потом хеширование пароля, сборка `AdminUser`/`RegularUser` и `self.repository.add(user)`. Раньше факт дубликата возвращал `bool` из менеджера — теперь проверка явная.
- Импорт `from user.managers import user_manager` убрать.

Модульного инстанса `user_service` не создаём — сервис живёт ровно один запрос и собирается зависимостью.

Исключение `UserAlreadyExistsError` и декоратор `handle_users_errors` (из видео) в проекте уже есть — `src/core/user/exceptions.py` и `src/api/rest/user/decorators.py`, делать нечего.

### 4. `src/api/dependencies.py` (новый) — общая точка сборки

Оба транспорта строят сервис одинаково, поэтому зависимость одна на двоих (дублировать её в `api/rest/user/dependencies.py` и `api/graphql/dependencies.py` — гарантированный будущий рассинхрон):

```python
def get_user_service(session=Depends(get_session)):
    return UserService.with_session(session)
```

### 5. `src/api/rest/user/` — прокинуть сервис в обработчики

`dependencies.py`: `get_current_user` дополнительно принимает `service=Depends(get_user_service)` и вызывает `service.get_current_user(token)`.

`views.py`: каждый обработчик, который сейчас дёргает класс, получает параметр `service: UserService = Depends(get_user_service)`; `UserService.x(...)` → `service.x(...)`. Затрагивает `add_user`, `get_all_users`, `login`, `refresh_token` (`views.py:22,29,35,41`). Пример:

```python
@user_router.post("")
@handle_users_errors
async def add_user(..., service: UserService = Depends(get_user_service)):
    service.register_user(username, password, email, is_admin, permissions)
```

Декораторы `handle_users_errors` и `require_permissions` написаны через `functools.wraps` и пробрасывают `**kwargs`, поэтому FastAPI видит новый параметр и правки в них не нужны. В `get_all_users` зависимость `get_session` окажется общей для `get_current_user` и `get_user_service` — FastAPI кеширует зависимости в пределах запроса, сессия будет одна.

### 6. `src/api/graphql/` — сервис через контекст

`dependencies.py`: `get_current_user` принимает `service=Depends(get_user_service)`; `get_context` дополнительно кладёт сервис в контекст — `{"current_user": ..., "user_service": user_service}`.

`user/resolvers.py`: сервис берётся из `info.context["user_service"]`. У `all_users` параметр `info` уже есть, `register` и `login` его получают — `info: strawberry.Info` зарезервирован strawberry и в схему не попадает, публичный контракт GraphQL не меняется.

### 7. `CLAUDE.md`

Актуализировать три места, где описан слой данных:
- слой 3 — «менеджеры» для домена `user` заменились репозиторием, сессия приходит зависимостью;
- слой 4 — про «менеджеры всё ещё хранят `dict` в памяти» верно теперь только для `product` и `file`;
- в Conventions — «в будущем сессия БД» стало настоящим.

Синхронная работа с БД и bcrypt внутри `async`-обработчиков остаётся осознанным упрощением — в объём этой итерации не входит.

## Проверка

1. `docker compose up -d --build`, затем с хоста `uv run alembic upgrade head` (таблица `users` уже должна существовать, команда подтвердит).
2. `docker compose logs -f` — приложение поднялось без ошибок импорта.
3. REST через http://127.0.0.1:8010/docs:
   - `POST /v1/api/users` с `is_admin=true` → `User ... added successfully`;
   - строка видна в БД (pgAdmin на http://127.0.0.1:5050, таблица `users`): пароль захеширован, `permissions` — список строк, `created_at`/`updated_at` заполнены;
   - повторный `POST` с тем же `username` → **400** `User ... already exists` (а не 500);
   - `GET /v1/api/users/login` → пара токенов; с `Authorization` → `GET /v1/api/users` отдаёт список из БД, `GET /v1/api/users/me` — приветствие;
   - обычный пользователь без `view_user` → **403**; мусорный токен → **401**.
4. **Главная проверка ради чего всё затевалось:** `docker compose restart web_app` — после перезапуска `GET /v1/api/users` с новым токеном по-прежнему возвращает созданных пользователей.
5. Проверка, что сессия не залипает: вызвать `POST /v1/api/users` с новым `username`, но уже занятым `email` (падение на уникальном индексе), затем повторить обычную регистрацию — она должна пройти.
6. GraphQL http://127.0.0.1:8010/v1/gql: мутация `register`, затем `login`, затем `allUsers` с заголовком `Authorization` (нужен пользователь с правом `view_user`); без заголовка — `Authentication required`.
7. `uv run ruff format .` → `uv run ruff check .` → `uvx pyright`.

Тестов в проекте нет — проверка ручная.
