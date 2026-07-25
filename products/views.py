from fastapi import APIRouter, Depends

from products.models import Product
from products.services import ProductService
from users.dependencies import check_permissions
from users.permissions import Permission

products_router = APIRouter(prefix="/products", tags=["products"])


@products_router.post("", dependencies=[Depends(check_permissions(Permission.ADD_PRODUCT))])
async def create_product(product: Product):
    ProductService.create_product(product)
    return {"result": f"Product created: {product.name}"}


@products_router.get("/{product_id}", dependencies=[Depends(check_permissions(Permission.VIEW_PRODUCT))])
async def get_product(product_id: int):
    return ProductService.get_product(product_id)


@products_router.put("/{product_id}", dependencies=[Depends(check_permissions(Permission.UPDATE_PRODUCT))])
async def update_product(product_id: int, product: Product):
    ProductService.update_product(product_id, product)
    return {"result": f"Product updated: {product.name}"}


@products_router.delete("/{product_id}", dependencies=[Depends(check_permissions(Permission.DELETE_PRODUCT))])
async def delete_product(product_id: int):
    ProductService.delete_product(product_id)
    return {"result": f"Product deleted: {product_id}"}
