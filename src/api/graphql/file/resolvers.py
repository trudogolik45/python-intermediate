from typing import cast

import strawberry
from fastapi import UploadFile
from strawberry.file_uploads import Upload

from api.graphql.decorators import require_permissions
from api.graphql.file.decorators import handle_files_errors
from api.graphql.file.types import UploadedFile, to_uploaded_file
from api.graphql.pagination import DEFAULT_LIMIT, Page, paginate
from core.file.services import FileService
from core.permissions import Permission


@strawberry.type
class FileQuery:
    @strawberry.field
    @require_permissions(Permission.VIEW_FILE)
    async def files(self, info: strawberry.Info, limit: int = DEFAULT_LIMIT, offset: int = 0) -> Page[UploadedFile]:
        files = [to_uploaded_file(filename) for filename in FileService.get_all_files()]
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
