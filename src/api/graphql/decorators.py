from functools import wraps

from graphql import GraphQLError


def require_authentication(func):
    @wraps(func)
    async def wrapper(*args, info, **kwargs):
        if not info.context.get("current_user"):
            raise GraphQLError("Authentication required")
        return await func(*args, info=info, **kwargs)

    return wrapper
