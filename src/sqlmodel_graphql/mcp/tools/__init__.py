"""MCP tools module."""

from sqlmodel_graphql.mcp.tools.get_schema import register_get_schema_tool
from sqlmodel_graphql.mcp.tools.graphql_mutation import register_graphql_mutation_tool
from sqlmodel_graphql.mcp.tools.graphql_query import register_graphql_query_tool

__all__ = [
    "register_get_schema_tool",
    "register_graphql_query_tool",
    "register_graphql_mutation_tool",
]
