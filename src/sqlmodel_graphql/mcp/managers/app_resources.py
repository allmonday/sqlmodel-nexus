"""App resources container for multi-app MCP support."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlmodel_graphql.handler import GraphQLHandler
    from sqlmodel_graphql.mcp.builders.type_tracer import TypeTracer
    from sqlmodel_graphql.sdl_generator import SDLGenerator


@dataclass
class AppResources:
    """Container for all resources needed by a single GraphQL application.

    This class encapsulates all the components required to expose a single
    SQLModel application through the MCP interface:

    - GraphQLHandler: Executes GraphQL queries and mutations
    - TypeTracer: Traces related types for progressive disclosure
    - SDLGenerator: Generates GraphQL Schema Definition Language

    Attributes:
        name: Unique identifier for this application
        description: Human-readable description
        handler: GraphQLHandler instance for executing operations
        tracer: TypeTracer instance for type analysis
        sdl_generator: SDLGenerator instance for schema generation
    """

    name: str
    description: str
    handler: GraphQLHandler
    tracer: TypeTracer
    sdl_generator: SDLGenerator

    @property
    def entity_names(self) -> set[str]:
        """Get the set of entity names managed by this application.

        Returns:
            Set of entity class names
        """
        return {e.__name__ for e in self.handler.entities}
