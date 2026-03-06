"""MCP (Model Context Protocol) integration for sqlmodel-graphql.

This module provides an MCP server that exposes GraphQL operations as MCP tools,
allowing AI models to dynamically discover and execute GraphQL queries and mutations.

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

CLI Usage:
    # stdio mode (default)
    python -m sqlmodel_graphql.mcp.server

    # HTTP mode
    python -m sqlmodel_graphql.mcp.server --transport streamable-http --port 8000
"""

from __future__ import annotations

__all__ = ["create_mcp_server"]

from sqlmodel_graphql.mcp.server import create_mcp_server
