from typing import Generic, TypeVar

import strawberry

DEFAULT_LIMIT = 10
MAX_LIMIT = 100

T = TypeVar("T")


@strawberry.type
class Page(Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


def paginate(items: list[T], limit: int, offset: int) -> Page[T]:
    limit = min(max(limit, 1), MAX_LIMIT)
    offset = max(offset, 0)
    return Page(items=items[offset : offset + limit], total=len(items), limit=limit, offset=offset)
