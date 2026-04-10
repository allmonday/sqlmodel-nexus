# Changelog

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