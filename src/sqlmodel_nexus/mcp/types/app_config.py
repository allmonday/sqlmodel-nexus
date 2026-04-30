"""App configuration types for multi-app MCP support."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from sqlmodel import SQLModel


class AppConfig(TypedDict, total=False):
    """Configuration for a single GraphQL application.

    Attributes:
        name: Unique identifier for the application (e.g., "blog", "shop")
        base: SQLModel base class for this application
        description: Human-readable description of the application
        session_factory: Async session factory for DataLoader relationship loading
        query_description: Description for the Query type in GraphQL schema
        mutation_description: Description for the Mutation type in GraphQL schema
    """

    name: str
    base: type[SQLModel]
    description: str | None
    session_factory: Callable | None
    query_description: str | None
    mutation_description: str | None
