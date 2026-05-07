# Changelog

## 1.3.3

### Breaking Change: Remove `Loader(str)` Support

Remove the string-based `Loader('relationship_name')` pattern that performed ErManager lookup at resolve time. Only `Loader(DataLoaderClass)` and `Loader(async_callable)` are now supported.

**Migration:**

```python
# Before
def resolve_owner(self, loader=Loader("owner")):
    return loader.load(self.owner_id)

# After — use DataLoader class or async callable
def resolve_owner(self, loader=Loader(UserLoader)):
    return loader.load(self.owner_id)
```

Note: Implicit auto-loading (field name matches relationship + compatible type) already handles the common case without any `resolve_*` method.

**Changes:**
- Remove `isinstance(dep_val, str)` branch from `Resolver._resolve_dependency`
- Remove string-based examples from `Loader` docstring
- Remove `TestLoaderWithStringName`, `TestResolverLoader`, `TestCustomRelationshipResolve` test classes
- Update `TestClassMetaCache` to use async callable instead of string dependency

## 1.3.2

### Bug Fix: Introspection defaultValue Format

Fix `IntrospectionGenerator` default value serialization from Python `repr()` to JSON format (`json.dumps`), ensuring valid GraphQL literals in introspection results. Previously, `buildClientSchema` from graphql-js (used by GraphiQL) would fail with syntax errors due to Python-formatted strings like `'planning'` (single quotes) and `None` instead of `"planning"` and `null`.

| Before (`repr`) | After (`json.dumps`) |
|------------------|----------------------|
| `'default'` | `"default"` |
| `None` | `null` |
| `True` | `true` |
| `False` | `false` |
| `5` | `5` |

- Add `_format_default_value` static method to `IntrospectionGenerator`
- Add `TestDefaultValueFormat` test class with 10 tests covering string, None, int, float, bool, list defaults and end-to-end `buildClientSchema` validation

### Documentation

- Update `llms-full.txt` to reflect current v1.3.1 API surface, including Core API, RPC + Voyager mode documentation

## 1.3.1

### Refactoring: Constant Extraction

Replace magic strings with named constants across the codebase.

| Constant | Used in |
|----------|---------|
| `QUERY_META_PARAM` | `introspection`, `sdl_generator` |
| `RELATIONSHIPS_ATTR` | `relationship` |
| `RESOLVE_PREFIX` / `POST_PREFIX` | `resolver`, `subset` |
| `RPC_METHODS_ATTR` | `rpc/business`, `rpc/introspector`, `rpc/server` |

### Demo Restructure

Consolidate all demo applications under `demo/` with domain-based sub-packages:

| Before | After |
|--------|-------|
| `auth_demo/` | `demo/auth/` |
| `demo/app.py` | `demo/blog/app.py` |
| `demo_multiple_app/` | `demo/multi_app/` |
| `demo/rpc_*.py` | `demo/rpc/` |

- Add `@query` / `@mutation` methods for User and Task entities in `demo/blog/models.py`
- Update all import paths to match new structure

### Voyager Enhancements

- **ER Diagram method discovery**: `@query` / `@mutation` methods are now shown on entity SchemaNodes
- **DefineSubset source tracking**: Voyager generates subset → source entity links for DTOs
- **RPC method source resolution**: `get_source_code` / `get_vscode_link` support `service.method` format in addition to `module.ClassName`

### Documentation

- Rewrite README tagline to emphasize progressive framework positioning and `DefineSubset` declarative capabilities
- Add mermaid flowchart illustrating P1 (ER Diagram) → P2 (GraphQL API) → P3 (Declarative Assembly) progression

## 1.3.0

### New Feature: Voyager Visualization

Migrated fastapi-voyager's interactive visualization into sqlmodel-nexus, decoupled from FastAPI route introspection. Visualizes RPC service structure and ER diagrams from ErManager.

**New package `sqlmodel_nexus.voyager`:**

| Export | Purpose |
|--------|---------|
| `create_rpc_voyager` | Create a FastAPI ASGI sub-app for interactive visualization |

**Voyager features:**
- RPC service graph: Service→Tag, Method→Route, DTO→SchemaNode mapping
- ER diagram: renders entities and relationships from ErManager
- DOT graph rendering via Jinja2 templates + Graphviz WASM frontend
- REST endpoints: `/dot`, `/dot-search`, `/er-diagram`, `/source`, `/vscode-link`
- Configurable: module colors, field visibility, theme color, initial page policy
- GZip middleware support

**ErManager new public methods:**
- `get_all_entities()` — return all registered entity classes
- `get_all_relationships()` — return full relationship registry

