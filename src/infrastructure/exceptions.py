class InfrastructureError(Exception):
    pass


class UnitOfWorkError(InfrastructureError):
    def __init__(self, message="Transaction failed"):
        super().__init__(message)
