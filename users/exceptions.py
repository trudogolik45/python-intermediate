class UserError(Exception):
    pass


class UserAlreadyExistsError(UserError):
    def __init__(self, username):
        super().__init__(f"User {username} already exists")


class InvalidCredentialsError(UserError):
    def __init__(self):
        super().__init__("Invalid username or password")


class InvalidTokenError(UserError):
    def __init__(self, message="Invalid or expired token"):
        super().__init__(message)
