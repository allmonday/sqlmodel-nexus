"""Multi-app managers for MCP support."""

from sqlmodel_graphql.mcp.managers.app_resources import AppResources
from sqlmodel_graphql.mcp.managers.multi_app_manager import MultiAppManager
from sqlmodel_graphql.mcp.managers.single_app_manager import SingleAppManager

__all__ = ["AppResources", "MultiAppManager", "SingleAppManager"]
