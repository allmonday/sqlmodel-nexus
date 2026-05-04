"""create_rpc_voyager — public API for creating RPC voyager visualization.

Creates a FastAPI ASGI sub-application that can be mounted on any
FastAPI/Starlette app to provide interactive visualization of
RPC services and ER diagrams.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel as PydanticModel

from sqlmodel_nexus.loader.registry import ErManager
from sqlmodel_nexus.rpc.types import RpcServiceConfig
from sqlmodel_nexus.voyager.type import CoreData, SchemaNode, Tag
from sqlmodel_nexus.voyager.voyager_context import (
    STATIC_FILES_PATH,
    WEB_DIR,
    VoyagerContext,
)

# ── Request/Response models ─────────────────────────────────────


class OptionParam(PydanticModel):
    tags: list[Tag]
    schemas: list[SchemaNode]
    dot: str
    enable_brief_mode: bool
    version: str
    initial_page_policy: Literal["first", "full", "empty"]
    swagger_url: str | None = None
    has_er_diagram: bool = False
    enable_pydantic_resolve_meta: bool = False
    framework_name: str = "RPC API"


class Payload(PydanticModel):
    tags: list[str] | None = None
    schema_name: str | None = None
    schema_field: str | None = None
    route_name: str | None = None
    show_fields: str = "object"
    brief: bool = False
    hide_primitive_route: bool = False
    show_module: bool = True
    show_pydantic_resolve_meta: bool = False


class SearchResultOptionParam(PydanticModel):
    tags: list[Tag]


class SchemaSearchPayload(PydanticModel):
    schema_name: str | None = None
    schema_field: str | None = None
    show_fields: str = "object"
    brief: bool = False
    hide_primitive_route: bool = False
    show_module: bool = True
    show_pydantic_resolve_meta: bool = False


class ErDiagramPayload(PydanticModel):
    show_fields: str = "object"
    show_module: bool = True
    edge_minlen: int = 3
    show_methods: bool = True


class SourcePayload(PydanticModel):
    schema_name: str


# ── Public API ───────────────────────────────────────────────────


def create_rpc_voyager(
    services: list[RpcServiceConfig],
    er_manager: ErManager | None = None,
    name: str = "RPC API",
    module_color: dict[str, str] | None = None,
    initial_page_policy: Literal["first", "full", "empty"] = "first",
    online_repo_url: str | None = None,
    version: str = "1.0.0",
    gzip_minimum_size: int | None = 500,
) -> Any:
    """Create a voyager visualization ASGI app for RPC services.

    Returns a FastAPI application that can be mounted on any
    FastAPI/Starlette app.

    Usage::

        from sqlmodel_nexus.voyager import create_rpc_voyager

        voyager_app = create_rpc_voyager(
            services=[
                {"name": "user", "service": UserService},
                {"name": "task", "service": TaskService},
            ],
            er_manager=er,
            name="My Project API",
        )
        app.mount("/voyager", voyager_app)

    Args:
        services: List of RpcServiceConfig dicts with name, service, description.
        er_manager: Optional ErManager for ER diagram visualization.
        name: Display name for the voyager UI.
        module_color: Optional color mapping for modules.
        initial_page_policy: Initial page display policy.
        online_repo_url: Optional online repository URL for source links.
        version: Version string for cache busting.
        gzip_minimum_size: Minimum size for gzip compression (set to <0 to disable).

    Returns:
        A FastAPI application that provides the voyager UI.
    """
    from fastapi import APIRouter, FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
    from fastapi.staticfiles import StaticFiles
    from starlette.middleware.gzip import GZipMiddleware

    ctx = VoyagerContext(
        configs=services,
        er_manager=er_manager,
        name=name,
        module_color=module_color,
        initial_page_policy=initial_page_policy,
        online_repo_url=online_repo_url,
        version=version,
    )

    router = APIRouter(tags=["voyager"])

    @router.get("/dot", response_model=OptionParam)
    def get_dot() -> OptionParam:
        data = ctx.get_option_param()
        return OptionParam(**data)

    @router.post("/dot-search", response_model=SearchResultOptionParam)
    def get_search_dot(payload: SchemaSearchPayload) -> SearchResultOptionParam:
        tags = ctx.get_search_dot(payload.model_dump())
        return SearchResultOptionParam(tags=tags)

    @router.post("/dot", response_class=PlainTextResponse)
    def get_filtered_dot(payload: Payload) -> str:
        return ctx.get_filtered_dot(payload.model_dump())

    @router.post("/dot-core-data", response_model=CoreData)
    def get_filtered_dot_core_data(payload: Payload) -> CoreData:
        return ctx.get_core_data(payload.model_dump())

    @router.post("/dot-render-core-data", response_class=PlainTextResponse)
    def render_dot_from_core_data(core_data: CoreData) -> str:
        return ctx.render_dot_from_core_data(core_data)

    @router.post("/er-diagram")
    def get_er_diagram(payload: ErDiagramPayload):
        return ctx.get_er_diagram_data(payload.model_dump())

    @router.get("/", response_class=HTMLResponse)
    def index() -> str:
        return ctx.get_index_html()

    @router.post("/source")
    def get_object_by_module_name(payload: SourcePayload) -> JSONResponse:
        result = ctx.get_source_code(payload.schema_name)
        status_code = 200 if "error" not in result else 400
        if "error" in result and "not found" in result["error"]:
            status_code = 404
        return JSONResponse(content=result, status_code=status_code)

    @router.post("/vscode-link")
    def get_vscode_link_by_module_name(payload: SourcePayload) -> JSONResponse:
        result = ctx.get_vscode_link(payload.schema_name)
        status_code = 200 if "error" not in result else 400
        if "error" in result and "not found" in result["error"]:
            status_code = 404
        return JSONResponse(content=result, status_code=status_code)

    app = FastAPI(title=f"{name} Voyager")

    if gzip_minimum_size is not None and gzip_minimum_size >= 0:
        app.add_middleware(GZipMiddleware, minimum_size=gzip_minimum_size)


    app.mount(STATIC_FILES_PATH, StaticFiles(directory=str(WEB_DIR)), name="static")
    app.include_router(router)

    return app
