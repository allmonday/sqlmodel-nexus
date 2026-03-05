# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-03-06

### Added
- Initial release
- Automatic GraphQL SDL generation from SQLModel classes
- `@query` and `@mutation` decorators for defining GraphQL operations
- `GraphQLHandler` for executing GraphQL queries with auto-discovery support
- `QueryParser` for extracting QueryMeta from GraphQL queries
- `QueryMeta.to_options()` for generating SQLAlchemy query optimizations
- Support for nested relationship queries (User → Posts → Comments)
- Auto-discovery of entities from SQLModel or custom base classes
- Recursive collection of related entities through Relationship fields
- Type extraction from complex type hints (Optional, List, forward references)
- FastAPI integration example with GraphiQL interface
- Comprehensive documentation and examples

### Features
- **Auto-discovery**: Automatically finds all SQLModel entities with `@query/@mutation` decorators
- **Relationship Support**: Includes all related entities through Relationship fields
- **N+1 Prevention**: Automatic `selectinload` and `load_only` generation based on query fields
- **Type Safety**: Full support for Python type hints including forward references
- **Framework Agnostic**: Can be integrated with any web framework (FastAPI, Flask, etc.)

### Documentation
- README with quick start guide
- API reference documentation
- How it works explanation
- Demo application with examples
- Release guide for maintainers

## [Unreleased]

### Planned
- Subscription support
- More database backends (PostgreSQL, MySQL)
- Custom scalar types
- Input type generation
- Better error messages
- Performance benchmarks
