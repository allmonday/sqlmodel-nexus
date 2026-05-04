"""GraphQL Demo with API Key Authentication.

This demo shows how to protect GraphQL endpoints with API Key authentication.

Usage:
    uv run python -m auth_demo.app

Authentication:
    All GraphQL endpoints require X-API-Key header with admin role.

    Example:
        curl -H "X-API-Key: admin-secret-key" -X POST http://localhost:8000/graphql \\
             -H "Content-Type: application/json" \\
             -d '{"query": "{ users { id name } }"}'
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

from demo.auth.auth import require_admin
from demo.blog.database import async_session, init_db
from demo.blog.models import BaseEntity
from sqlmodel_nexus import GraphQLHandler


class GraphQLRequest(BaseModel):
    """GraphQL request model."""

    query: str
    variables: dict[str, Any] | None = None
    operation_name: str | None = None


# Create GraphQL handler
handler = GraphQLHandler(base=BaseEntity, session_factory=async_session)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await init_db()
    yield


# Create FastAPI application
app = FastAPI(
    title="SQLModel Nexus Auth Demo",
    description="Demo application with API Key authentication for GraphQL endpoints",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/graphql", response_class=HTMLResponse)
async def graphiql_playground(_: str = Depends(require_admin)):
    """GraphiQL interactive query interface (requires admin API Key)."""
    return handler.get_graphiql_html()


@app.post("/graphql")
async def graphql_endpoint(
    req: GraphQLRequest,
    _: str = Depends(require_admin),
):
    """GraphQL query endpoint (requires admin API Key)."""
    return await handler.execute(
        query=req.query,
        variables=req.variables,
        operation_name=req.operation_name,
    )


@app.get("/schema", response_class=PlainTextResponse)
async def get_schema(_: str = Depends(require_admin)):
    """Get GraphQL schema in SDL format (requires admin API Key)."""
    return handler.get_sdl()


@app.get("/")
async def root():
    """Root endpoint with usage instructions."""
    return {
        "message": "SQLModel Nexus Auth Demo Server",
        "authentication": {
            "type": "API Key",
            "header": "X-API-Key",
            "roles": {
                "admin": "Full access to GraphQL and MCP",
                "readonly": "No access (reserved for future use)",
            },
        },
        "api_keys": {
            "admin": "admin-secret-key (set ADMIN_API_KEY env var)",
            "readonly": "readonly-key (set READONLY_API_KEY env var)",
        },
        "endpoints": {
            "graphiql": "/graphql (GET - GraphiQL UI, requires admin)",
            "graphql": "/graphql (POST - Query endpoint, requires admin)",
            "schema": "/schema (GET - SDL schema, requires admin)",
            "docs": "/docs (GET - FastAPI docs)",
        },
        "example_requests": [
            {
                "description": "Query users with admin key",
                "command": (
                    'curl -H "X-API-Key: admin-secret-key" -X POST '
                    "http://localhost:8000/graphql -H 'Content-Type: application/json' "
                    '-d \'{"query": "{ users { id name } }"}\''
                ),
            },
            {
                "description": "Query without API Key (will fail)",
                "command": (
                    "curl -X POST http://localhost:8000/graphql "
                    "-H 'Content-Type: application/json' "
                    '-d \'{"query": "{ users { id name } }"}\''
                ),
            },
        ],
    }


if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
