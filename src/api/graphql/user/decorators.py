from functools import wraps

from graphql import GraphQLError

from core.exceptions import ServiceError
from core.user.exceptions import InvalidCredentialsError, UserAlreadyExistsError


def handle_users_errors(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except (UserAlreadyExistsError, InvalidCredentialsError, ServiceError) as error:
            raise GraphQLError(str(error)) from error

    return wrapper
