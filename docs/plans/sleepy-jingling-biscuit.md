# Unit of Work для работы с БД

## Context

Урок 17 видеокурса («Паттерн: Unit of Work в FastAPI») вводит границу транзакции на уровне приложения. Сейчас в проекте её нет: `UserRepository.add` (`src/user/repositories.py:20`) коммитит сам, сразу после `session.add`. Пока запись одна — это работает, но как только сервис начнёт менять несколько объектов за вызов, частичный результат останется в базе: первая запись закоммичена, вторая упала.

Задача — перенести ответственность за `commit`/`rollback` из репозитория в отдельный объект `UnitOfWork`, которым распоряжается сервис. Репозиторий после этого только формирует запросы, транзакцией управляет тот слой, который знает бизнес-операцию целиком.

Три отличия от урока, согласованные заранее:

1. **UoW не создаёт сессию.** В уроке `unit_of_work()` вызывает `SessionLocal()` внутри себя, из-за чего понадобилась фабрика репозитория. В проекте сессия уже приходит зависимостью `get_session` (`src/infrastructure/database.py:14`) и на ней же собирается сервис (`src/api/dependencies.py:7`). `UnitOfWork` принимает готовую сессию — фабрика не нужна, на запрос по-прежнему одна сессия, конвенция «зависимости FastAPI для всего, что берётся из запроса» не нарушается.
2. **Не ловим голый `Exception`.** В `UnitOfWorkError` конвертируются только `SQLAlchemyError`; доменные исключения (`UserAlreadyExistsError`) проходят наружу как есть, иначе 400 превратился бы в 500.
3. **`ServiceError` → 500, а не 400.** Дубли сервис проверяет явно и отдаёт 400 сам; падение транзакции — это гонка или сбой БД, то есть не вина клиента.

Демонстрационный сценарий с двумя записями из урока не переносим — вводим только границу транзакции.

## Реализация

### 1. `src/infrastructure/exceptions.py` (новый)

```python
class InfrastructureError(Exception):
    pass


class UnitOfWorkError(InfrastructureError):
    def __init__(self, message="Transaction failed"):
        super().__init__(message)
```

Базовый класс + конкретный — по образцу `core/user/exceptions.py`.

### 2. `src/infrastructure/unit_of_work.py` (новый)

`database.py` оставляем про подключение, UoW кладём отдельно.

```python
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from infrastructure.exceptions import UnitOfWorkError


class UnitOfWork:
    def __init__(self, session: Session):
        self.session = session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is None:
            self.commit()
            return False
        self.session.rollback()
        if issubclass(exc_type, SQLAlchemyError):
            raise UnitOfWorkError() from exc
        return False

    def commit(self):
        try:
            self.session.commit()
        except SQLAlchemyError as error:
            self.session.rollback()
            raise UnitOfWorkError() from error
```

Ключевые моменты:

- `__enter__`/`__exit__` вместо `@contextmanager` из урока: UoW должен быть объектом, который сервис получает в `__init__` и в который можно входить повторно (после `commit` сессия пригодна для новой транзакции).
- `close` не нужен — сессией владеет `get_session`, он же её закрывает через `with SessionLocal()`.
- Ошибка внутри блока (`flush`) и ошибка на самом `commit` обе дают `UnitOfWorkError`; SQLAlchemy наружу не утекает.
- `raise ... from exc` в `__exit__` заменяет исходное исключение, сохраняя его в `__cause__`.

### 3. `src/core/exceptions.py` (новый)

Общий для доменов, рядом с `core/permissions.py` — когда `product` переедет в БД, он понадобится и там.

```python
class ServiceError(Exception):
    def __init__(self, message="Operation failed"):
        super().__init__(message)
```

### 4. `src/user/repositories.py`

Убрать `self.session.commit()` из `add` (строка 20). Больше ничего.

### 5. `src/core/user/services.py`

- `__init__(self, repository: UserRepository, uow: UnitOfWork)`.
- `with_session` собирает оба на одной сессии:
  ```python
  @classmethod
  def with_session(cls, session):
      return cls(UserRepository(session), UnitOfWork(session))
  ```
