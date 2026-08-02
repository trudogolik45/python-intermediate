from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.permissions import Permission
from core.user.entities import User
from user.models import User as UserRow


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, user: User):
        self.session.add(
            UserRow(
                username=user.username,
                password=user.password,
                email=user.email,
                is_admin=user.is_admin,
                permissions=[Permission(permission).value for permission in user.permissions],
            )
        )

    async def get_by_username(self, username):
        result = await self.session.execute(select(UserRow).where(UserRow.username == username))
        row = result.scalars().first()
        if not row:
            return None
        return self._to_entity(row)

    async def get_by_email(self, email):
        result = await self.session.execute(select(UserRow).where(UserRow.email == email))
        row = result.scalars().first()
        if not row:
            return None
        return self._to_entity(row)

    async def get_all(self):
        result = await self.session.execute(select(UserRow))
        return [self._to_entity(row) for row in result.scalars().all()]

    async def update(self, user_id, is_admin, permissions):
        row = await self._row_by_id(user_id)
        if not row:
            return None
        row.is_admin = is_admin
        row.permissions = [Permission(permission).value for permission in permissions]
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_entity(row)

    async def _row_by_id(self, user_id):
        result = await self.session.execute(select(UserRow).where(UserRow.id == user_id))
        return result.scalars().first()

    @staticmethod
    def _to_entity(row: UserRow) -> User:
        return User(
            username=row.username,
            password=row.password,
            email=row.email,
            is_admin=row.is_admin,
            permissions=[Permission(value) for value in row.permissions],
            id=row.id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
