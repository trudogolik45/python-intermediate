import strawberry

from api.graphql.file.resolvers import FileMutation, FileQuery
from api.graphql.user.resolvers import UserMutation, UserQuery


@strawberry.type
class Query(UserQuery, FileQuery):
    pass


@strawberry.type
class Mutation(UserMutation, FileMutation):
    pass
