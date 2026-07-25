from fastapi import HTTPException

from products.managers import product_manager
from products.models import Product


class ProductService:
    @staticmethod
    def create_product(product: Product):
        if not product_manager.add_product(product):
            raise HTTPException(status_code=400, detail="Product already exists")

    @staticmethod
    def get_product(product_id: int):
        product = product_manager.get_product(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product

    @staticmethod
    def update_product(product_id: int, product: Product):
        if not product_manager.update_product(product_id, product):
            raise HTTPException(status_code=404, detail="Product not found")

    @staticmethod
    def delete_product(product_id: int):
        if not product_manager.delete_product(product_id):
            raise HTTPException(status_code=404, detail="Product not found")
