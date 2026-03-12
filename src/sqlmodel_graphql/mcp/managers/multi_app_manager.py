"""Multi-application manager for MCP support."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel_graphql.handler import GraphQLHandler
from sqlmodel_graphql.mcp.builders.type_tracer import TypeTracer
from sqlmodel_graphql.mcp.managers.app_resources import AppResources
from sqlmodel_graphql.mcp.types.app_config import AppConfig

if TYPE_CHECKING:
    pass


class MultiAppManager:
    """Manages multiple GraphQL applications in a single MCP server.

    This class is responsible for:
    - Initializing and storing resources for each application
    - Routing tool calls to the correct application
    - Providing app discovery functionality
    """

    def __init__(self, apps: list[AppConfig]):
        """Initialize the multi-app manager.

        Args:
            apps: List of application configurations

        Example:
            ```python
            apps = [
                {"name": "blog", "base": BlogBaseEntity, "description": "Blog API"},
                {"name": "shop", "base": ShopBaseEntity, "description": "Shop API"}
            ]
            manager = MultiAppManager(apps)
            ```
        """
        self.apps: dict[str, AppResources] = {}

        # Initialize each application
        for app_config in apps:
            resources = self._create_app_resources(app_config)
            self.apps[app_config["name"]] = resources

    def _create_app_resources(self, config: AppConfig) -> AppResources:
        """Create resources for a single application.

        Args:
            config: Application configuration

        Returns:
            AppResources instance with handler, tracer, and SDL generator
        """
        # Create GraphQL handler for this app
        handler = GraphQLHandler(
            base=config["base"],
            query_description=config.get("query_description"),
            mutation_description=config.get("mutation_description"),
        )

        # Create type tracer for progressive disclosure
        introspection_data = handler._introspection_generator.generate()
        entity_names = {e.__name__ for e in handler.entities}
        tracer = TypeTracer(introspection_data, entity_names)

        # Create AppResources container
        return AppResources(
            name=config["name"],
            description=config.get("description", ""),
            handler=handler,
            tracer=tracer,
            sdl_generator=handler._sdl_generator,
        )

    def get_app(self, name: str) -> AppResources:
        """Get resources for a specific application.

        Args:
            name: Application name (required)

        Returns:
            AppResources for the specified application

        Raises:
            ValueError: If application name is not found

        Example:
            ```python
            app = manager.get_app("blog")
            queries = app.tracer.list_operation_fields("Query")
            ```
        """
        # Try exact match first
        if name in self.apps:
            return self.apps[name]

        # Smart fallback: try removing common suffixes
        # Handle cases like "todos_app" -> "todos", "blog_app" -> "blog"
        normalized_name = name
        if normalized_name.endswith("_app"):
            normalized_name = normalized_name[:-4]  # Remove "_app"
        elif normalized_name.endswith("-app"):
            normalized_name = normalized_name[:-4]  # Remove "-app"

        if normalized_name in self.apps:
            return self.apps[normalized_name]

        # No match found, provide helpful error message
        available = list(self.apps.keys())
        raise ValueError(
            f"App '{name}' not found. Available apps: {available}"
        )

    def list_apps(self) -> list[str]:
        """List all available application names.

        Returns:
            List of application names

        Example:
            ```python
            app_names = manager.list_apps()
            # ["blog", "shop"]
            ```
        """
        return list(self.apps.keys())
