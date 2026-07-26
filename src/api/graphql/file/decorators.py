from functools import wraps

from graphql import GraphQLError

from core.file.exceptions import FileAlreadyExistsError, InvalidFileNameError, UnsupportedFileTypeError


def handle_files_errors(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except (FileAlreadyExistsError, InvalidFileNameError, UnsupportedFileTypeError) as error:
            raise GraphQLError(str(error)) from error

    return wrapper
