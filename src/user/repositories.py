from core.permissions import Permission
from core.user.entities import AdminUser, BaseUser, RegularUser
from user.models import User


class UserRepository:
    def __init__(self, session):
        self.session = session

    def add(self, user: BaseUser):
        self.session.add(
            User(
                username=user.username,
                password=user.password,
                email=user.email,
                is_admin=user.is_admin,
                permissions=[Permission(permission).value for permission in user.permissions],
            )
        )
        self.session.commit()

    def get_by_username(self, username):
        row = self.session.query(User).filter(User.username == username).first()
        if not row:
            return None
        return self._to_entity(row)

    def get_by_email(self, email):
        row = self.session.query(User).filter(User.email == email).first()
        if not row:
            return None
        return self._to_entity(row)

    def get_all(self):
        return [self._to_entity(row) for row in self.session.query(User).all()]

    @staticmethod
    def _to_entity(row: User) -> BaseUser:
        if row.is_admin:
            return AdminUser(username=row.username, password=row.password, email=row.email)
        return RegularUser(
            username=row.username,
            password=row.password,
            email=row.email,
            permissions=[Permission(value) for value in row.permissions],
        )
