from fastapi import APIRouter, Depends

from api.rest.product.decorators import handle_products_errors
from api.rest.user.decorators import require_permissions
from api.rest.user.dependencies import get_current_user
from core.permissions import Permission
from core.product.entities import Product
from core.product.services import ProductService

products_router = APIRouter(prefix="/products", tags=["products"])


@products_router.post("")
@require_permissions(Permission.ADD_PRODUCT)
@handle_products_errors
async def create_product(product: Product, current_user=Depends(get_current_user)):
    ProductService.create_product(product)
    return {"result": f"Product created: {product.name}"}


@products_router.get("/{product_id}")
@require_permissions(Permission.VIEW_PRODUCT)
@handle_products_errors
async def get_product(product_id: int, current_user=Depends(get_current_user)):
    return ProductService.get_product(product_id)


@products_router.put("/{product_id}")
@require_permissions(Permission.UPDATE_PRODUCT)
@handle_products_errors
async def update_product(product_id: int, product: Product, current_user=Depends(get_current_user)):
    ProductService.update_product(product_id, product)
    return {"result": f"Product updated: {product.name}"}


@products_router.delete("/{product_id}")
@require_permissions(Permission.DELETE_PRODUCT)
@handle_products_errors
async def delete_product(product_id: int, current_user=Depends(get_current_user)):
    ProductService.delete_product(product_id)
    return {"result": f"Product deleted: {product_id}"}
