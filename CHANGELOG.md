# Changelog

## 1.0.0

### New Public API: Core API Mode

sqlmodel-graphql now provides a complete Core API mode alongside GraphQL, enabling DTO-first response assembly for REST endpoints and service layers.

**New exports from `sqlmodel_graphql`:**

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
from sqlmodel_graphql import DefineSubset, ErManager, Loader

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
from sqlmodel_graphql import LoaderRegistry, Resolver, AutoLoad
registry = LoaderRegistry(entities=[User, Task], session_factory=sf)
result = await Resolver(registry).resolve(dtos)

# After (1.0.0)
from sqlmodel_graphql import ErManager
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