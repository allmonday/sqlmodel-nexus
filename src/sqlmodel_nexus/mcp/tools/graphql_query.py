"""graphql_query MCP tool.

Executes GraphQL queries directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlmodel_nexus.mcp.types.errors import (
    MCPErrors,
    create_error_response,
    create_success_response,
)

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from sqlmodel_nexus.handler import GraphQLHandler


def register_graphql_query_tool(mcp: FastMCP, handler: GraphQLHandler) -> None:
    """Register the graphql_query tool with the MCP server.

    Args:
        mcp: The FastMCP server instance.
        handler: The GraphQLHandler instance.
    """

    @mcp.tool()
    async def graphql_query(query: str) -> dict[str, Any]:
        """Execute a GraphQL query.

        Use this tool to execute GraphQL queries after discovering available
        operations with list_queries and understanding their schema with
        get_query_schema.

        Args:
            query: A GraphQL query string.

        Returns:
            Dictionary containing:
            - success: True if query succeeded
            - data: The query result (if successful)
            - error: Error message (if failed)
            - error_type: Type of error (if failed)

        Examples:
            # Simple query
            graphql_query(query="{ users(limit: 10) { id name email } }")

            # Query with nested fields
            graphql_query(query="{ user(id: 1) { id name posts { title } } }")

            # Multiple operations in one query
            graphql_query(query="{ users { id name } posts { id title } }")
        """
        try:
            # Validate input
            if not query or not query.strip():
                return create_error_response(
                    "query is required and cannot be empty",
                    MCPErrors.MISSING_REQUIRED_FIELD,
                )

            # Execute the query
            result = await handler.execute(query)

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
            data = result.get("data")
            return create_success_response(data)

        except Exception as e:
            return create_error_response(
                str(e),
                MCPErrors.INTERNAL_ERROR,
            )
