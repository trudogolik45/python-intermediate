import strawberry

from api.graphql.decorators import require_authentication
from api.graphql.pagination import DEFAULT_LIMIT, Page, paginate
from api.graphql.user.decorators import handle_users_errors
from api.graphql.user.types import Token, User
from core.user.services import UserService


@strawberry.type
class UserQuery:
    @strawberry.field
    @require_authentication
    async def all_users(self, info: strawberry.Info, limit: int = DEFAULT_LIMIT, offset: int = 0) -> Page[User]:
        users = [User(username=user.username, email=user.email) for user in UserService.get_all_users()]
        return paginate(users, limit, offset)


@strawberry.type
class UserMutation:
    @strawberry.mutation
    @handle_users_errors
    async def register(self, username: str, password: str, email: str) -> User:
        UserService.register_user(username, password, email, is_admin=False, permissions=[])
        return User(username=username, email=email)

    @strawberry.mutation
    @handle_users_errors
    async def login(self, username: str, password: str) -> Token:
        return Token(**UserService.login(username, password))
