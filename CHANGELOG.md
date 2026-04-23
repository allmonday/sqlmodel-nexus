# Changelog

## 0.14.0

### Breaking Changes

- **Remove `QueryMeta`** — the entire `QueryMeta` / `to_options()` mechanism has been replaced by DataLoader-based relationship resolution. User code no longer needs `query_meta` parameters or `stmt.options()` calls.

### New Features

- **DataLoader relationship resolution** — relationships are now loaded level-by-level via batched DataLoaders (using `aiodataloader`), eliminating N+1 queries without any user code
- **Pagination for list relationships** — one-to-many and many-to-many relationships support `limit`/`offset` pagination with `has_more` and `total_count`, powered by `ROW_NUMBER()` window functions
- **`enable_pagination`** flag on `GraphQLHandler` — when `True`, list relationships expose `EntityResult` types with `items` + `pagination` fields in the GraphQL schema
- **`session_factory`** parameter on `GraphQLHandler` — required for DataLoader queries; pass your async session factory

### Changes

- `GraphQLHandler` accepts `session_factory` and `enable_pagination` parameters
- SDL generator excludes FK fields from entity types and generates `Pagination` / `EntityResult` types when pagination is enabled
- Introspection generator mirrors SDL behavior: FK field filtering, pagination type awareness, `limit`/`offset` args on list relationship fields
- `@query` / `@mutation` methods no longer receive `query_meta` — relationships are resolved by the framework after the root method returns
- Add `aiodataloader` dependency
- Remove `types.py` (`QueryMeta`, `FieldSelection`, `RelationshipSelection`)

### Migration Guide

1. Remove `from sqlmodel_graphql import QueryMeta`
2. Remove `query_meta: QueryMeta | None = None` from all `@query` / `@mutation` method signatures
3. Remove `if query_meta: stmt = stmt.options(*query_meta.to_options(cls))` blocks
4. Add `sa_relationship_kwargs={"order_by": "Entity.column"}` to list relationships for pagination support
5. Pass `session_factory=async_session` to `GraphQLHandler`


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