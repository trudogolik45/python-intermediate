from core.exceptions import DomainError, Failure


class ProductError(DomainError):
    pass


class ProductNotFoundError(ProductError):
    failure = Failure.NOT_FOUND

    def __init__(self, product_id):
        super().__init__(f"Product {product_id} not found")


class ProductAlreadyExistsError(ProductError):
    failure = Failure.CONFLICT

    def __init__(self, product_id):
        super().__init__(f"Product {product_id} already exists")
