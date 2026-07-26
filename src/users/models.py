from users.permissions import Permission


class BaseUser:
    def __init__(self, username, password, email, is_admin, permissions):
        self.username = username
        self.password = password
        self.email = email
        self.is_admin = is_admin
        self.permissions = permissions

    def get_info(self):
        return {
            "username": self.username,
            "email": self.email,
            "is_admin": self.is_admin,
            "permissions": self.permissions,
        }


class AdminUser(BaseUser):
    def __init__(self, username, password, email):
        super().__init__(username, password, email, is_admin=True, permissions=list(Permission))


class RegularUser(BaseUser):
    def __init__(self, username, password, email, permissions):
        super().__init__(username, password, email, is_admin=False, permissions=permissions or [])
