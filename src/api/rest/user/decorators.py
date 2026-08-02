from functools import wraps

from fastapi import HTTPException, status

from core.permissions import Permission


def require_permissions(*required: Permission):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user, **kwargs):
            if not all(permission in current_user.permissions for permission in required):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
            return await func(*args, current_user=current_user, **kwargs)

        return wrapper

    return decorator
