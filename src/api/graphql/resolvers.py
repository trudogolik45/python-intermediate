import strawberry

from api.graphql.user.resolvers import UserMutation, UserQuery


@strawberry.type
class Query(UserQuery):
    pass


@strawberry.type
class Mutation(UserMutation):
    pass
