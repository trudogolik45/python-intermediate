from core.exceptions import DomainError, Failure


class UserError(DomainError):
    pass


class UserAlreadyExistsError(UserError):
    failure = Failure.CONFLICT

    def __init__(self, username):
        super().__init__(f"User {username} already exists")


class UserNotFoundError(UserError):
    failure = Failure.NOT_FOUND

    def __init__(self, user_id):
        super().__init__(f"User {user_id} not found")


class InvalidCredentialsError(UserError):
    failure = Failure.UNAUTHENTICATED

    def __init__(self):
        super().__init__("Invalid username or password")


class InvalidTokenError(UserError):
    failure = Failure.UNAUTHENTICATED

    def __init__(self, message="Invalid or expired token"):
        super().__init__(message)
