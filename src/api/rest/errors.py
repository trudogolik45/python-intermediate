from functools import wraps

from fastapi import HTTPException, status

from core.exceptions import DomainError, Failure

STATUS = {
    Failure.CONFLICT: status.HTTP_400_BAD_REQUEST,
    Failure.NOT_FOUND: status.HTTP_404_NOT_FOUND,
    Failure.UNAUTHENTICATED: status.HTTP_401_UNAUTHORIZED,
    Failure.INVALID: status.HTTP_400_BAD_REQUEST,
    Failure.INTERNAL: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def handle_domain_errors(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except DomainError as error:
            raise HTTPException(status_code=STATUS[error.failure], detail=str(error)) from error

    return wrapper
