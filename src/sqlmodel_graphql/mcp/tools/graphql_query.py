"""graphql_query MCP tool.

Executes dynamic GraphQL queries based on field paths.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlmodel_graphql.mcp.builders.query_builder import GraphQLQueryBuilder
from sqlmodel_graphql.mcp.types.errors import (
    MCPError,
    MCPErrors,
    create_error_response,
    create_success_response,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from sqlmodel_graphql.handler import GraphQLHandler


def register_graphql_query_tool(mcp: FastMCP, handler: GraphQLHandler) -> None:
    """Register the graphql_query tool with the MCP server.

    Args:
        mcp: The FastMCP server instance.
        handler: The GraphQLHandler instance.
    """
    builder = GraphQLQueryBuilder()

    @mcp.tool()
    async def graphql_query(
        operation_name: str,
        arguments: dict[str, Any] | None,
        fields: list[str],
    ) -> dict[str, Any]:
        """Execute a GraphQL query dynamically.

        This tool allows you to query any GraphQL operation by specifying the operation name,
        optional arguments, and the fields you want to retrieve using dot notation.

        Args:
            operation_name: The name of the GraphQL query operation (e.g., "users", "user", "posts").
            arguments: Optional dictionary of arguments for the query (e.g., {"limit": 10, "id": 1}).
            fields: List of field paths to retrieve, using dot notation for nested fields.
                    For example: ["id", "name", "posts.title", "posts.author.name"]

        Returns:
            Dictionary with:
            - success: True if query succeeded
            - data: The query result (if successful)
            - error: Error message (if failed)
            - error_type: Type of error (if failed)

        Examples:
            # Simple query
            graphql_query(
                operation_name="users",
                arguments={"limit": 10},
                fields=["id", "name", "email"]
            )

            # Nested query
            graphql_query(
                operation_name="user",
                arguments={"id": 1},
                fields=["id", "name", "posts.title", "posts.comments.content"]
            )
        """
        try:
            # Validate inputs
            if not operation_name:
                return create_error_response(
                    "operation_name is required",
                    MCPErrors.MISSING_REQUIRED_FIELD,
                )

            if not fields:
                return create_error_response(
                    "At least one field must be specified",
                    MCPErrors.MISSING_REQUIRED_FIELD,
                )

            # Build the GraphQL query string
            query_str = builder.build_query(
                operation_name=operation_name,
                arguments=arguments,
                fields=fields,
                operation_type="query",
            )

            # Execute the query
            result = await handler.execute(query_str)

            # Check for GraphQL errors
            if "errors" in result:
                error_messages = [
                    err.get("message", "Unknown error")
                    for err in result["errors"]
                ]
                return create_error_response(
                    "; ".join(error_messages),
                    MCPErrors.QUERY_EXECUTION_ERROR,
                )

            # Return the data
            data = result.get("data", {}).get(operation_name)
            return create_success_response(data)

        except MCPError as e:
            return create_error_response(e)
        except Exception as e:
            return create_error_response(
                str(e),
                MCPErrors.INTERNAL_ERROR,
            )
