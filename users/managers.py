from users.models import BaseUser
from fastapi import HTTPException


class UserManager:
    def __init__(self):
        self.users = {}

    def add_user(self, user: BaseUser):
        if user.username in self.users:
            raise HTTPException(status_code=400, detail="User already exists")
        self.users[user.username] = user
        return user

    def get_all_users(self):
        return [user.get_info() for user in self.users.values()]


user_manager = UserManager()
