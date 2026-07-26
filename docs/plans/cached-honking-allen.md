# Загрузка файлов через GraphQL

## Context

Урок 14 курса — приём файла мутацией strawberry и раздача загруженного статикой. В видео всё сделано одним куском: `FileMutation` положена в `api/graphql/user/resolvers.py`, запись файла идёт прямо в резолвере через `open()`, имя берётся от клиента без проверок, доступ не ограничен.

В этом проекте так нельзя: слои разведены (`api` → `core` → менеджеры), домены лежат по отдельным пакетам, логика живёт в сервисах. Поэтому урок раскладывается на полноценный домен `file`, а хранилище файлов встаёт четвёртым менеджером рядом с `product_manager` и `user_manager`.

Заодно закрывается давний пробел: в GraphQL-слое до сих пор нет проверки прав — только `require_authentication` (`api/graphql/decorators.py:6`), хотя REST давно ходит через `require_permissions` (`api/rest/user/decorators.py:22`). Новая мутация — повод завести права и в GraphQL.

Решения, согласованные с пользователем:
- доступ к файловым резолверам — через права: новые `Permission.UPLOAD_FILE` и `Permission.VIEW_FILE`;
- объём — загрузка файла и список файлов с пагинацией (удаления нет);
- имя файла санитизируется, повторная загрузка того же имени — ошибка, а не молчаливая перезапись;
- `allUsers` переезжает на `require_permissions(Permission.VIEW_USER)` — паритет с `GET /v1/api/users`; `require_authentication` после этого нигде не используется и удаляется.

Что уже есть и переиспользуется:
- `Page` / `paginate` (`src/api/graphql/pagination.py`) — под список файлов;
- `python-multipart` уже стоит транзитивно через `fastapi[standard]` (`uv.lock`), отдельная зависимость не нужна — в отличие от урока;
- `get_context` (`src/api/graphql/dependencies.py:17`) уже кладёт `current_user` в контекст, менять не надо.

## Реализация

### 1. Слой хранения — `src/file/managers.py` (новый пакет)

Повторяет форму `ProductManager` (`src/product/managers.py`): булевы возвраты, protected-проверка существования, синглтон в конце модуля.

```python
from pathlib import Path

MEDIA_ROOT = Path(__file__).resolve().parents[2] / "media"


class FileManager:
    def __init__(self, root=MEDIA_ROOT):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save_file(self, filename, content):
        if self._is_file_exists(filename):
            return False
        (self.root / filename).write_bytes(content)
        return True

    def get_all_files(self):
        return sorted(path.name for path in self.root.iterdir() if path.is_file())

    def _is_file_exists(self, filename):
        return (self.root / filename).exists()


file_manager = FileManager()
```

`parents[2]` — корень проекта (`src/file/managers.py` → `src` → корень), в контейнере это `/app/media`. `mkdir` в `__init__` отрабатывает при импорте синглтона, поэтому к моменту `app.mount` директория гарантированно есть.

Пустой `src/file/__init__.py` — как у остальных пакетов.

### 2. Ядро — `src/core/file/`

`exceptions.py` — по образцу `core/product/exceptions.py`:

```python
class FileError(Exception): ...
class FileAlreadyExistsError(FileError)     # f"File {filename} already exists"
class InvalidFileNameError(FileError)       # f"Invalid file name: {filename}"
class UnsupportedFileTypeError(FileError)   # f"File type {suffix} is not supported"
```

`services.py` — вся проверка имени здесь, менеджер получает уже безопасное:

```python
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".txt"}


class FileService:
    @staticmethod
    def save_file(filename, content):
        safe_name = FileService.build_safe_name(filename)
        if not file_manager.save_file(safe_name, content):
            raise FileAlreadyExistsError(safe_name)
        return safe_name

    @staticmethod
    def get_all_files():
        return file_manager.get_all_files()

    @staticmethod
    def build_safe_name(filename):
        name = Path(filename or "").name
        if not name or name.startswith("."):
            raise InvalidFileNameError(filename)
        suffix = Path(name).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise UnsupportedFileTypeError(suffix)
        return name
```

`Path(...).name` срезает любой путь, поэтому имя `../../etc/passwd` превращается в `passwd` и остаётся внутри `media/`. `filename` у `UploadFile` опционален — `or ""` закрывает `None`.

Файл сущности не нужен: наружу ходят имена, а GraphQL-тип собирается в слое API.

### 3. Права — `src/core/permissions.py`

Дописать в `Permission` два значения:

```python
VIEW_FILE = "view_file"
UPLOAD_FILE = "upload_file"
```

`AdminUser` берёт `list(Permission)` (`core/user/entities.py:23`), поэтому админ получает их автоматически.

### 4. Права в GraphQL — `src/api/graphql/decorators.py`

Заменить `require_authentication` на `require_permissions`. Форма — фабрика декораторов, как в REST (`api/rest/user/decorators.py:22`), но `current_user` берётся не из параметра, а из контекста, и `None` тут возможен (`get_current_user` в `api/graphql/dependencies.py` возвращает `None` вместо исключения), поэтому проверок две:

```python
def require_permissions(*required: Permission):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, info, **kwargs):
            current_user = info.context.get("current_user")
            if not current_user:
                raise GraphQLError("Authentication required")
            if not all(permission in current_user.permissions for permission in required):
                raise GraphQLError("Not enough permissions")
            return await func(*args, info=info, **kwargs)

        return wrapper

    return decorator
```

`require_authentication` удалить — после правки пункта 6 он больше нигде не вызывается.

### 5. API-слой — `src/api/graphql/file/`

`types.py`:

```python
MEDIA_URL = "/media"


@strawberry.type
class UploadedFile:
    filename: str
    url: str


def to_uploaded_file(filename: str) -> UploadedFile:
    return UploadedFile(filename=filename, url=f"{MEDIA_URL}/{filename}")
```

