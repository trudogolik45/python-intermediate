import strawberry
from strawberry.fastapi import GraphQLRouter

from api.graphql.resolvers import Query

schema = strawberry.Schema(query=Query)
graphql_router = GraphQLRouter(schema)
