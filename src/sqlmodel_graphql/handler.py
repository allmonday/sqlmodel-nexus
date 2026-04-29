"""GraphQL execution handler for SQLModel entities."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from sqlmodel_graphql.discovery import EntityDiscovery
from sqlmodel_graphql.execution.query_executor import QueryExecutor
from sqlmodel_graphql.graphiql import GRAPHIQL_HTML
from sqlmodel_graphql.introspection import IntrospectionGenerator
from sqlmodel_graphql.loader.registry import LoaderRegistry
from sqlmodel_graphql.query_parser import QueryParser
from sqlmodel_graphql.sdl_generator import SDLGenerator
from sqlmodel_graphql.standard_queries import AutoQueryConfig, add_standard_queries

logger = logging.getLogger(__name__)


class GraphQLHandler:
    """Handles GraphQL query execution for SQLModel entities.

    Uses DataLoader for relationship resolution instead of SQLAlchemy eager loading.

    Example:
        ```python
        handler = GraphQLHandler(
            base=BaseEntity,
            session_factory=async_session,
            enable_pagination=True,
        )
        result = await handler.execute('{ users { id name posts { items { title } } } }')
        ```
    """

    def __init__(
        self,
        base: type,
        session_factory: Callable | None = None,
        query_description: str | None = None,
        mutation_description: str | None = None,
        auto_query_config: AutoQueryConfig | None = None,
        enable_pagination: bool = False,
    ):
        """Initialize the GraphQL handler.

        Args:
            base: SQLModel base class. All subclasses with @query/@mutation
                  decorators will be automatically discovered.
            session_factory: Async session factory for DataLoader queries.
                Required when entities have relationships.
                If auto_query_config is provided, its session_factory is used as fallback.
            query_description: Optional custom description for Query type.
            mutation_description: Optional custom description for Mutation type.
            auto_query_config: Optional AutoQueryConfig for auto-generating
                               standard queries (by_id, by_filter).
            enable_pagination: When True, list relationships return Result types
                with { items, pagination } wrapping.
        """
        if auto_query_config and not session_factory:
            session_factory = auto_query_config.session_factory

        self.session_factory = session_factory
        self.enable_pagination = enable_pagination

        # Discover entities with decorators and their related entities
        discovery = EntityDiscovery(base)
        self.entities = discovery.discover(include_all=auto_query_config is not None)

        # Add standard queries if auto_query_config is provided
        if auto_query_config is not None:
            add_standard_queries(self.entities, auto_query_config)

        # Build loader registry for DataLoader-based relationship resolution
        self._loader_registry = LoaderRegistry(
            self.entities,
            session_factory=session_factory,
            enable_pagination=enable_pagination,
        )

        # Initialize SDL generator
        self._sdl_generator = SDLGenerator(
            self.entities,
            query_description=query_description,
            mutation_description=mutation_description,
        )

        # Parse queries for field selection
        self._query_parser = QueryParser()

        # Scan for @query and @mutation methods
        from sqlmodel_graphql.scanning import MethodScanner

        self._scanner = MethodScanner()
        self._query_methods, self._mutation_methods = self._scanner.scan(self.entities)

        # Initialize introspection generator
        self._introspection_generator = IntrospectionGenerator(
            entities=self.entities,
            query_methods=self._query_methods,
            mutation_methods=self._mutation_methods,
            query_description=query_description,
            mutation_description=mutation_description,
            enable_pagination=enable_pagination,
            loader_registry=self._loader_registry,
        )

        # Initialize executor with DataLoader support
        self._executor = QueryExecutor(
            loader_registry=self._loader_registry,
            enable_pagination=enable_pagination,
            introspection_generator=self._introspection_generator,
        )

    def get_sdl(self) -> str:
        """Get the GraphQL Schema Definition Language string.

        Returns:
            SDL string representing the GraphQL schema.
        """
        return self._sdl_generator.generate(
            enable_pagination=self.enable_pagination,
            loader_registry=self._loader_registry,
        )

    def get_graphiql_html(self, endpoint: str = "/graphql") -> str:
        """Get the GraphiQL HTML template.

        Args:
            endpoint: GraphQL API endpoint URL. Defaults to "/graphql".

        Returns:
            HTML string for GraphiQL playground.
        """
        return GRAPHIQL_HTML.replace("{graphql_url}", endpoint)

    async def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        operation_name: str | None = None,
    ) -> dict[str, Any]:
        """Execute a GraphQL query.

        Args:
            query: GraphQL query string.
            variables: Optional variables for the query.
            operation_name: Optional operation name for multi-operation documents.

        Returns:
            Dictionary with 'data' and/or 'errors' keys.
        """
        try:
            self._query_parser.validate_no_aliases(query)

            # Parse the query to get field selections
            parsed_selections = self._query_parser.parse(query)

            # Execute via DataLoader-based executor
            return await self._executor.execute_query(
                query=query,
                variables=variables,
                operation_name=operation_name,
                parsed_selections=parsed_selections,
                query_methods=self._query_methods,
                mutation_methods=self._mutation_methods,
                entities=self.entities,
            )

        except Exception as e:
            logger.exception("GraphQL execution error")
            return {"errors": [{"message": str(e)}]}

    def _is_introspection_query(self, query: str) -> bool:
        """Check if the query is an introspection query."""
        return self._introspection_generator.is_introspection_query(query)

    def _execute_introspection(
        self, query: str, variables: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Execute an introspection query."""
        return self._introspection_generator.execute(query, variables)
