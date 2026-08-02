from functools import wraps

from graphql import GraphQLError

from core.exceptions import DomainError


def handle_domain_errors(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except DomainError as error:
            raise GraphQLError(str(error), extensions={"code": error.failure.value}) from error

    return wrapper
