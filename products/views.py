from fastapi import APIRouter

from products.models import Product
from products.services import ProductService

products_router = APIRouter(prefix="/products", tags=["products"])


@products_router.post("")
async def create_product(product: Product):
    ProductService.create_product(product)
    return {"result": f"Product created: {product.name}"}


@products_router.get("/{product_id}")
async def get_product(product_id: int):
    return ProductService.get_product(product_id)


@products_router.put("/{product_id}")
async def update_product(product_id: int, product: Product):
    ProductService.update_product(product_id, product)
    return {"result": f"Product updated: {product.name}"}


@products_router.delete("/{product_id}")
async def delete_product(product_id: int):
    ProductService.delete_product(product_id)
    return {"result": f"Product deleted: {product_id}"}
