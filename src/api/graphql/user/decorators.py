from functools import wraps

from graphql import GraphQLError

from core.exceptions import ServiceError
from core.user.exceptions import InvalidCredentialsError, UserAlreadyExistsError, UserNotFoundError


def handle_users_errors(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except (UserAlreadyExistsError, UserNotFoundError, InvalidCredentialsError, ServiceError) as error:
            raise GraphQLError(str(error)) from error

    return wrapper
