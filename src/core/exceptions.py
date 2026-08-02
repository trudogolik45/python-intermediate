from enum import StrEnum


class Failure(StrEnum):
    CONFLICT = "conflict"
    NOT_FOUND = "not_found"
    UNAUTHENTICATED = "unauthenticated"
    INVALID = "invalid"
    INTERNAL = "internal"


class DomainError(Exception):
    failure = Failure.INTERNAL


class ServiceError(DomainError):
    def __init__(self, message="Operation failed"):
        super().__init__(message)
