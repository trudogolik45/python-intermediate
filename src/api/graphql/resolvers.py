import strawberry

from api.graphql.types import User

USERS = {
    1: User(id=1, username="john", email="john@example.com"),
    2: User(id=2, username="jane", email="jane@example.com"),
}


@strawberry.type
class Query:
    @strawberry.field
    def user(self, id: int) -> User:
        user = USERS.get(id)
        if not user:
            raise ValueError(f"User {id} not found")
        return user
