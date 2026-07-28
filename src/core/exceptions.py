class ServiceError(Exception):
    def __init__(self, message="Operation failed"):
        super().__init__(message)
