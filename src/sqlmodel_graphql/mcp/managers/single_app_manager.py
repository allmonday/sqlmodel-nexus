"""Single-application manager for MCP support."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel_graphql.handler import GraphQLHandler
from sqlmodel_graphql.mcp.builders.type_tracer import TypeTracer

if TYPE_CHECKING:
    from sqlmodel import SQLModel


class SingleAppManager:
    """Manages a single GraphQL application without multi-app overhead.

    This class provides a simplified interface for single-app scenarios,
    eliminating the need for app routing and discovery.

    Unlike MultiAppManager, this manager:
    - Does not require app_name routing
    - Provides direct access to handler, tracer, and SDL generator
    - Is designed for single-database scenarios
    """

    def __init__(
        self,
        base: type[SQLModel],
        description: str | None = None,
    ):
        """Initialize the single-app manager.

        Args:
            base: SQLModel base class. All subclasses with @query/@mutation
                  decorators will be automatically discovered.
            description: Optional description for the GraphQL schema
                        (used for both Query and Mutation type descriptions)

        Example:
            ```python
            class BaseEntity(SQLModel):
                pass

            manager = SingleAppManager(
                base=BaseEntity,
                description="Blog system with users and posts"
            )

            # Access handler for query execution
            result = await manager.handler.execute("{ users { id name } }")

            # Get SDL
            sdl = manager.sdl_generator.generate()
            ```
        """
        # Create GraphQL handler for this app
        self.handler = GraphQLHandler(
            base=base,
            query_description=description,
            mutation_description=description,
        )

        # Create type tracer for schema introspection
        introspection_data = self.handler._introspection_generator.generate()
        entity_names = {e.__name__ for e in self.handler.entities}
        self.tracer = TypeTracer(introspection_data, entity_names)

        # Reference to SDL generator
        self.sdl_generator = self.handler._sdl_generator

    @property
    def entity_names(self) -> set[str]:
        """Get the set of entity names in this application.

        Returns:
            Set of entity class names (e.g., {"User", "Post", "Comment"})
        """
        return {e.__name__ for e in self.handler.entities}
