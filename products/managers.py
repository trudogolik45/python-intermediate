class ProductManager:
    def __init__(self):
        self.products = {}

    def add_product(self, product):
        if self._is_product_exists(product.id):
            return False
        self.products[product.id] = product
        return True

    def get_product(self, product_id):
        return self.products.get(product_id)

    def update_product(self, product_id, product):
        if not self._is_product_exists(product_id):
            return False
        self.products[product_id] = product
        return True

    def delete_product(self, product_id):
        if not self._is_product_exists(product_id):
            return False
        del self.products[product_id]
        return True

    def _is_product_exists(self, product_id):
        return product_id in self.products


product_manager = ProductManager()
