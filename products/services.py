from products.exceptions import ProductAlreadyExistsError, ProductNotFoundError
from products.managers import product_manager
from products.models import Product


class ProductService:
    @staticmethod
    def create_product(product: Product):
        if not product_manager.add_product(product):
            raise ProductAlreadyExistsError(product.id)

    @staticmethod
    def get_product(product_id: int):
        product = product_manager.get_product(product_id)
        if not product:
            raise ProductNotFoundError(product_id)
        return product

    @staticmethod
    def update_product(product_id: int, product: Product):
        if not product_manager.update_product(product_id, product):
            raise ProductNotFoundError(product_id)

    @staticmethod
    def delete_product(product_id: int):
        if not product_manager.delete_product(product_id):
            raise ProductNotFoundError(product_id)