- `register_user`: хеширование пароля **до** входа в контекст (bcrypt держит транзакцию открытой ~100 мс, если хешировать внутри), в контексте — проверки дублей и запись:
  ```python
  def register_user(self, username, password, email, is_admin, permissions):
      hashed_password = bcrypt.hashpw(...)
      user = AdminUser(...) if is_admin else RegularUser(...)
      try:
          with self.uow:
              if self.repository.get_by_username(username):
                  raise UserAlreadyExistsError(username)
              if self.repository.get_by_email(email):
                  raise UserAlreadyExistsError(email)
              self.repository.add(user)
      except UnitOfWorkError as error:
          raise ServiceError("Failed to register user") from error
  ```
  `UserAlreadyExistsError` летит сквозь `__exit__` нетронутым (с откатом) и превращается в 400 как раньше.

Читающие методы (`get_all_users`, `get_current_user`, `authenticate_user`) не трогаем — в UoW заворачивается только запись.

### 6. Транспорт

- `src/api/rest/user/decorators.py`, `handle_users_errors` — добавить ветку:
  ```python
  except ServiceError as error:
      raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error
  ```
- `src/api/graphql/user/decorators.py`, `handle_users_errors` — добавить `ServiceError` в кортеж, который переводится в `GraphQLError`.

Оба уже висят на `add_user` / мутации `register`, новых декораторов не нужно.

### 7. `CLAUDE.md`

В описание слоя 4 добавить фразу про `UnitOfWork`: границу транзакции держит сервис, репозиторий не коммитит. В слое 3 — что репозиторий больше не управляет транзакцией.

## Файлы

| Файл | Что |
|---|---|
| `src/infrastructure/exceptions.py` | новый — `InfrastructureError`, `UnitOfWorkError` |
| `src/infrastructure/unit_of_work.py` | новый — `UnitOfWork` |
| `src/core/exceptions.py` | новый — `ServiceError` |
| `src/user/repositories.py` | убрать `commit` из `add` |
| `src/core/user/services.py` | `uow` в `__init__`/`with_session`, обёртка `register_user` |
| `src/api/rest/user/decorators.py` | `ServiceError` → 500 |
| `src/api/graphql/user/decorators.py` | `ServiceError` → `GraphQLError` |
| `CLAUDE.md` | слои 3–4 |

Миграции не нужны — схема не меняется.

## Verification

1. `uv run ruff format . && uv run ruff check . && uvx pyright`
2. `docker compose up -d --build`, `uv run alembic upgrade head`
3. **Запись по-прежнему коммитится** (главный риск: `commit` убран из репозитория) — `POST /v1/api/users` в Swagger (http://127.0.0.1:8010/docs), затем `GET /v1/api/users` и `psql` в контейнере: пользователь на месте.
4. **Дубль отдаёт 400, а не 500** — повторить тот же `POST`: `UserAlreadyExistsError` должен пройти сквозь `__exit__` неизменным.
5. **Откат работает** — скриптом в scratchpad (не в репозитории), запуск с хоста, `DATABASE_URL` берётся из `.env`:
   ```python
   from core.user.entities import RegularUser
   from infrastructure.database import SessionLocal
   from infrastructure.unit_of_work import UnitOfWork
   from user.repositories import UserRepository

   session = SessionLocal()
   uow, repo = UnitOfWork(session), UserRepository(session)
   try:
       with uow:
           repo.add(RegularUser(username="rb_test", password="x", email="rb@test.com", permissions=[]))
           raise RuntimeError("boom")
   except RuntimeError:
       pass
   print(repo.get_by_username("rb_test"))  # ожидаем None
   ```
   Второй прогон того же скрипта без `raise`, но с двумя `add`, где у второго дублирующий email: ожидаем `UnitOfWorkError` и отсутствие первого пользователя в базе.
6. **GraphQL** — мутация `register` в GraphiQL (http://127.0.0.1:8010/v1/gql): успешная регистрация сохраняется, повторная даёт понятный `GraphQLError`.
