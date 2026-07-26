import strawberry
from strawberry.fastapi import GraphQLRouter

from api.graphql.resolvers import Mutation, Query

schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_router = GraphQLRouter(schema)
