"""get_schema MCP tool.

Returns structured GraphQL schema information for AI discovery.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlmodel_graphql.mcp.types.errors import create_success_response

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from sqlmodel_graphql.mcp.builders.schema_formatter import SchemaFormatter


def register_get_schema_tool(mcp: FastMCP, formatter: SchemaFormatter) -> None:
    """Register the get_schema tool with the MCP server.

    Args:
        mcp: The FastMCP server instance.
        formatter: The SchemaFormatter instance.
    """

    @mcp.tool()
    def get_schema() -> dict[str, Any]:
        """Get GraphQL schema information.

        Returns the complete schema including available queries, mutations, and types.
        Use this tool to discover what operations are available before executing queries.

        Returns:
            Dictionary containing:
            - queries: List of available query operations with arguments and return types
            - mutations: List of available mutation operations with arguments and return types
            - types: List of entity types with their scalar and relationship fields

        Example response:
            {
                "queries": [
                    {
                        "name": "users",
                        "description": "Get all users with optional limit",
                        "arguments": [{"name": "limit", "type": "Int", "required": false}],
                        "return_type": "[User]!"
                    }
                ],
                "mutations": [...],
                "types": [
                    {
                        "name": "User",
                        "scalar_fields": [{"name": "id", "type": "Int"}, {"name": "name", "type": "String!"}],
                        "relationship_fields": [{"name": "posts", "type": "[Post]!"}]
                    }
                ]
            }
        """
        try:
            schema_info = formatter.get_schema_info()
            return create_success_response(schema_info)
        except Exception as e:
            # Should not fail, but return error if it does
            return {
                "success": False,
                "error": str(e),
                "error_type": "internal_error",
            }
