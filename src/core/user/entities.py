from core.permissions import Permission


def permissions_for(is_admin, permissions):
    if is_admin:
        return list(Permission)
    return list(permissions or [])


class User:
    def __init__(
        self,
        username,
        password,
        email,
        is_admin=False,
        permissions=None,
        id=None,
        created_at=None,
        updated_at=None,
    ):
        self.id = id
        self.username = username
        self.password = password
        self.email = email
        self.is_admin = is_admin
        self.permissions = permissions_for(is_admin, permissions)
        self.created_at = created_at
        self.updated_at = updated_at

    def get_info(self):
        return {
            "username": self.username,
            "email": self.email,
            "is_admin": self.is_admin,
            "permissions": self.permissions,
        }
