"""Decorators for marking SQLModel methods as GraphQL queries and mutations."""

from __future__ import annotations

from collections.abc import Callable
from typing import overload


@overload
def query(func: Callable) -> classmethod: ...


@overload
def query(
    *, name: str | None = None, description: str | None = None
) -> Callable[[Callable], classmethod]: ...


def query(
    name_or_func: Callable | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
) -> classmethod | Callable[[Callable], classmethod]:
    """Mark a method as a GraphQL query.

    This decorator automatically converts the method to a classmethod.

    Args:
        name_or_func: Function object (when called without parameters) or None.
        name: GraphQL query name (defaults to camelCase conversion of method name).
        description: Description text in GraphQL Schema.

    Returns:
        A classmethod decorator.

    Example:
        ```python
        from sqlmodel import SQLModel
        from sqlmodel_graphql import query

        class User(SQLModel, table=True):
            id: int
            name: str

            @query(name='users', description='Get all users')
            async def get_all(cls, limit: int = 10) -> list['User']:
                return await fetch_users(limit)
        ```

    This generates the following GraphQL Schema:
        ```graphql
        type Query {
            users(limit: Int): [User!]!
        }
        ```
    """
    # Handle @query without parameters
    if callable(name_or_func):
        func = name_or_func
        func._graphql_query = True  # type: ignore[attr-defined]
        func._graphql_query_name = name  # type: ignore[attr-defined]
        func._graphql_query_description = description  # type: ignore[attr-defined]
        return classmethod(func)

    # Handle @query(name='...', description='...')
    query_name = name or name_or_func

    def decorator(func: Callable) -> classmethod:
        func._graphql_query = True  # type: ignore[attr-defined]
        func._graphql_query_name = query_name  # type: ignore[attr-defined]
        func._graphql_query_description = description  # type: ignore[attr-defined]
        return classmethod(func)

    return decorator


@overload
def mutation(func: Callable) -> classmethod: ...


@overload
def mutation(
    *, name: str | None = None, description: str | None = None
) -> Callable[[Callable], classmethod]: ...


def mutation(
    name_or_func: Callable | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
) -> classmethod | Callable[[Callable], classmethod]:
    """Mark a method as a GraphQL mutation.

    This decorator automatically converts the method to a classmethod.

    Args:
        name_or_func: Function object (when called without parameters) or None.
        name: GraphQL mutation name (defaults to camelCase conversion of method name).
        description: Description text in GraphQL Schema.

    Returns:
        A classmethod decorator.

    Example:
        ```python
        from sqlmodel import SQLModel
        from sqlmodel_graphql import mutation

        class User(SQLModel, table=True):
            id: int
            name: str
            email: str

            @mutation(name='createUser', description='Create a new user')
            async def create(cls, name: str, email: str) -> 'User':
                return await create_user(name, email)
        ```

    This generates the following GraphQL Schema:
        ```graphql
        type Mutation {
            createUser(name: String!, email: String!): User!
        }
        ```
    """
    # Handle @mutation without parameters
    if callable(name_or_func):
        func = name_or_func
        func._graphql_mutation = True  # type: ignore[attr-defined]
        func._graphql_mutation_name = name  # type: ignore[attr-defined]
        func._graphql_mutation_description = description  # type: ignore[attr-defined]
        return classmethod(func)

    # Handle @mutation(name='...', description='...')
    mutation_name = name or name_or_func

    def decorator(func: Callable) -> classmethod:
        func._graphql_mutation = True  # type: ignore[attr-defined]
        func._graphql_mutation_name = mutation_name  # type: ignore[attr-defined]
        func._graphql_mutation_description = description  # type: ignore[attr-defined]
        return classmethod(func)

    return decorator
