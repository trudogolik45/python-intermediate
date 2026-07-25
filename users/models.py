
PERMISSIONS = ["view_product", "update_product", "add_product", "delete_product"]

class BaseUser:
    def __init__(self, username, email, is_admin, permissions):
        self.username = username
        self.email = email
        self.is_admin = is_admin
        self.permissions = permissions
        
    def get_info(self):
        return {
            "username": self.username,
            "email": self.email,
            "is_admin": self.is_admin,
            "permissions": self.permissions
        }
        
class AdminUser(BaseUser):
    def __init__(self, username, email):
        super().__init__(username, email, is_admin=True, permissions=PERMISSIONS)
        
class RegularUser(BaseUser):
    def __init__(self, username, email, permissions):
        super().__init__(username, email, is_admin=False, permissions=permissions)