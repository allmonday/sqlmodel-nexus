"""GraphQL execution handler for SQLModel entities."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Callable

from graphql import parse

from sqlmodel_graphql.introspection import IntrospectionGenerator
from sqlmodel_graphql.query_parser import QueryParser
from sqlmodel_graphql.sdl_generator import SDLGenerator

if TYPE_CHECKING:
    from sqlmodel import SQLModel


def _serialize_value(value: Any) -> Any:
    """Serialize a value for JSON response.

    Handles SQLModel instances, lists, and basic types.
    """
    if value is None:
        return None

    # Handle SQLModel instances
    if hasattr(value, "model_dump"):
        return value.model_dump()

    # Handle lists
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]

    # Handle dicts
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}

    # Basic types (int, str, bool, float)
    return value


class GraphQLHandler:
    """Handles GraphQL query execution for SQLModel entities.

    This class scans entities for @query and @mutation decorators,
    builds a GraphQL schema, and executes queries against it.

    Example:
        ```python
        from sqlmodel import SQLModel
        from sqlmodel_graphql import GraphQLHandler, query

        class User(SQLModel, table=True):
            id: int
            name: str

            @query(name='users')
            async def get_all(cls) -> list['User']:
                return await fetch_users()

        handler = GraphQLHandler(entities=[User])
        result = await handler.execute('{ users { id name } }')
        ```
    """

    def __init__(self, entities: list[type[SQLModel]]):
        """Initialize the GraphQL handler.

        Args:
            entities: List of SQLModel classes with @query/@mutation decorators.
        """
        self.entities = entities
        self._sdl_generator = SDLGenerator(entities)
        self._query_parser = QueryParser()

        # Build method mappings: field_name -> (entity, method)
        self._query_methods: dict[str, tuple[type[SQLModel], Callable[..., Any]]] = {}
        self._mutation_methods: dict[str, tuple[type[SQLModel], Callable[..., Any]]] = {}

        self._scan_methods()

        # Initialize introspection generator
        self._introspection_generator = IntrospectionGenerator(
            entities=entities,
            query_methods=self._query_methods,
            mutation_methods=self._mutation_methods,
        )

    def _scan_methods(self) -> None:
        """Scan all entities for @query and @mutation methods."""
        for entity in self.entities:
            for name in dir(entity):
                try:
                    attr = getattr(entity, name)
                    if not callable(attr):
                        continue

                    # Check for @query decorator
                    if hasattr(attr, "_graphql_query"):
                        func = attr.__func__ if hasattr(attr, "__func__") else attr
                        gql_name = getattr(func, "_graphql_query_name", None)
                        if gql_name is None:
                            gql_name = func.__name__
                        self._query_methods[gql_name] = (entity, attr)

                    # Check for @mutation decorator
                    if hasattr(attr, "_graphql_mutation"):
                        func = attr.__func__ if hasattr(attr, "__func__") else attr
                        gql_name = getattr(func, "_graphql_mutation_name", None)
                        if gql_name is None:
                            gql_name = func.__name__
                        self._mutation_methods[gql_name] = (entity, attr)

                except Exception:
                    continue

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
                return await self._execute_introspection(query, variables)

            # Parse the query to get field selection info
            parsed = self._query_parser.parse(query)

            # Execute regular query
            return await self._execute_query(query, variables, operation_name, parsed)

        except Exception as e:
            return {"errors": [{"message": str(e)}]}

    def _is_introspection_query(self, query: str) -> bool:
        """Check if the query is an introspection query."""
        return "__schema" in query or "__type" in query

    async def _execute_introspection(
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
        from graphql import FieldNode, OperationDefinitionNode, parse

        document = parse(query)
        data: dict[str, Any] = {}
        errors: list[dict[str, Any]] = []

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
                                errors.append(
                                    {
                                        "message": f"Cannot query field '{field_name}' on type '{op_type.title()}'",
                                        "path": [field_name],
                                    }
                                )
                                continue

                            entity, method = method_info

                            # Build arguments
                            args = self._build_arguments(
                                selection, variables, method, entity
                            )

                            # Add query_meta if available (only for queries, not mutations)
                            if op_type == "query" and field_name in parsed_meta:
                                args["query_meta"] = parsed_meta[field_name]

                            # Execute the method
                            result = method(**args)
                            if inspect.isawaitable(result):
                                result = await result

                            # Serialize the result
                            data[field_name] = _serialize_value(result)

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

    def _build_arguments(
        self,
        selection: Any,
        variables: dict[str, Any] | None,
        method: Callable[..., Any],
        entity: type[SQLModel],
    ) -> dict[str, Any]:
        """Build method arguments from GraphQL field arguments.

        Args:
            selection: GraphQL FieldNode with argument info.
            variables: GraphQL variables dict.
            method: The method to call.
            entity: The SQLModel entity class.

        Returns:
            Dictionary of argument name to value.
        """
        args: dict[str, Any] = {}
        variables = variables or {}

        if not selection.arguments:
            return args

        # Get method signature for type info
        func = method.__func__ if hasattr(method, "__func__") else method
        sig = inspect.signature(func)

        for arg in selection.arguments:
            arg_name = arg.name.value

            # Get the value (from literal or variable)
            if hasattr(arg.value, "value"):
                # Literal value
                value = arg.value.value
            elif hasattr(arg.value, "name"):
                # Variable reference
                var_name = arg.value.name.value
                value = variables.get(var_name)
            else:
                value = arg.value

            # Use argument name directly
            param_name = arg_name

            # Check if this param exists in the method signature
            if param_name in sig.parameters:
                args[param_name] = value
            elif arg_name in sig.parameters:
                args[arg_name] = value

        return args
