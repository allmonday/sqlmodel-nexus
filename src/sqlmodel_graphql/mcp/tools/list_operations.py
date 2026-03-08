"""list_queries and list_mutations MCP tools.

These tools provide the first layer of progressive disclosure,
returning only operation names and descriptions to minimize context usage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlmodel_graphql.mcp.types.errors import create_success_response

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from sqlmodel_graphql.mcp.builders.type_tracer import TypeTracer


def register_list_operations_tools(mcp: "FastMCP", tracer: "TypeTracer") -> None:
    """Register list_queries and list_mutations tools with the MCP server.

    Args:
        mcp: The FastMCP server instance.
        tracer: The TypeTracer instance.
    """

    @mcp.tool()
    def list_queries() -> dict[str, Any]:
        """List all available GraphQL queries.

        Returns a lightweight list of query names and descriptions.
        Use this tool first to discover available queries, then use
        get_query_schema to get detailed information about a specific query.

        Returns:
            Dictionary containing:
            - success: True
            - data: List of query info dictionaries with name and description

        Example response:
            {
                "success": true,
                "data": [
                    {"name": "users", "description": "Get all users"},
                    {"name": "user", "description": "Get user by ID"}
                ]
            }
        """
        try:
            queries = tracer.list_operation_fields("Query")
            return create_success_response(queries)
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "internal_error",
            }

    @mcp.tool()
    def list_mutations() -> dict[str, Any]:
        """List all available GraphQL mutations.

        Returns a lightweight list of mutation names and descriptions.
        Use this tool first to discover available mutations, then use
        get_mutation_schema to get detailed information about a specific mutation.

        Returns:
            Dictionary containing:
            - success: True
            - data: List of mutation info dictionaries with name and description

        Example response:
            {
                "success": true,
                "data": [
                    {"name": "createUser", "description": "Create a new user"},
                    {"name": "updateUser", "description": "Update user information"}
                ]
            }
        """
        try:
            mutations = tracer.list_operation_fields("Mutation")
            return create_success_response(mutations)
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "internal_error",
            }
