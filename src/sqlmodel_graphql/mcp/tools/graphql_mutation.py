"""graphql_mutation MCP tool.

Executes dynamic GraphQL mutations.
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


def register_graphql_mutation_tool(mcp: FastMCP, handler: GraphQLHandler) -> None:
    """Register the graphql_mutation tool with the MCP server.

    Args:
        mcp: The FastMCP server instance.
        handler: The GraphQLHandler instance.
    """
    builder = GraphQLQueryBuilder()

    @mcp.tool()
    async def graphql_mutation(
        operation_name: str,
        arguments: dict[str, Any],
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute a GraphQL mutation dynamically.

        This tool allows you to execute any GraphQL mutation by specifying the mutation name,
        required arguments, and optional fields to retrieve from the result.

        Args:
            operation_name: The name of the GraphQL mutation (e.g., "create_user", "create_post").
            arguments: Dictionary of arguments for the mutation (e.g., {"name": "John", "email": "john@example.com"}).
            fields: Optional list of field paths to retrieve from the mutation result.
                    If not specified, returns all scalar fields.
                    Use dot notation for nested fields: ["id", "name", "author.email"]

        Returns:
            Dictionary with:
            - success: True if mutation succeeded
            - data: The mutation result (if successful)
            - error: Error message (if failed)
            - error_type: Type of error (if failed)

        Examples:
            # Create a user
            graphql_mutation(
                operation_name="create_user",
                arguments={"name": "John", "email": "john@example.com"},
                fields=["id", "name", "email"]
            )

            # Create a post with nested author info
            graphql_mutation(
                operation_name="create_post",
                arguments={"title": "Hello", "content": "World", "author_id": 1},
                fields=["id", "title", "author.name"]
            )
        """
        try:
            # Validate inputs
            if not operation_name:
                return create_error_response(
                    "operation_name is required",
                    MCPErrors.MISSING_REQUIRED_FIELD,
                )

            if arguments is None:
                arguments = {}

            # If no fields specified, use a minimal selection
            if not fields:
                # Build a minimal mutation without field selection
                # This will return an empty object, which is valid for mutations
                fields = []

            # Build the GraphQL mutation string
            if fields:
                mutation_str = builder.build_query(
                    operation_name=operation_name,
                    arguments=arguments,
                    fields=fields,
                    operation_type="mutation",
                )
            else:
                # Build mutation without field selection
                args_str = ""
                if arguments:
                    args_str = "(" + builder._format_arguments(arguments) + ")"
                mutation_str = f"mutation {{ {operation_name}{args_str} }}"

            # Execute the mutation
            result = await handler.execute(mutation_str)

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
            data = result.get("data", {}).get(operation_name)
            return create_success_response(data)

        except MCPError as e:
            return create_error_response(e)
        except Exception as e:
            return create_error_response(
                str(e),
                MCPErrors.INTERNAL_ERROR,
            )
