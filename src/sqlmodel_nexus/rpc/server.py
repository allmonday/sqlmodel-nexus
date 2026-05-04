"""RPC MCP Server — three-layer progressive disclosure for RPC methods.

Creates an independent FastMCP server that exposes RpcService methods
to AI agents via progressive disclosure:
- list_services: discover available services
- describe_service: get method signatures for a service
- call_rpc: execute a specific method
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from sqlmodel_nexus.mcp.types.errors import (
    MCPErrors,
    create_error_response,
    create_success_response,
)
from sqlmodel_nexus.rpc.business import RPC_METHODS_ATTR  # noqa: F401
from sqlmodel_nexus.rpc.introspector import ServiceIntrospector

if TYPE_CHECKING:
    from fastmcp import FastMCP


_RPC_SERVICE_NOT_FOUND = "SERVICE_NOT_FOUND"
_RPC_METHOD_NOT_FOUND = "METHOD_NOT_FOUND"
_RPC_EXECUTION_ERROR = "EXECUTION_ERROR"
_RPC_INVALID_PARAMS = "INVALID_PARAMS"


def create_rpc_mcp_server(
    services: list[dict[str, Any]],
    name: str = "RPC API",
) -> FastMCP:
    """Create an MCP server that exposes RPC services as tools.

    Args:
        services: List of RpcServiceConfig dicts. Each must have
            ``name`` and ``service`` keys.
        name: Name of the MCP server (shown in MCP clients).

    Returns:
        A configured FastMCP server instance.

    Example::

        mcp = create_rpc_mcp_server(
            services=[
                {"name": "sprint", "service": SprintService,
                 "description": "Sprint management"},
            ],
            name="Project RPC API",
        )
        mcp.run()
    """
    from fastmcp import FastMCP

    introspector = ServiceIntrospector(services)

    mcp = FastMCP(name)

    # Layer 1: Service discovery
    @mcp.tool()
    def list_services() -> dict[str, Any]:
        """List all available RPC services.

        Returns a list of services with their names, descriptions, and
        method counts. Use this tool first to discover available services,
        then use describe_service to explore a specific service's methods.

        Returns:
            Dictionary with success, data (list of service info), and hint.

        Example response::

            {
                "success": true,
                "data": [
                    {"name": "sprint", "description": "Sprint management",
                     "methods_count": 2}
                ],
                "hint": "Use describe_service(service_name='sprint') ..."
            }
        """
        try:
            services_info = introspector.list_services()

            service_names = [s["name"] for s in services_info]
            hint = (
                f"Use describe_service(service_name='...') to explore methods. "
                f"Available services: {service_names}."
            )

            return {
                "success": True,
                "data": services_info,
                "hint": hint,
            }
        except Exception as e:
            return create_error_response(str(e), MCPErrors.INTERNAL_ERROR)

    # Layer 2: Method description
    @mcp.tool()
    def describe_service(service_name: str) -> dict[str, Any]:
        """Get detailed method info for a specific RPC service.

        Returns all methods on the service with their names, descriptions,
        parameter schemas (JSON Schema), and return type schemas.
        Use this after list_services to understand what methods are available,
        then use call_rpc to execute a specific method.

        Args:
            service_name: Name of the service (from list_services).

        Returns:
            Dictionary with success, data (service details), and hint.

        Example::

            describe_service(service_name="sprint")
        """
        try:
            info = introspector.describe_service(service_name)
            if info is None:
                return create_error_response(
                    f"Service '{service_name}' not found. "
                    f"Use list_services() to see available services.",
                    MCPErrors.APP_NOT_FOUND,
                )

            method_names = [m["name"] for m in info.get("methods", [])]
            hint = (
                f"Methods in '{service_name}': {method_names}. "
                f"Use call_rpc(service_name='{service_name}', "
                f"method_name='...', params='{{...}}') to execute."
            )

            result = create_success_response(info)
            result["hint"] = hint
            return result
        except Exception as e:
            return create_error_response(str(e), MCPErrors.INTERNAL_ERROR)

    # Layer 3: Execute RPC
    @mcp.tool()
    async def call_rpc(
        service_name: str, method_name: str, params: str = "{}"
    ) -> dict[str, Any]:
        """Execute an RPC method on a specific service.

        Call a method discovered via describe_service. The params argument
        should be a JSON object string matching the method's parameter schema.

        Args:
            service_name: Name of the service.
            method_name: Name of the method to call.
            params: JSON string with method parameters (default: "{}").

        Returns:
            Dictionary with success, data (method result), and hint.

        Examples::

            # No parameters
            call_rpc(service_name="sprint", method_name="list_sprints")

            # With parameters
            call_rpc(
                service_name="sprint",
                method_name="get_sprint",
                params='{"sprint_id": 1}'
            )
        """
        # Parse params JSON
        try:
            kwargs = json.loads(params) if params else {}
        except json.JSONDecodeError as e:
            return create_error_response(
                f"Invalid JSON in params: {e}",
                MCPErrors.VALIDATION_ERROR,
            )

        if not isinstance(kwargs, dict):
            return create_error_response(
                "params must be a JSON object (dict), not an array or scalar",
                MCPErrors.VALIDATION_ERROR,
            )

        # Look up service
        service_cls = introspector.get_service(service_name)
        if service_cls is None:
            return create_error_response(
                f"Service '{service_name}' not found. "
                f"Use list_services() to see available services.",
                MCPErrors.APP_NOT_FOUND,
            )

        # Look up method
        methods = getattr(service_cls, RPC_METHODS_ATTR)
        if method_name not in methods:
            available = list(methods.keys())
            return create_error_response(
                f"Method '{method_name}' not found in service '{service_name}'. "
                f"Available methods: {available}",
                MCPErrors.TYPE_NOT_FOUND,
            )

        # Execute
        try:
            method = getattr(service_cls, method_name)
            result = await method(**kwargs)
        except TypeError as e:
            return create_error_response(
                f"Parameter error calling {service_name}.{method_name}: {e}",
                MCPErrors.VALIDATION_ERROR,
            )
        except Exception as e:
            return create_error_response(
                f"Error executing {service_name}.{method_name}: {e}",
                MCPErrors.QUERY_EXECUTION_ERROR,
            )

        # Serialize result
        data = _serialize_result(result)

        response = create_success_response(data)
        response["hint"] = (
            f"Executed {service_name}.{method_name}. "
            f"Use describe_service(service_name='{service_name}') "
            f"to explore more methods."
        )
        return response

    return mcp


def _serialize_result(result: Any) -> Any:
    """Serialize a method result to a JSON-friendly structure."""
    if result is None:
        return None

    if isinstance(result, BaseModel):
        return result.model_dump()

    if isinstance(result, list):
        return [_serialize_result(item) for item in result]

    if isinstance(result, dict):
        return result

    if isinstance(result, (str, int, float, bool)):
        return result

    # Fallback: try model_dump for any Pydantic-like object
    if hasattr(result, "model_dump"):
        return result.model_dump()

    return result
