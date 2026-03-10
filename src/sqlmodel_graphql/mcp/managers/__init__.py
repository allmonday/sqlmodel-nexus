"""Multi-app managers for MCP support."""

from sqlmodel_graphql.mcp.managers.app_resources import AppResources
from sqlmodel_graphql.mcp.managers.multi_app_manager import MultiAppManager

__all__ = ["AppResources", "MultiAppManager"]
