import strawberry
from strawberry.fastapi import GraphQLRouter

from api.graphql.dependencies import get_context
from api.graphql.resolvers import Mutation, Query

schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_router = GraphQLRouter(schema, context_getter=get_context, multipart_uploads_enabled=True)
