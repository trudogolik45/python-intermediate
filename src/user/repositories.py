from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.permissions import Permission
from core.user.entities import AdminUser, BaseUser, RegularUser
from user.models import User


class UserRepository:
    def __init__(self, session: AsyncSession):
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

    async def get_by_username(self, username):
        result = await self.session.execute(select(User).where(User.username == username))
        row = result.scalars().first()
        if not row:
            return None
        return self._to_entity(row)

    async def get_by_email(self, email):
        result = await self.session.execute(select(User).where(User.email == email))
        row = result.scalars().first()
        if not row:
            return None
        return self._to_entity(row)

    async def get_all(self):
        result = await self.session.execute(select(User))
        return [self._to_entity(row) for row in result.scalars().all()]

    async def update(self, user_id, is_admin):
        row = await self._row_by_id(user_id)
        if not row:
            return None
        row.is_admin = is_admin
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_entity(row)

    async def _row_by_id(self, user_id):
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalars().first()

    @staticmethod
    def _to_entity(row: User) -> BaseUser:
        if row.is_admin:
            return AdminUser(
                username=row.username,
                password=row.password,
                email=row.email,
                id=row.id,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
        return RegularUser(
            username=row.username,
            password=row.password,
            email=row.email,
            permissions=[Permission(value) for value in row.permissions],
            id=row.id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
