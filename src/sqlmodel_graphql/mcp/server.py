"""MCP Server for sqlmodel-graphql.

Provides a FastMCP server that exposes multiple GraphQL applications as MCP tools
with three-layer progressive disclosure for reduced context usage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel_graphql.mcp.managers import MultiAppManager
from sqlmodel_graphql.mcp.tools.multi_app_tools import register_multi_app_tools
from sqlmodel_graphql.mcp.types.app_config import AppConfig

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def create_mcp_server(
    apps: list[AppConfig],
    name: str = "Multi-App SQLModel GraphQL API",
) -> FastMCP:
    """Create an MCP server that exposes multiple GraphQL APIs as tools.

    This function creates a FastMCP server with multi-app support and three-layer
    progressive disclosure:

    **Layer 0 (App Discovery):**
    - list_apps: List all available applications

    **Layer 1 (Lightweight):**
    - list_queries: List query names and descriptions for a specific app
    - list_mutations: List mutation names and descriptions for a specific app

    **Layer 2 (On-demand):**
    - get_query_schema: Get query details + related type introspection
    - get_mutation_schema: Get mutation details + related type introspection

    **Layer 3 (Execution):**
    - graphql_query: Execute GraphQL queries
    - graphql_mutation: Execute GraphQL mutations

    All tools (except list_apps) require a mandatory app_name parameter.

    Args:
        apps: List of app configurations. Each app has its own GraphQL schema
              and independent database.
        name: Name of the MCP server (shown in MCP clients).

    Returns:
        A configured FastMCP server instance.

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

    Tools provided:
        - list_apps(): List all available apps
        - list_queries(app_name): List queries for an app
        - list_mutations(app_name): List mutations for an app
        - get_query_schema(name, app_name, response_type): Get query details
        - get_mutation_schema(name, app_name, response_type): Get mutation details
        - graphql_query(query, app_name): Execute a GraphQL query
        - graphql_mutation(mutation, app_name): Execute a GraphQL mutation
    """
    from mcp.server.fastmcp import FastMCP

    # Create the multi-app manager
    manager = MultiAppManager(apps)

    # Create the FastMCP server
    mcp = FastMCP(name)

    # Register all multi-app tools
    register_multi_app_tools(mcp, manager)

    return mcp


def config_simple_mcp_server(
    base: type,
    name: str = "SQLModel GraphQL API",
    desc: str | None = None,
) -> FastMCP:
    """Create a simplified MCP server for single-app scenarios.

    This function creates a FastMCP server with only 3 tools, eliminating
    the complexity of multi-app management and progressive disclosure.
    Perfect for simple GraphQL APIs with a single database.

    **Tools provided:**
    - get_schema: Get the complete GraphQL schema in SDL format
    - graphql_query: Execute GraphQL queries
    - graphql_mutation: Execute GraphQL mutations

    All tools work without requiring an app_name parameter.

    Args:
        base: SQLModel base class. All subclasses with @query/@mutation
              decorators will be automatically discovered.
        name: Name of the MCP server (shown in MCP clients).
        desc: Optional description for the GraphQL schema (used for both
              Query and Mutation type descriptions).

    Returns:
        A configured FastMCP server instance with 3 simplified tools.

    Example:
        ```python
        from sqlmodel import SQLModel
        from sqlmodel_graphql import query
        from sqlmodel_graphql.mcp import config_simple_mcp_server

        class BaseEntity(SQLModel):
            pass

        class User(BaseEntity, table=True):
            id: int
            name: str

            @query
            async def get_users(cls) -> list['User']:
                return await fetch_users()

        # Create simplified MCP server
        mcp = config_simple_mcp_server(
            base=BaseEntity,
            name="My Blog API",
            desc="Blog system with users and posts"
        )

        # Run with stdio transport (default)
        mcp.run()

        # Or run with HTTP transport
        mcp.run(transport="streamable-http")
        ```

    Note:
        For multi-app scenarios with separate databases, use create_mcp_server()
        instead, which provides app discovery and routing capabilities.

    Tools provided:
        - get_schema(): Get the complete GraphQL schema
        - graphql_query(query): Execute a GraphQL query
        - graphql_mutation(mutation): Execute a GraphQL mutation
    """
    from mcp.server.fastmcp import FastMCP

    from sqlmodel_graphql.mcp.managers.single_app_manager import SingleAppManager
    from sqlmodel_graphql.mcp.tools.simple_tools import register_simple_tools

    # Create the single-app manager
    manager = SingleAppManager(base=base, description=desc)

    # Create the FastMCP server
    mcp = FastMCP(name)

    # Register simplified tools (no app_name required)
    register_simple_tools(mcp, manager)

    return mcp
