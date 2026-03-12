"""GraphQL execution handler for SQLModel entities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlmodel_graphql.discovery import EntityDiscovery
from sqlmodel_graphql.introspection import IntrospectionGenerator
from sqlmodel_graphql.query_parser import QueryParser
from sqlmodel_graphql.scanning import MethodScanner
from sqlmodel_graphql.sdl_generator import SDLGenerator

if TYPE_CHECKING:
    from sqlmodel import SQLModel


class GraphQLHandler:
    """Handles GraphQL query execution for SQLModel entities.

    This class scans entities for @query and @mutation decorators,
    builds a GraphQL schema, and executes queries against it.

    Example:
        ```python
        from sqlmodel import SQLModel
        from sqlmodel_graphql import GraphQLHandler, query

        # Define a base class for your entities
        class BaseEntity(SQLModel):
            pass

        class User(BaseEntity, table=True):
            id: int
            name: str

            @query(name='users')
            async def get_all(cls) -> list['User']:
                return await fetch_users()

        # Create handler with base class - auto-discovers all entities
        handler = GraphQLHandler(base=BaseEntity)
        result = await handler.execute('{ users { id name } }')
        ```
    """

    def __init__(
        self,
        base: type[SQLModel],
        query_description: str | None = None,
        mutation_description: str | None = None,
    ):
        """Initialize the GraphQL handler.

        Args:
            base: SQLModel base class. All subclasses with @query/@mutation
                  decorators will be automatically discovered.
            query_description: Optional custom description for Query type.
            mutation_description: Optional custom description for Mutation type.
        """
        # Discover entities with decorators and their related entities
        discovery = EntityDiscovery(base)
        self.entities = discovery.discover()

        # Initialize SDL generator
        self._sdl_generator = SDLGenerator(
            self.entities,
            query_description=query_description,
            mutation_description=mutation_description,
        )

        # Parse queries for field selection optimization
        self._query_parser = QueryParser()

        # Scan for @query and @mutation methods
        self._scanner = MethodScanner()
        self._query_methods, self._mutation_methods = self._scanner.scan(self.entities)
        self._name_mapping = self._scanner.get_name_mapping()

        # Initialize introspection generator
        self._introspection_generator = IntrospectionGenerator(
            entities=self.entities,
            query_methods=self._query_methods,
            mutation_methods=self._mutation_methods,
            query_description=query_description,
            mutation_description=mutation_description,
        )

    def get_sdl(self) -> str:
        """Get the GraphQL Schema Definition Language string.

        Returns:
            SDL string representing the GraphQL schema.
        """
        return self._sdl_generator.generate()

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
            # Check if this is an introspection query
            if self._is_introspection_query(query):
                return self._execute_introspection(query, variables)

            # Parse the query to get field selection info
            parsed = self._query_parser.parse(query)

            # Execute regular query
            return await self._execute_query(
                query, variables, operation_name, parsed
            )

        except Exception as e:
            return {"errors": [{"message": str(e)}]}

    def _is_introspection_query(self, query: str) -> bool:
        """Check if the query is an introspection query."""
        return "__schema" in query or "__type" in query

    def _execute_introspection(
        self, query: str, variables: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Execute an introspection query.

        Args:
            query: GraphQL introspection query string.
            variables: Optional variables.

        Returns:
            Introspection result dictionary.
        """
        return self._introspection_generator.execute(query)

    async def _execute_query(
        self,
        query: str,
        variables: dict[str, Any] | None,
        operation_name: str | None,
        parsed_meta: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a regular GraphQL query.

        Args:
            query: GraphQL query string.
            variables: Optional variables.
            operation_name: Optional operation name.
            parsed_meta: Parsed QueryMeta from the query.

        Returns:
            Query result dictionary.
        """
        import inspect

        from graphql import FieldNode, OperationDefinitionNode, parse

        from sqlmodel_graphql.execution import ArgumentBuilder, FieldTreeBuilder
        from sqlmodel_graphql.response_builder import serialize_with_model

        document = parse(query)
        data: dict[str, Any] = {}
        errors: list[dict[str, Any]] = []

        argument_builder = ArgumentBuilder()
        field_tree_builder = FieldTreeBuilder()

        for definition in document.definitions:
            if isinstance(definition, OperationDefinitionNode):
                op_type = definition.operation.value  # 'query' or 'mutation'

                for selection in definition.selection_set.selections:
                    if isinstance(selection, FieldNode):
                        field_name = selection.name.value

                        try:
                            # Get the method for this field
                            if op_type == "query":
                                method_info = self._query_methods.get(field_name)
                            else:
                                method_info = self._mutation_methods.get(field_name)

                            if method_info is None:
                                op_name = op_type.title()
                                msg = f"Cannot query field '{field_name}' on type '{op_name}'"
                                errors.append(
                                    {
                                        "message": msg,
                                        "path": [field_name],
                                    }
                                )
                                continue

                            entity, method = method_info

                            # Build arguments
                            entity_names = {e.__name__ for e in self.entities}
                            args = argument_builder.build_arguments(
                                selection, variables, method, entity, entity_names
                            )

                            # Add query_meta if available
                            # For queries: always pass query_meta
                            # For mutations: only pass query_meta if return type is an entity
                            if field_name in parsed_meta:
                                if op_type == "query":
                                    args["query_meta"] = parsed_meta[field_name]
                                elif op_type == "mutation":
                                    from sqlmodel_graphql.utils.type_utils import (
                                        get_return_entity_type,
                                    )

                                    return_entity = get_return_entity_type(
                                        method, self.entities
                                    )
                                    if return_entity is not None:
                                        args["query_meta"] = parsed_meta[field_name]

                            # Execute the method
                            result = method(**args)
                            if inspect.isawaitable(result):
                                result = await result

                            # Extract requested fields from selection set
                            requested_fields = field_tree_builder.build_field_tree(
                                selection
                            )

                            # Serialize using dynamic Pydantic model (filters FK fields)
                            data[field_name] = serialize_with_model(
                                result,
                                entity=entity,
                                field_tree=requested_fields,
                            )

                        except Exception as e:
                            errors.append(
                                {"message": str(e), "path": [field_name]}
                            )

        response: dict[str, Any] = {}
        if data:
            response["data"] = data
        if errors:
            response["errors"] = errors

        return response
