"""API Key authentication module for GraphQL and MCP endpoints."""

import os

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# API Keys configuration from environment variables
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "admin-secret-key")
READONLY_API_KEY = os.getenv("READONLY_API_KEY", "readonly-key")

# Key to role mapping
API_KEYS: dict[str, str] = {
    ADMIN_API_KEY: "admin",
    READONLY_API_KEY: "readonly",
}


def get_api_key(request: Request) -> str | None:
    """Extract API Key from request headers.

    Args:
        request: FastAPI request object

    Returns:
        API Key string or None if not found
    """
    return request.headers.get("X-API-Key")


def require_admin(request: Request) -> str:
    """Dependency that requires admin role.

    Use with FastAPI Depends() to protect endpoints.

    Args:
        request: FastAPI request object

    Returns:
        Role string if authenticated

    Raises:
        HTTPException: 401 if no/invalid API key, 403 if not admin
    """
    key = get_api_key(request)
    if not key:
        raise HTTPException(status_code=401, detail="API Key required (X-API-Key header)")

    role = API_KEYS.get(key)
    if not role:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    return role


class MCPAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to protect MCP HTTP endpoints with API Key authentication.

    Only allows requests with valid admin API Key.
    """

    async def dispatch(self, request, call_next):
        """Check API Key before processing request."""
        key = request.headers.get("X-API-Key")

        if not key:
            return JSONResponse(
                {"error": "API Key required (X-API-Key header)"},
                status_code=401,
            )

        role = API_KEYS.get(key)
        if not role:
            return JSONResponse(
                {"error": "Invalid API Key"},
                status_code=401,
            )

        if role != "admin":
            return JSONResponse(
                {"error": "Admin access required"},
                status_code=403,
            )

        return await call_next(request)
