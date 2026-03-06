"""MCP Server for sqlmodel-graphql.

Provides a FastMCP server that exposes GraphQL operations as MCP tools.
"""

from __future__ import annotations

import argparse
import asyncio
from typing import TYPE_CHECKING

from sqlmodel_graphql.handler import GraphQLHandler
from sqlmodel_graphql.mcp.builders.schema_formatter import SchemaFormatter
from sqlmodel_graphql.mcp.tools import (
    register_get_schema_tool,
    register_graphql_mutation_tool,
    register_graphql_query_tool,
)

if TYPE_CHECKING:
    from sqlmodel import SQLModel


def create_mcp_server(
    entities: list[type[SQLModel]],
    name: str = "SQLModel GraphQL API",
    version: str = "1.0.0",
) -> "FastMCP":
    """Create an MCP server that exposes GraphQL operations as tools.

    This function creates a FastMCP server with three tools:
    - get_schema: Discover available queries, mutations, and types
    - graphql_query: Execute dynamic GraphQL queries
    - graphql_mutation: Execute dynamic GraphQL mutations

    Args:
        entities: List of SQLModel entity classes with @query/@mutation decorators.
        name: Name of the MCP server (shown in MCP clients).
        version: Version of the MCP server.

    Returns:
        A configured FastMCP server instance.

    Example:
        ```python
        from demo.models import User, Post, Comment
        from sqlmodel_graphql.mcp import create_mcp_server

        mcp = create_mcp_server(
            entities=[User, Post, Comment],
            name="Blog GraphQL API"
        )

        # Run with stdio transport (default)
        mcp.run()

        # Or run with HTTP transport
        mcp.run(transport="streamable-http")
        ```
    """
    from mcp.server.fastmcp import FastMCP

    # Create the GraphQL handler
    handler = GraphQLHandler(entities=entities)

    # Create the schema formatter
    formatter = SchemaFormatter(handler)

    # Create the FastMCP server
    mcp = FastMCP(name)

    # Register the tools
    register_get_schema_tool(mcp, formatter)
    register_graphql_query_tool(mcp, handler)
    register_graphql_mutation_tool(mcp, handler)

    return mcp


def main() -> None:
    """CLI entry point for running the MCP server.

    Usage:
        # stdio mode (default)
        python -m sqlmodel_graphql.mcp.server

        # HTTP mode
        python -m sqlmodel_graphql.mcp.server --transport http --port 8000
    """
    import sys
    from pathlib import Path

    # Add project root to sys.path for demo module access
    project_root = Path(__file__).parent.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    parser = argparse.ArgumentParser(
        description="Run the sqlmodel-graphql MCP server"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="Transport protocol to use (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP transport (default: 8000)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host for HTTP transport (default: 0.0.0.0)",
    )

    args = parser.parse_args()

    # Import demo entities as a fallback for CLI usage
    # In real usage, users would import their own entities
    try:
        from demo.models import Comment, Post, User

        entities = [User, Post, Comment]
    except ImportError:
        print(
            "Error: No entities found. Please create your entities and "
            "use create_mcp_server() directly."
        )
        return

    mcp = create_mcp_server(
        entities=entities,
        name="SQLModel GraphQL MCP Server",
    )

    if args.transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
