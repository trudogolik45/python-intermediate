from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.exceptions import UnitOfWorkError


class UnitOfWork:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        if exc_type is None:
            await self.commit()
            return False
        await self.session.rollback()
        if issubclass(exc_type, SQLAlchemyError):
            raise UnitOfWorkError() from exc
        return False

    async def commit(self):
        try:
            await self.session.commit()
        except SQLAlchemyError as error:
            await self.session.rollback()
            raise UnitOfWorkError() from error
