from core.permissions import Permission


class BaseUser:
    def __init__(self, username, password, email, is_admin, permissions, id=None, created_at=None, updated_at=None):
        self.id = id
        self.username = username
        self.password = password
        self.email = email
        self.is_admin = is_admin
        self.permissions = permissions
        self.created_at = created_at
        self.updated_at = updated_at

    def get_info(self):
        return {
            "username": self.username,
            "email": self.email,
            "is_admin": self.is_admin,
            "permissions": self.permissions,
        }


class AdminUser(BaseUser):
    def __init__(self, username, password, email, id=None, created_at=None, updated_at=None):
        super().__init__(
            username,
            password,
            email,
            is_admin=True,
            permissions=list(Permission),
            id=id,
            created_at=created_at,
            updated_at=updated_at,
        )


class RegularUser(BaseUser):
    def __init__(self, username, password, email, permissions, id=None, created_at=None, updated_at=None):
        super().__init__(
            username,
            password,
            email,
            is_admin=False,
            permissions=permissions or [],
            id=id,
            created_at=created_at,
            updated_at=updated_at,
        )