`MEDIA_URL` живёт здесь, потому что префикс раздачи — транспортное знание; `main.py` его импортирует, так что литерал остаётся в одном месте.

`decorators.py` — `handle_files_errors`, копия `api/graphql/user/decorators.py` с тремя файловыми исключениями → `GraphQLError`.

`resolvers.py`:

```python
@strawberry.type
class FileQuery:
    @strawberry.field
    @require_permissions(Permission.VIEW_FILE)
    async def files(self, info: strawberry.Info, limit: int = DEFAULT_LIMIT, offset: int = 0) -> Page[UploadedFile]:
        files = [to_uploaded_file(name) for name in FileService.get_all_files()]
        return paginate(files, limit, offset)


@strawberry.type
class FileMutation:
    @strawberry.mutation
    @require_permissions(Permission.UPLOAD_FILE)
    @handle_files_errors
    async def upload_file(self, info: strawberry.Info, file: Upload) -> UploadedFile:
        upload = cast(UploadFile, file)
        content = await upload.read()
        return to_uploaded_file(FileService.save_file(upload.filename, content))
```

Про `cast`: `Upload` из `strawberry.file_uploads` — это `NewType("Upload", bytes)` (`strawberry/file_uploads/scalars.py`), то есть для pyright у аргумента нет ни `.read()`, ни `.filename`. Фактически же strawberry подставляет туда starlette-овский `UploadFile` (`strawberry/http/async_base_view.py:274` — `parse_multipart` берёт объекты из `form_data.files`). Аннотацию менять нельзя — strawberry строит по ней схему, — поэтому один `cast(UploadFile, file)` из `fastapi`; это чище, чем `# type: ignore`.

`info` в сигнатуре обязателен: `require_permissions` читает из него контекст.

### 6. Сборка схемы

`src/api/graphql/resolvers.py` — подмешать файловые классы:

```python
class Query(UserQuery, FileQuery): ...
class Mutation(UserMutation, FileMutation): ...
```

`src/api/graphql/user/resolvers.py` — `all_users` переводится на `@require_permissions(Permission.VIEW_USER)`, импорт `require_authentication` уходит.

`src/api/graphql/schema.py` — включить multipart, иначе strawberry ответит `Unsupported content type` на `multipart/form-data` (по умолчанию флаг `False`):

```python
graphql_router = GraphQLRouter(schema, context_getter=get_context, multipart_uploads_enabled=True)
```

### 7. Раздача статики — `src/main.py`

```python
app.mount(MEDIA_URL, StaticFiles(directory=MEDIA_ROOT), name="media")
```

`MEDIA_URL` из `api.graphql.file.types`, `MEDIA_ROOT` из `file.managers`.

### 8. Инфраструктура

- `pyproject.toml` — в `[tool.hatch.build.targets.wheel].packages` добавить `"src/file"`, затем `uv sync` (иначе `import file.managers` не разрешится).
- `docker-compose.yml` — в `volumes` сервиса `web_app` добавить `- ./media:/app/media`, иначе загруженные файлы живут только внутри контейнера. Смонтирован сейчас только `./src`.
- `.gitignore` — `media/`; `.dockerignore` — `media`.
- `CLAUDE.md` — в описании слоя 1 убрать «Прав в нём пока нет», в слое 3 упомянуть `file/managers.py` как файловое хранилище.

## Verification

Обязательный прогон из `CLAUDE.md`: `uv run ruff format .` → `uv run ruff check .` → `uvx pyright`.

Затем `docker compose up -d --build` (пересборка нужна: менялся `pyproject.toml`) и сквозной сценарий:

1. Админ — только через REST, GraphQL-`register` выдаёт пустые права:
   `curl -X POST "http://127.0.0.1:8010/v1/api/users?username=admin&password=secret&email=a@b.c&is_admin=true"`
2. Токен: `curl "http://127.0.0.1:8010/v1/api/users/login?username=admin&password=secret"` — access живёт минуту, при 401 перелогиниться.
3. Загрузка (GraphiQL файлы отправлять не умеет — только curl или Postman):
   ```
   curl -X POST http://127.0.0.1:8010/v1/gql -H "Authorization: $TOKEN" \
     -F operations='{"query":"mutation($file: Upload!){ uploadFile(file: $file){ filename url } }","variables":{"file":null}}' \
     -F map='{"0":["variables.file"]}' \
     -F 0=@./picture.png
   ```
   Ожидание: `{"filename":"picture.png","url":"/media/picture.png"}`.
4. Файл отдаётся: `http://127.0.0.1:8010/media/picture.png` открывается в браузере; на хосте он лежит в `./media/`.
5. Повторная отправка того же файла → `File picture.png already exists`.
6. Отправка с именем `../../etc/passwd` (`-F '0=@./picture.png;filename=../../etc/passwd'`) → `File type  is not supported`, за пределы `media/` ничего не записалось.
7. Расширение вне списка (`.exe`) → `File type .exe is not supported`.
8. Список в GraphiQL: `{ files(limit: 10, offset: 0) { items { filename url } total } }` с заголовком `Authorization`.
9. Без токена или обычным пользователем (`mutation { register(...) }` → логин) те же запросы дают `Authentication required` / `Not enough permissions`.
10. Регрессия по правам: `{ allUsers(limit: 5) { items { username } } }` под админом отдаёт список, под свежерегистрированным пользователем — `Not enough permissions`.

## Известные упрощения

- Запись файла синхронная (`write_bytes`) внутри async-резолвера — как и bcrypt в `UserService`, событийный цикл на время записи блокируется.
- Содержимое читается в память целиком, ограничения на размер нет.
