from fastapi import APIRouter
from pydantic import BaseModel
from products.managers import product_manager

products_router = APIRouter(prefix="/products", tags=["products"])

class Product(BaseModel):
    id: int
    name: str
    price: float


@products_router.post("")
async def create_product(product: Product):
    product_manager.add_product(product)
    return {"result": f"Product created: {product.name}"}


@products_router.get("/{product_id}")
async def get_product(product_id: int):
    return product_manager.get_product(product_id)


@products_router.put("/{product_id}")
async def update_product(product_id: int, product: Product):
    product_manager.update_product(product_id, product)
    return {"result": f"Product updated: {product.name}"}


@products_router.delete("/{product_id}")
async def delete_product(product_id: int):
    product_manager.delete_product(product_id)
    return {"result": f"Product deleted: {product_id}"}
