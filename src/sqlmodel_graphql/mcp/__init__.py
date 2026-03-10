"""MCP (Model Context Protocol) integration for sqlmodel-graphql.

This module provides an MCP server that exposes multiple GraphQL applications as MCP tools,
allowing AI models to dynamically discover and execute GraphQL queries and mutations
across multiple independent databases.

Example:
    ```python
    from myapp.blog_models import BlogBaseEntity
    from myapp.shop_models import ShopBaseEntity
    from sqlmodel_graphql.mcp import create_mcp_server

    apps = [
        {
            "name": "blog",
            "base": BlogBaseEntity,
            "description": "Blog system API",
            "query_description": "Query users, posts, and comments",
            "mutation_description": "Create and update blog data",
        },
        {
            "name": "shop",
            "base": ShopBaseEntity,
            "description": "E-commerce system API",
            "query_description": "Query products and orders",
            "mutation_description": "Create orders and products",
        }
    ]

    mcp = create_mcp_server(
        apps=apps,
        name="My Multi-App GraphQL API"
    )

    # Run with stdio transport (default)
    mcp.run()

    # Or run with HTTP transport
    mcp.run(transport="streamable-http")
    ```
"""

from __future__ import annotations

__all__ = ["create_mcp_server", "AppConfig", "MultiAppManager", "AppResources"]

from sqlmodel_graphql.mcp.managers import AppResources, MultiAppManager
from sqlmodel_graphql.mcp.server import create_mcp_server
from sqlmodel_graphql.mcp.types.app_config import AppConfig
