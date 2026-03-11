"""MCP server using demo entities.

Usage:
    # stdio mode (for Claude Desktop, etc.)
    uv run python demo/mcp_server.py

    # HTTP mode
    uv run python demo/mcp_server.py --http --port 8000
"""

import argparse
import sys
from pathlib import Path

# Add project root to path for sqlmodel_graphql module access
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from demo.models import BaseEntity  # noqa: E402
from sqlmodel_graphql.mcp import create_mcp_server  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the MCP server")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Use HTTP transport instead of stdio",
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

    mcp = create_mcp_server(
        apps=[{"name": "Blog", "base": BaseEntity}],
        name="Demo Blog GraphQL MCP Server",
    )

    if args.http:
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
