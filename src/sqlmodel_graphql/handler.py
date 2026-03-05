"""GraphQL execution handler for SQLModel entities."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from graphql import parse

from sqlmodel_graphql.introspection import IntrospectionGenerator
from sqlmodel_graphql.query_parser import QueryParser
from sqlmodel_graphql.sdl_generator import SDLGenerator

if TYPE_CHECKING:
    from sqlmodel import SQLModel


def _serialize_value(
    value: Any,
    include: set[str] | dict[str, Any] | None = None
) -> Any:
    """Serialize a value for JSON response.

    Handles SQLModel instances, lists, and basic types.

    Args:
        value: The value to serialize.
        include: Can be:
            - None: Include all fields
            - set[str]: Include only these field names (no nested selection)
            - dict[str, Any]: Field selection tree where keys are field names
                             and values are nested selection trees for relationships
    """
    if value is None:
        return None

    # Handle SQLModel instances
    if hasattr(value, "model_dump"):
        # Get base fields from model_dump
        result = value.model_dump()

        # Determine field selection
        if include is None:
            # Include all fields (including relationships)
            for field_name in dir(value):
                if not field_name.startswith('_') and field_name not in result:
                    field_value = getattr(value, field_name, None)
                    if field_value is not None and (
                        hasattr(field_value, "model_dump") or
                        isinstance(field_value, list)
                    ):
                        result[field_name] = _serialize_value(field_value)
        elif isinstance(include, dict):
            # Dict-based selection with nested field info
            # First, filter scalar fields
            result = {k: v for k, v in result.items() if k in include}

            # Then handle relationship fields
            for field_name, nested_include in include.items():
                if field_name not in result and hasattr(value, field_name):
                    field_value = getattr(value, field_name)
                    if field_value is not None:
                        result[field_name] = _serialize_value(field_value, nested_include)
        else:
            # Set-based selection (backward compatible)
            result = {k: v for k, v in result.items() if k in include}

            # Handle relationship fields
            for field_name in include:
                if field_name not in result and hasattr(value, field_name):
                    field_value = getattr(value, field_name)
                    if field_value is not None:
                        result[field_name] = _serialize_value(field_value)

        return result

    # Handle lists
    if isinstance(value, list):
        return [_serialize_value(item, include) for item in value]

    # Handle dicts
    if isinstance(value, dict):
        if include:
            if isinstance(include, dict):
                return {
                    k: _serialize_value(v, include.get(k))
                    for k, v in value.items()
                    if k in include
                }
            else:
                return {
                    k: _serialize_value(v)
                    for k, v in value.items()
                    if k in include
                }
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
        from graphql import FieldNode, OperationDefinitionNode

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

                            # Extract requested fields from selection set
                            requested_fields = self._build_field_tree(selection)

                            # Serialize the result, only including requested fields
                            data[field_name] = _serialize_value(result, include=requested_fields)

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

    def _build_field_tree(self, selection: Any) -> dict[str, Any] | None:
        """Build a field selection tree from a GraphQL FieldNode.

        Args:
            selection: GraphQL FieldNode with selection set.

        Returns:
            Dictionary where keys are field names and values are:
            - {} for scalar fields
            - {nested_field: ...} for relationship fields
            Returns None if no selection_set.
        """
        if not selection.selection_set:
            return None

        field_tree: dict[str, Any] = {}
        for field in selection.selection_set.selections:
            if hasattr(field, "name"):
                field_name = field.name.value
                if hasattr(field, "selection_set") and field.selection_set:
                    # It's a relationship field - recursively build nested tree
                    field_tree[field_name] = self._build_field_tree(field)
                else:
                    # It's a scalar field
                    field_tree[field_name] = None

        return field_tree

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
