"""get_query_schema and get_mutation_schema MCP tools.

These tools provide the second layer of progressive disclosure,
returning operation details and related type introspection data.

Supports two output formats:
- "sdl" (default): Schema Definition Language format, more compact
- "introspection": Full GraphQL introspection format
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from sqlmodel_graphql.mcp.builders.introspection_to_sdl import IntrospectionToSDL
from sqlmodel_graphql.mcp.types.errors import (
    MCPErrors,
    create_error_response,
    create_success_response,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from sqlmodel_graphql.mcp.builders.type_tracer import TypeTracer


def register_get_operation_schema_tools(
    mcp: "FastMCP", tracer: "TypeTracer"
) -> None:
    """Register get_query_schema and get_mutation_schema tools with the MCP server.

    Args:
        mcp: The FastMCP server instance.
        tracer: The TypeTracer instance.
    """

    @mcp.tool()
    def get_query_schema(
        name: str,
        response_type: Literal["sdl", "introspection"] = "sdl"
    ) -> dict[str, Any]:
        """Get detailed schema information for a specific GraphQL query.

        Returns the query's arguments, return type, and related entity types.
        Use this after list_queries to get detailed information before executing a query.

        Args:
            name: The name of the query (e.g., "users", "user").
            response_type: Output format - "sdl" (default, compact) or "introspection" (full).

        Returns:
            Dictionary containing:
            - success: True if found, False otherwise
            - data: (if successful) Dictionary with:
                - sdl: (when response_type="sdl") SDL format string
                - operation: (when response_type="introspection") Query introspection
                - types: (when response_type="introspection") Related type introspections
            - error: (if failed) Error message
            - error_type: (if failed) Error type

        Example SDL response:
            {
                "success": true,
                "data": {
                    "sdl": "# Query\\nusers(limit: Int): [User!]!\\n\\n# Related Types\\ntype User { ... }"
                }
            }

        Example introspection response:
            {
                "success": true,
                "data": {
                    "operation": {"name": "users", "args": [...], "type": {...}},
                    "types": [{"kind": "OBJECT", "name": "User", "fields": [...]}]
                }
            }
        """
        try:
            # Get the operation field
            operation = tracer.get_operation_field("Query", name)
            if operation is None:
                return create_error_response(
                    f"Query '{name}' not found",
                    MCPErrors.TYPE_NOT_FOUND,
                )

            # Collect related types from return type
            return_type = operation.get("type")
            related_type_names = tracer.collect_related_types(return_type)

            # Get introspection data for related types
            types = tracer.get_introspection_for_types(related_type_names)

            if response_type == "sdl":
                converter = IntrospectionToSDL()
                sdl = converter.convert_operation_with_types(
                    operation, types, "Query"
                )
                return create_success_response({"sdl": sdl})
            else:
                return create_success_response({
                    "operation": operation,
                    "types": types,
                })

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "internal_error",
            }

    @mcp.tool()
    def get_mutation_schema(
        name: str,
        response_type: Literal["sdl", "introspection"] = "sdl"
    ) -> dict[str, Any]:
        """Get detailed schema information for a specific GraphQL mutation.

        Returns the mutation's arguments, return type, and related entity types.
        Use this after list_mutations to get detailed information before executing a mutation.

        Args:
            name: The name of the mutation (e.g., "createUser", "updateUser").
            response_type: Output format - "sdl" (default, compact) or "introspection" (full).

        Returns:
            Dictionary containing:
            - success: True if found, False otherwise
            - data: (if successful) Dictionary with:
                - sdl: (when response_type="sdl") SDL format string
                - operation: (when response_type="introspection") Mutation introspection
                - types: (when response_type="introspection") Related type introspections
            - error: (if failed) Error message
            - error_type: (if failed) Error type

        Example SDL response:
            {
                "success": true,
                "data": {
                    "sdl": "# Mutation\\ncreateUser(name: String!, email: String!): User!\\n\\n# Related Types\\ntype User { ... }"
                }
            }

        Example introspection response:
            {
                "success": true,
                "data": {
                    "operation": {"name": "createUser", "args": [...], "type": {...}},
                    "types": [{"kind": "OBJECT", "name": "User", "fields": [...]}]
                }
            }
        """
        try:
            # Get the operation field
            operation = tracer.get_operation_field("Mutation", name)
            if operation is None:
                return create_error_response(
                    f"Mutation '{name}' not found",
                    MCPErrors.TYPE_NOT_FOUND,
                )

            # Collect related types from return type
            return_type = operation.get("type")
            related_type_names = tracer.collect_related_types(return_type)

            # Also collect types from input arguments
            for arg in operation.get("args", []):
                arg_types = tracer.collect_related_types(arg.get("type"))
                related_type_names.update(arg_types)

            # Get introspection data for related types
            types = tracer.get_introspection_for_types(related_type_names)

            if response_type == "sdl":
                converter = IntrospectionToSDL()
                sdl = converter.convert_operation_with_types(
                    operation, types, "Mutation"
                )
                return create_success_response({"sdl": sdl})
            else:
                return create_success_response({
                    "operation": operation,
                    "types": types,
                })

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "internal_error",
            }
