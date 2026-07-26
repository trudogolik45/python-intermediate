from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles

from api.graphql.file.types import MEDIA_URL
from api.graphql.schema import graphql_router
from api.rest.product.views import products_router
from api.rest.user.views import user_router
from file.managers import MEDIA_ROOT

app = FastAPI()


api_v1_router = APIRouter(prefix="/v1/api")
api_v1_router.include_router(products_router)
api_v1_router.include_router(user_router)

app.include_router(api_v1_router)
app.include_router(graphql_router, prefix="/v1/gql")
app.mount(MEDIA_URL, StaticFiles(directory=MEDIA_ROOT), name="media")
