"""MCP Server for sqlmodel-nexus.

Provides a FastMCP server that exposes multiple GraphQL applications as MCP tools
with three-layer progressive disclosure for reduced context usage.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from sqlmodel_nexus.mcp.managers import MultiAppManager
from sqlmodel_nexus.mcp.tools.multi_app_tools import register_multi_app_tools
from sqlmodel_nexus.mcp.types.app_config import AppConfig

if TYPE_CHECKING:
    from fastmcp import FastMCP


def create_mcp_server(
    apps: list[AppConfig],
    name: str = "Multi-App SQLModel Nexus API",
    allow_mutation: bool = False,
) -> FastMCP:
    """Create an MCP server that exposes multiple GraphQL APIs as tools.

    This function creates a FastMCP server with multi-app support and three-layer
    progressive disclosure:

    **Layer 0 (App Discovery):**
    - list_apps: List all available applications

    **Layer 1 (Lightweight):**
    - list_queries: List query names and descriptions for a specific app
    - list_mutations: List mutation names and descriptions for a specific app
      (if allow_mutation=True)

    **Layer 2 (On-demand):**
    - get_query_schema: Get query details + related type introspection
    - get_mutation_schema: Get mutation details + related type introspection
      (if allow_mutation=True)

    **Layer 3 (Execution):**
    - graphql_query: Execute GraphQL queries
    - graphql_mutation: Execute GraphQL mutations
      (if allow_mutation=True)

    All tools (except list_apps) require a mandatory app_name parameter.

    Args:
        apps: List of app configurations. Each app has its own GraphQL schema
              and independent database.
        name: Name of the MCP server (shown in MCP clients).
        allow_mutation: If True, registers mutation-related tools (list_mutations,
            get_mutation_schema, graphql_mutation) and includes mutations_count
            in list_apps. Default is False (read-only mode).

    Returns:
        A configured FastMCP server instance.

    Example:
        ```python
        from myapp.blog_models import BlogBaseEntity
        from myapp.shop_models import ShopBaseEntity
        from sqlmodel_nexus.mcp import create_mcp_server

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

    Tools provided (when allow_mutation=False, default):
        - list_apps(): List all available apps
        - list_queries(app_name): List queries for an app
        - get_query_schema(name, app_name, response_type): Get query details
        - graphql_query(query, app_name): Execute a GraphQL query

    Additional tools (when allow_mutation=True):
        - list_mutations(app_name): List mutations for an app
        - get_mutation_schema(name, app_name, response_type): Get mutation details
        - graphql_mutation(mutation, app_name): Execute a GraphQL mutation
    """
    from fastmcp import FastMCP

    # Create the multi-app manager
    manager = MultiAppManager(apps)

    # Create the FastMCP server
    mcp = FastMCP(name)

    # Register all multi-app tools
    register_multi_app_tools(mcp, manager, allow_mutation=allow_mutation)

    return mcp


def config_simple_mcp_server(
    base: type,
    name: str = "SQLModel Nexus API",
    desc: str | None = None,
    allow_mutation: bool = False,
    session_factory: Callable | None = None,
) -> FastMCP:
    """Create a simplified MCP server for single-app scenarios.

    This function creates a FastMCP server with only 2-3 tools, eliminating
    the complexity of multi-app management and progressive disclosure.
    Perfect for simple GraphQL APIs with a single database.

    **Tools provided (when allow_mutation=False, default):**
    - get_schema: Get the complete GraphQL schema in SDL format
    - graphql_query: Execute GraphQL queries

    **Additional tool (when allow_mutation=True):**
    - graphql_mutation: Execute GraphQL mutations

    All tools work without requiring an app_name parameter.

    Args:
        base: SQLModel base class. All subclasses with @query/@mutation
              decorators will be automatically discovered.
        name: Name of the MCP server (shown in MCP clients).
        desc: Optional description for the GraphQL schema (used for both
              Query and Mutation type descriptions).
        allow_mutation: If True, registers graphql_mutation tool and includes
            Mutation type in schema. Default is False (read-only mode).
        session_factory: Async session factory for DataLoader relationship
            loading. Required if queries return entities with relationships.

    Returns:
        A configured FastMCP server instance with 2-3 simplified tools.

    Example:
        ```python
        from sqlmodel import SQLModel
        from sqlmodel_nexus import query
        from sqlmodel_nexus.mcp import config_simple_mcp_server

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

    Tools provided (when allow_mutation=False, default):
        - get_schema(): Get the complete GraphQL schema
        - graphql_query(query): Execute a GraphQL query

    Additional tool (when allow_mutation=True):
        - graphql_mutation(mutation): Execute a GraphQL mutation
    """
    from fastmcp import FastMCP

    from sqlmodel_nexus.mcp.managers.single_app_manager import SingleAppManager
    from sqlmodel_nexus.mcp.tools.simple_tools import register_simple_tools

    # Create the single-app manager
    manager = SingleAppManager(base=base, description=desc, session_factory=session_factory)

    # Create the FastMCP server
    mcp = FastMCP(name)

    # Register simplified tools (no app_name required)
    register_simple_tools(mcp, manager, allow_mutation=allow_mutation)

    return mcp
