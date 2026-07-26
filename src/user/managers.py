from core.user.entities import BaseUser


class UserManager:
    def __init__(self):
        self.users = {}

    def add_user(self, user: BaseUser):
        if self._is_user_exists(user.username):
            return False
        self.users[user.username] = user
        return True

    def get_user(self, username):
        return self.users.get(username)

    def get_all_users(self):
        return [user.get_info() for user in self.users.values()]

    def _is_user_exists(self, username):
        return username in self.users


user_manager = UserManager()
