"""Decorators for marking SQLModel methods as GraphQL queries and mutations."""

from __future__ import annotations

from collections.abc import Callable


def query(func: Callable) -> classmethod:
    """Mark a method as a GraphQL query.

    This decorator automatically converts the method to a classmethod.
    The GraphQL field name is generated as: `{entityName}{methodName}`.
    The description is taken from the method's docstring.

    Args:
        func: The method to decorate.

    Returns:
        A classmethod decorator.

    Example:
        ```python
        from sqlmodel import SQLModel
        from sqlmodel_nexus import query

        class User(SQLModel, table=True):
            id: int
            name: str

            @query
            async def get_all(cls, limit: int = 10) -> list['User']:
                \"\"\"Get all users with optional limit.\"\"\"
                return await fetch_users(limit)

            @query
            async def get_by_id(cls, id: int) -> Optional['User']:
                \"\"\"Get a user by ID.\"\"\"
                return await fetch_user(id)
        ```

    This generates the following GraphQL Schema:
        ```graphql
        type Query {
            \"\"\"Get all users with optional limit.\"\"\"
            userGetAll(limit: Int): [User!]!
            \"\"\"Get a user by ID.\"\"\"
            userGetById(id: Int!): User
        }
        ```
    """
    func._graphql_query = True  # type: ignore[attr-defined]
    return classmethod(func)


def mutation(func: Callable) -> classmethod:
    """Mark a method as a GraphQL mutation.

    This decorator automatically converts the method to a classmethod.
    The GraphQL field name is generated as: `{entityName}{methodName}`.
    The description is taken from the method's docstring.

    Args:
        func: The method to decorate.

    Returns:
        A classmethod decorator.

    Example:
        ```python
        from sqlmodel import SQLModel
        from sqlmodel_nexus import mutation

        class User(SQLModel, table=True):
            id: int
            name: str
            email: str

            @mutation
            async def create(cls, name: str, email: str) -> 'User':
                \"\"\"Create a new user.\"\"\"
                return await create_user(name, email)

            @mutation
            async def update_email(cls, id: int, email: str) -> 'User':
                \"\"\"Update user's email.\"\"\"
                return await update_user_email(id, email)
        ```

    This generates the following GraphQL Schema:
        ```graphql
        type Mutation {
            \"\"\"Create a new user.\"\"\"
            userCreate(name: String!, email: String!): User!
            \"\"\"Update user's email.\"\"\"
            userUpdateEmail(id: Int!, email: String!): User!
        }
        ```
    """
    func._graphql_mutation = True  # type: ignore[attr-defined]
    return classmethod(func)
