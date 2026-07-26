from functools import wraps

from graphql import GraphQLError

from core.permissions import Permission


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
