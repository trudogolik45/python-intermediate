from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from infrastructure.exceptions import UnitOfWorkError


class UnitOfWork:
    def __init__(self, session: Session):
        self.session = session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is None:
            self.commit()
            return False
        self.session.rollback()
        if issubclass(exc_type, SQLAlchemyError):
            raise UnitOfWorkError() from exc
        return False

    def commit(self):
        try:
            self.session.commit()
        except SQLAlchemyError as error:
            self.session.rollback()
            raise UnitOfWorkError() from error
