"""MCP Server for sqlmodel-graphql.

Provides a FastMCP server that exposes GraphQL operations as MCP tools
with three-layer progressive disclosure for reduced context usage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel_graphql.handler import GraphQLHandler
from sqlmodel_graphql.mcp.builders.type_tracer import TypeTracer
from sqlmodel_graphql.mcp.tools import (
    register_get_operation_schema_tools,
    register_graphql_mutation_tool,
    register_graphql_query_tool,
    register_list_operations_tools,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from sqlmodel import SQLModel


def create_mcp_server(
    base: type[SQLModel],
    name: str = "SQLModel GraphQL API",
    query_description: str | None = None,
    mutation_description: str | None = None,
) -> "FastMCP":
    """Create an MCP server that exposes GraphQL operations as tools.

    This function creates a FastMCP server with three-layer progressive disclosure:

    **Layer 1 (Lightweight):**
    - list_queries: List query names and descriptions (~50 tokens)
    - list_mutations: List mutation names and descriptions (~50 tokens)

    **Layer 2 (On-demand):**
    - get_query_schema: Get query details + related type introspection
    - get_mutation_schema: Get mutation details + related type introspection

    **Layer 3 (Execution):**
    - graphql_query: Execute GraphQL queries
    - graphql_mutation: Execute GraphQL mutations

    Args:
        base: SQLModel base class. All subclasses with @query/@mutation
              decorators will be automatically discovered.
        name: Name of the MCP server (shown in MCP clients).
        query_description: Optional custom description for Query type.
        mutation_description: Optional custom description for Mutation type.

    Returns:
        A configured FastMCP server instance.

    Example:
        ```python
        from myapp.models import BaseEntity
        from sqlmodel_graphql.mcp import create_mcp_server

        mcp = create_mcp_server(
            base=BaseEntity,
            name="My Blog GraphQL API",
            query_description="Query users, posts, and comments",
            mutation_description="Create and update data",
        )

        # Run with stdio transport (default)
        mcp.run()

        # Or run with HTTP transport
        mcp.run(transport="streamable-http")
        ```
    """
    from mcp.server.fastmcp import FastMCP

    # Create the GraphQL handler
    handler = GraphQLHandler(
        base=base,
        query_description=query_description,
        mutation_description=mutation_description,
    )

    # Get introspection data and entity names
    introspection_data = handler._introspection_generator.generate()
    entity_names = {e.__name__ for e in handler.entities}

    # Create the type tracer for progressive disclosure
    tracer = TypeTracer(introspection_data, entity_names)

    # Create the FastMCP server
    mcp = FastMCP(name)

    # Register Layer 1 tools (lightweight operation lists)
    register_list_operations_tools(mcp, tracer)

    # Register Layer 2 tools (operation details + related types)
    register_get_operation_schema_tools(mcp, tracer)

    # Register Layer 3 tools (query execution)
    register_graphql_query_tool(mcp, handler)
    register_graphql_mutation_tool(mcp, handler)

    return mcp
