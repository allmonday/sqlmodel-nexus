"""SQLModel GraphQL - GraphQL SDL generation and query optimization for SQLModel.

This package provides:
- Automatic GraphQL SDL generation from SQLModel classes
- @query/@mutation decorators for defining GraphQL operations
- QueryMeta extraction from GraphQL queries for query optimization
- SQLAlchemy query optimization via to_options()

Example:
    ```python
    from sqlmodel import SQLModel, Field, Relationship, select
    from sqlmodel_graphql import query, mutation, SDLGenerator, QueryParser

    class User(SQLModel, table=True):
        id: int = Field(primary_key=True)
        name: str
        posts: list["Post"] = Relationship(back_populates="author")

        @query(name='users')
        async def get_all(cls, query_meta: QueryMeta = None) -> list['User']:
            stmt = select(cls)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            return await fetch_users(stmt)

    # Generate SDL
    generator = SDLGenerator([User, Post])
    print(generator.generate())
    ```
"""

from __future__ import annotations

__version__ = "0.1.0"

from sqlmodel_graphql.decorator import mutation, query
from sqlmodel_graphql.handler import GraphQLHandler
from sqlmodel_graphql.query_parser import QueryParser
from sqlmodel_graphql.sdl_generator import SDLGenerator
from sqlmodel_graphql.types import FieldSelection, QueryMeta, RelationshipSelection

__all__ = [
    # Version
    "__version__",
    # Decorators
    "query",
    "mutation",
    # Core classes
    "SDLGenerator",
    "QueryParser",
    "GraphQLHandler",
    # Types
    "QueryMeta",
    "FieldSelection",
    "RelationshipSelection",
]
