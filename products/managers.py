from fastapi import HTTPException


class ProductManager:
    def __init__(self):
        self.products = {}

    def add_product(self, product):
        if self._is_product_exists(product.id):
            raise HTTPException(status_code=400, detail="Product already exists")
        self.products[product.id] = product

    def get_product(self, product_id):
        if not self._is_product_exists(product_id):
            raise HTTPException(status_code=404, detail="Product not found")
        return self.products[product_id]

    def update_product(self, product_id, product):
        if not self._is_product_exists(product_id):
            raise HTTPException(status_code=404, detail="Product not found")
        self.products[product_id] = product

    def delete_product(self, product_id):
        if not self._is_product_exists(product_id):
            raise HTTPException(status_code=404, detail="Product not found")
        del self.products[product_id]
        
    def _is_product_exists(self, product_id):
        return product_id in self.products


product_manager = ProductManager()
