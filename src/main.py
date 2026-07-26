from fastapi import APIRouter, FastAPI

from api.graphql.schema import graphql_router
from api.rest.product.views import products_router
from api.rest.user.views import user_router

app = FastAPI()


api_v1_router = APIRouter(prefix="/v1/api")
api_v1_router.include_router(products_router)
api_v1_router.include_router(user_router)

app.include_router(api_v1_router)
app.include_router(graphql_router, prefix="/v1/gql")
