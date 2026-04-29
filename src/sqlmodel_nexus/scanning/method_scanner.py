"""Method scanning for GraphQL decorators."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlmodel_nexus.utils.naming import to_graphql_field_name


class MethodScanner:
    """Scans entities for @query and @mutation methods."""

    def __init__(self) -> None:
        """Initialize the scanner."""
        self._name_mapping: dict[str, tuple[str, str]] = {}

    def scan(
        self,
        entities: list[type],
    ) -> tuple[
        dict[str, tuple[type, Callable[..., Any]]],
        dict[str, tuple[type, Callable[..., Any]]],
    ]:
        """Scan all entities for @query and @mutation methods.

        Args:
            entities: List of entity classes to scan.

        Returns:
            Tuple of (query_methods, mutation_methods) where each is a
            mapping of GraphQL field names to (entity, method) tuples.
            Field names are generated as: {entityName}{MethodName} (e.g., userGetAll).
        """
        query_methods: dict[str, tuple[type, Callable[..., Any]]] = {}
        mutation_methods: dict[str, tuple[type, Callable[..., Any]]] = {}
        self._name_mapping = {}

        for entity in entities:
            for method_name in dir(entity):
                try:
                    attr = getattr(entity, method_name)
                    if not callable(attr):
                        continue

                    # Check for @query decorator
                    if hasattr(attr, "_graphql_query"):
                        func = attr.__func__ if hasattr(attr, "__func__") else attr
                        # Generate GraphQL field name: entityName + MethodName
                        gql_name = to_graphql_field_name(entity.__name__, func.__name__)

                        query_methods[gql_name] = (entity, attr)
                        self._name_mapping[gql_name] = (entity.__name__, func.__name__)

                    # Check for @mutation decorator
                    if hasattr(attr, "_graphql_mutation"):
                        func = attr.__func__ if hasattr(attr, "__func__") else attr
                        # Generate GraphQL field name: entityName + MethodName
                        gql_name = to_graphql_field_name(entity.__name__, func.__name__)

                        mutation_methods[gql_name] = (entity, attr)
                        self._name_mapping[gql_name] = (entity.__name__, func.__name__)

                except Exception:
                    continue

        return query_methods, mutation_methods

    def get_name_mapping(self) -> dict[str, tuple[str, str]]:
        """Get the mapping from GraphQL names to original names.

        Returns:
            Dictionary mapping GraphQL field names to
            (entity_name, original_method_name) tuples.
        """
        return self._name_mapping.copy()
