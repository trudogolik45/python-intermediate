import strawberry

from api.graphql.decorators import require_permissions
from api.graphql.pagination import DEFAULT_LIMIT, Page, paginate
from api.graphql.user.decorators import handle_users_errors
from api.graphql.user.types import Token, User
from core.permissions import Permission


@strawberry.type
class UserQuery:
    @strawberry.field
    @require_permissions(Permission.VIEW_USER)
    async def all_users(self, info: strawberry.Info, limit: int = DEFAULT_LIMIT, offset: int = 0) -> Page[User]:
        service = info.context["user_service"]
        users = [User(username=user.username, email=user.email) for user in service.get_all_users()]
        return paginate(users, limit, offset)


@strawberry.type
class UserMutation:
    @strawberry.mutation
    @handle_users_errors
    async def register(self, info: strawberry.Info, username: str, password: str, email: str) -> User:
        service = info.context["user_service"]
        service.register_user(username, password, email, is_admin=False, permissions=[])
        return User(username=username, email=email)

    @strawberry.mutation
    @handle_users_errors
    async def login(self, info: strawberry.Info, username: str, password: str) -> Token:
        service = info.context["user_service"]
        return Token(**service.login(username, password))
