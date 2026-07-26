import strawberry


@strawberry.type
class User:
    username: str
    email: str


@strawberry.type
class Token:
    access_token: str
    refresh_token: str
