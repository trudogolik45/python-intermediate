class ProductError(Exception):
    pass


class ProductNotFoundError(ProductError):
    def __init__(self, product_id):
        super().__init__(f"Product {product_id} not found")


class ProductAlreadyExistsError(ProductError):
    def __init__(self, product_id):
        super().__init__(f"Product {product_id} already exists")