**Public API:**
- `create_rpc_voyager` accepts `list[RpcServiceConfig]` (reusable with `create_rpc_mcp_server`)

### Demos

- **`demo/rpc_voyager_demo.py`** — Voyager UI mounted on FastAPI, with 8 entities and 12 relationships (port 8008)
- Demo entities expanded: Project, Sprint, Task, User, Comment, Label, TaskLabel, Tag
- Update `start_all.sh` with RPC Voyager (port 8008)

### Dependencies

- Add `jinja2>=3.0` for DOT template rendering

## 1.2.0

### New Feature: RPC Services

Business service classes with auto-discovery, SDL introspection, and dual serving via MCP and web frameworks.

**New package `sqlmodel_nexus.rpc`:**

| Export | Purpose |
|--------|---------|
| `RpcService` | Base class — subclasses declare `async classmethod`s, auto-discovered by `BusinessMeta` metaclass |
| `create_rpc_mcp_server` | Create an independent FastMCP server exposing services as progressive-disclosure tools |
| `RpcServiceConfig` | Service registration config (name, service class, description) |

**RpcService features:**
- `BusinessMeta` metaclass scans for public `async classmethod`s, excludes `_`-prefixed and `get_tag_name`
- `get_tag_name()` returns OpenAPI-compatible tag name (`SprintService` → `"sprint"`)
- `ServiceIntrospector` generates SDL-style method signatures and DTO type definitions
- FK fields from `DefineSubset` DTOs are hidden from SDL output
- `_type_to_sdl_name()` converts Python type annotations to SDL types (`list[int]` → `[Int!]!`, `X | None` → `X`)

**MCP server — three-layer progressive disclosure:**

| Tool | Purpose |
|------|---------|
| `list_services()` | Discover available services and method counts |
| `describe_service(service_name)` | Method signatures (SDL) + DTO type definitions |
| `call_rpc(service_name, method_name, params)` | Execute a method with JSON params |

**Web framework integration:**
- Same `RpcService` classes serve both MCP and FastAPI routes
- Routes are thin wrappers calling service classmethods
- OpenAPI tags derived from `get_tag_name()` for automatic grouping in `/docs`

### Demos

- **`demo/rpc_mcp_server.py`** — RPC MCP server with UserService, TaskService, SprintService (stdio + HTTP)
- **`demo/rpc_fastapi.py`** — FastAPI routes calling the same RPC services, demonstrating dual-serving pattern
- Update `start_all.sh` with RPC MCP (port 8006) and RPC FastAPI (port 8007)

### Tests

- Add `tests/test_rpc.py` — 41 tests covering `BusinessMeta` discovery, SDL type conversion, `ServiceIntrospector`, MCP tool integration

### Documentation

- Add "RPC Services" section to README with service definition, MCP exposure, and web framework embedding examples
- Update README quick start table and reading order


## 1.1.1

### New Features

- **`build_dto_select`** — new public function that generates a `select(*columns)` statement from a DefineSubset DTO, querying only the scalar columns the DTO needs. Relationship field names are filtered automatically. Accepts an optional `where` parameter for SQLAlchemy filter expressions.

### Documentation & Demos

- Simplify Core API demo endpoints to use `build_dto_select` + `dict(row._mapping)` pattern instead of manual field-by-field DTO construction.

## 1.1.0

### New Features

- **`Relationship.target` supports `list[Entity]`** — one-to-many relationships can now use `target=list[Entity]` instead of the separate `is_list=True` flag. The `is_list` attribute becomes a computed property derived from the target type. A new `target_entity` property extracts the bare entity class, stripping the `list[...]` wrapper.
- **Many-to-many relationship support** — added `Article`/`Reader` many-to-many test fixtures in `conftest.py` and comprehensive loader factory tests covering `create_many_to_many_loader` and `create_page_many_to_many_loader`.
- **MCP supports `session_factory`** — `AppConfig` and `SingleAppManager` now accept an optional `session_factory` parameter, which is forwarded to `GraphQLHandler` to enable DataLoader relationship loading in MCP services.

### Bug Fixes

- **Many-to-many loader queries use `session.execute()`** — replaced `session.exec()` with `session.execute()` for raw `Table` and subquery/aggregate queries in `create_many_to_many_loader` and `create_page_many_to_many_loader`. `exec()` unwraps multi-column rows into scalars, which loses column data needed for join table resolution.

### Documentation & Demos

- Add `CLAUDE.md` and `llms-full.txt` for project-level AI context.
- Add paginated GraphQL demo application (`demo/app_paginated.py`).
- Update `start_all.sh` to include the new paginated demo service.


## 1.0.0

### New Public API: Core API Mode

