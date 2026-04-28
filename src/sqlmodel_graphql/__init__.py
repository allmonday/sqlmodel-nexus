"""SQLModel GraphQL - GraphQL SDL generation and Core API response building.

This package provides:
- Automatic GraphQL SDL generation from SQLModel classes
- @query/@mutation decorators for defining GraphQL operations
- DataLoader-based relationship resolution (replaces QueryMeta)
- Per-relationship pagination support
- DefineSubset for creating independent DTO models from SQLModel entities
- Resolver for building use case responses with resolve_/post_ methods

Example (GraphQL mode):
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

Example (Core API mode):
    ```python
    from sqlmodel_graphql import DefineSubset, Resolver, Loader, LoaderRegistry

    class UserDTO(DefineSubset):
        __subset__ = (User, ('id', 'name'))

    class PostDTO(DefineSubset):
        __subset__ = (Post, ('id', 'title', 'author_id'))
        author: UserDTO | None = None

        def resolve_author(self, loader=Loader('author')):
            return loader.load(self.author_id)

    registry = LoaderRegistry(entities=[User, Post], session_factory=session)
    result = await Resolver(registry).resolve([PostDTO(...) for p in posts])
    ```
"""

from __future__ import annotations

__version__ = "0.14.0"

from sqlmodel_graphql.context import AutoLoad, Collector, ExposeAs, SendTo
from sqlmodel_graphql.decorator import mutation, query
from sqlmodel_graphql.er_diagram import ErDiagram
from sqlmodel_graphql.handler import GraphQLHandler
from sqlmodel_graphql.loader import LoaderRegistry
from sqlmodel_graphql.query_parser import FieldSelection, QueryParser
from sqlmodel_graphql.relationship import Relationship
from sqlmodel_graphql.resolver import Loader, Resolver
from sqlmodel_graphql.sdl_generator import SDLGenerator
from sqlmodel_graphql.standard_queries import AutoQueryConfig, add_standard_queries
from sqlmodel_graphql.subset import DefineSubset, SubsetConfig

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
    "LoaderRegistry",
    # Types
    "FieldSelection",
    # Standard queries
    "AutoQueryConfig",
    "add_standard_queries",
    # Core API mode (use case response building)
    "DefineSubset",
    "SubsetConfig",
    "Resolver",
    "Loader",
    "AutoLoad",
    "ExposeAs",
    "SendTo",
    "Collector",
    # Custom relationships
    "Relationship",
    "ErDiagram",
]
