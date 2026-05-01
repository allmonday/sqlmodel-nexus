"""RPC module — MCP server for Core API DTO-driven business methods.

Provides an independent MCP server that exposes RpcService methods
to AI agents via three-layer progressive disclosure.
"""

from sqlmodel_nexus.rpc.business import RpcService
from sqlmodel_nexus.rpc.server import create_rpc_mcp_server
from sqlmodel_nexus.rpc.types import RpcServiceConfig

__all__ = [
    "RpcService",
    "create_rpc_mcp_server",
    "RpcServiceConfig",
]