sqlmodel-nexus now provides a complete Core API mode alongside GraphQL, enabling DTO-first response assembly for REST endpoints and service layers.

**New exports from `sqlmodel_nexus`:**

| Export | Purpose |
|--------|---------|
| `ErManager` | Central hub — discovers entities from SQLModel base, manages relationships, produces Resolvers |
| `Loader` | Declare DataLoader dependencies in `resolve_*` method signatures |
| `DefineSubset`, `SubsetConfig` | Create independent DTO models from SQLModel entities |
| `ExposeAs`, `SendTo`, `Collector` | Cross-layer data flow (parent→descendant and descendant→ancestor) |
| `Relationship`, `ErDiagram` | Custom non-ORM relationships and Mermaid ER diagram generation |

**Core API usage:**

```python
from sqlmodel import SQLModel
from sqlmodel_nexus import DefineSubset, ErManager, Loader

er = ErManager(base=SQLModel, session_factory=async_session)
Resolver = er.create_resolver()
result = await Resolver(context={"user_id": 1}).resolve(dtos)
```

### New Features

- **`ErManager`** — replaces internal `LoaderRegistry`. Accepts `base` (auto-discovers all `table=True` SQLModel subclasses) or `entities` (explicit list). Provides `create_resolver()` which returns a Resolver **class** bound to the entity graph.
- **Implicit auto-loading** — DTO fields matching ORM relationship names are loaded automatically via DataLoader. No annotation needed; the framework checks field name match + type compatibility with `is_compatible_type`.
- **`is_compatible_type`** — validates that a DTO type is compatible with the relationship's target entity before auto-loading, preventing silent type mismatches at runtime.
- **Resolver metadata caching** — `_ClassMeta` cache avoids repeated `dir()` + `inspect.signature()` calls. Method parameters are analyzed once per class, reused across all instances.
- **`scan_expose_fields` / `scan_send_to_fields` caching** — module-level caches for field metadata scanning.
- **`_node_collectors` cleanup** — per-node collector entries are released immediately after traversal, preventing memory growth during large tree resolution.
- **`_extract_sort_field` supports `desc()` / `asc()`** — handles SQLAlchemy `UnaryExpression` in `order_by` clauses.
- **`get_loader_by_name` ambiguity warning** — logs a warning when multiple entities share the same relationship name.
- **FK field lookup from registry** — `query_meta` uses actual FK field names from `ErManager` instead of assuming `{relationship_name}_id` convention.
- **DataLoader factories use closures** — cleaner pattern; configuration captured in closure scope instead of class attributes.

### Removed from Public API

| Removed | Replacement |
|---------|-------------|
| `AutoLoad` | Implicit auto-loading (field name matches relationship + compatible type) |
| `LoaderRegistry` | `ErManager` (alias `LoaderRegistry = ErManager` kept for internal compat) |
| `Resolver` (direct export) | `er.create_resolver()` returns a bound Resolver class |

### Migration from 0.14.0

The 0.14.0 Core API exports were not yet part of a stable release. If you used them from the feature branch:

```python
# Before (0.14.0 feature branch)
from sqlmodel_nexus import LoaderRegistry, Resolver, AutoLoad
registry = LoaderRegistry(entities=[User, Task], session_factory=sf)
result = await Resolver(registry).resolve(dtos)

# After (1.0.0)
from sqlmodel_nexus import ErManager
er = ErManager(base=SQLModel, session_factory=sf)
Resolver = er.create_resolver()
result = await Resolver().resolve(dtos)
```

`AutoLoad()` annotations can be removed — implicit auto-loading handles it when field names match relationships.

### GraphQL Mode

No breaking changes. All existing `GraphQLHandler` usage works unchanged.


## 0.13.0

- Add `AutoQueryConfig` for auto-generating `by_id` and `by_filter` queries for SQLModel entities
- `by_id`: find a single entity by primary key
- `by_filter`: filter entities by field values with auto-generated `FilterInput` type
- Pass `auto_query_config` to `GraphQLHandler` to enable; handler discovers all entity subclasses automatically
- Update README.md with Auto-Generated Standard Queries documentation

## 0.12.0
- migrate from mcp to fastmcp

## 0.11.0

- Update README.md to emphasize rapid development of minimum viable systems
- Add 30-Second Quick Start section for quick onboarding
- Embed GraphiQL HTML template into the library
- Add `get_graphiql_html()` method to `GraphQLHandler` with configurable `endpoint` parameter

## 0.10.0

- add `allow_mutation` option to `create_mcp_server` to enable mutation support in the generated GraphQL server. This allows clients to perform create, update, and delete operations on the data models defined in the SQLModel schema.