import strawberry

from api.graphql.decorators import handle_users_errors
from api.graphql.types import Token, User
from core.user.services import UserService


@strawberry.type
class Query:
    @strawberry.field
    async def all_users(self) -> list[User]:
        return [User(username=user.username, email=user.email) for user in UserService.get_all_users()]


@strawberry.type
class Mutation:
    @strawberry.mutation
    @handle_users_errors
    async def register(self, username: str, password: str, email: str) -> User:
        UserService.register_user(username, password, email, is_admin=False, permissions=[])
        return User(username=username, email=email)

    @strawberry.mutation
    @handle_users_errors
    async def login(self, username: str, password: str) -> Token:
        return Token(**UserService.login(username, password))
