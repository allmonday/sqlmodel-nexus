"""graphql_mutation MCP tool.

Executes GraphQL mutations directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlmodel_graphql.mcp.types.errors import (
    MCPErrors,
    create_error_response,
    create_success_response,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from sqlmodel_graphql.handler import GraphQLHandler


def register_graphql_mutation_tool(mcp: FastMCP, handler: GraphQLHandler) -> None:
    """Register the graphql_mutation tool with the MCP server.

    Args:
        mcp: The FastMCP server instance.
        handler: The GraphQLHandler instance.
    """

    @mcp.tool()
    async def graphql_mutation(query: str) -> dict[str, Any]:
        """Execute a GraphQL mutation.

        Use this tool to execute GraphQL mutations after discovering available
        operations with list_mutations and understanding their schema with
        get_mutation_schema.

        Args:
            query: A GraphQL mutation string.

        Returns:
            Dictionary containing:
            - success: True if mutation succeeded
            - data: The mutation result (if successful)
            - error: Error message (if failed)
            - error_type: Type of error (if failed)

        Examples:
            # Create a user
            graphql_mutation(query="mutation { createUser(name: \\"John\\", "
                         "email: \\"john@example.com\\") { id name email } }")

            # Create a post with nested author info
            graphql_mutation(query="mutation { createPost(title: \\"Hello\\", "
                         "content: \\"World\\", author_id: 1) { id title author { name } } }")
        """
        try:
            # Validate input
            if not query or not query.strip():
                return create_error_response(
                    "query is required and cannot be empty",
                    MCPErrors.MISSING_REQUIRED_FIELD,
                )

            # Execute the mutation
            result = await handler.execute(query)

            # Check for GraphQL errors
            if "errors" in result:
                error_messages = [
                    err.get("message", "Unknown error")
                    for err in result["errors"]
                ]
                return create_error_response(
                    "; ".join(error_messages),
                    MCPErrors.MUTATION_EXECUTION_ERROR,
                )

            # Return the data
            data = result.get("data")
            return create_success_response(data)

        except Exception as e:
            return create_error_response(
                str(e),
                MCPErrors.INTERNAL_ERROR,
            )
