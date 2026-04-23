"""SQLModel GraphQL - GraphQL SDL generation and DataLoader-based query execution.

This package provides:
- Automatic GraphQL SDL generation from SQLModel classes
- @query/@mutation decorators for defining GraphQL operations
- DataLoader-based relationship resolution (replaces QueryMeta)
- Per-relationship pagination support

Example:
    ```python
    from sqlmodel import SQLModel, Field, Relationship, select
    from sqlmodel_graphql import query, mutation, GraphQLHandler

    class User(SQLModel, table=True):
        id: int = Field(primary_key=True)
        name: str
        posts: list["Post"] = Relationship(back_populates="author", order_by="id")

        @query
        async def get_users(cls, limit: int = 10) -> list['User']:
            stmt = select(cls).limit(limit)
            result = await session.exec(stmt)
            return list(result.all())

    handler = GraphQLHandler(
        base=User,
        session_factory=async_session,
        enable_pagination=True,
    )
    ```
"""

from __future__ import annotations

__version__ = "0.14.0"

from sqlmodel_graphql.decorator import mutation, query
from sqlmodel_graphql.handler import GraphQLHandler
from sqlmodel_graphql.query_parser import FieldSelection, QueryParser
from sqlmodel_graphql.sdl_generator import SDLGenerator
from sqlmodel_graphql.standard_queries import AutoQueryConfig, add_standard_queries

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
    "FieldSelection",
    # Standard queries
    "AutoQueryConfig",
    "add_standard_queries",
]
