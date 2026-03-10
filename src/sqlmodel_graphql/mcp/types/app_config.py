"""App configuration types for multi-app MCP support."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from sqlmodel import SQLModel


class AppConfig(TypedDict, total=False):
    """Configuration for a single GraphQL application.

    Attributes:
        name: Unique identifier for the application (e.g., "blog", "shop")
        base: SQLModel base class for this application
        description: Human-readable description of the application
        query_description: Description for the Query type in GraphQL schema
        mutation_description: Description for the Mutation type in GraphQL schema
    """

    name: str
    base: type[SQLModel]
    description: str | None
    query_description: str | None
    mutation_description: str | None
