from functools import wraps

from fastapi import HTTPException, status

from users.exceptions import InvalidCredentialsError, InvalidTokenError, UserAlreadyExistsError
from users.permissions import Permission


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
