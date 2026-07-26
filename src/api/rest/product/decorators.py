from functools import wraps

from fastapi import HTTPException, status

from core.product.exceptions import ProductAlreadyExistsError, ProductNotFoundError


def handle_products_errors(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ProductNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        except ProductAlreadyExistsError as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    return wrapper
