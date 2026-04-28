# SQLModel GraphQL


[![pypi](https://img.shields.io/pypi/v/sqlmodel-graphql.svg)](https://pypi.python.org/pypi/sqlmodel-graphql)
[![PyPI Downloads](https://static.pepy.tech/badge/sqlmodel-graphql/month)](https://pepy.tech/projects/sqlmodel-graphql)
![Python Versions](https://img.shields.io/pypi/pyversion/sqlmodel-graphql)

**From SQLModel to Running GraphQL API, Core API DTOs, and MCP Server in Minutes**

sqlmodel-graphql is the fastest way to build a minimum viable system:

- **Zero Config GraphQL** - SQLModel classes → GraphQL schema automatically
- **Core API DTO Mode** - DefineSubset + Resolver for REST and use-case responses
- **@query/@mutation Decorators** - Mark methods, get endpoints instantly
- **GraphiQL Built-in** - Interactive debugging playground
- **One-Line MCP Server** - Expose APIs to AI assistants
- **Auto N+1 Prevention** - DataLoader batch loading for relationships
- **Custom Relationships + ER Diagram** - Document and load ORM or non-ORM edges

No schema files. No handwritten GraphQL resolvers. Minimal boilerplate.
Use decorators for GraphQL/MCP, or DefineSubset + Resolver for Core API responses.

## 30-Second GraphQL Quick Start

```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, select
from sqlmodel_graphql import query, GraphQLHandler

# 1. Define your model with @query decorator
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str

    @query
    async def get_all(cls) -> list['User']:
        async with get_session() as session:
            return (await session.exec(select(cls))).all()

# 2. Create GraphQL handler (auto-generates schema)
handler = GraphQLHandler(base=SQLModel)

# 3. Setup FastAPI endpoints
class GraphQLRequest(BaseModel):
    query: str

app = FastAPI()

@app.get("/graphql", response_class=HTMLResponse)
async def graphiql():
    return handler.get_graphiql_html()

@app.post("/graphql")
async def graphql(req: GraphQLRequest):
    return await handler.execute(req.query)
```

Run: `uvicorn app:app` and visit `http://localhost:8000/graphql` for the interactive playground.

## Features

### Rapid Development
- **Zero Config GraphQL** - SQLModel classes become GraphQL schema automatically
- **@query/@mutation Decorators** - Mark methods as GraphQL operations
- **GraphiQL Integration** - Built-in playground for testing and debugging

### Core API Mode
- **DefineSubset + SubsetConfig** - Build DTOs decoupled from SQLModel entities
- **Resolver + AutoLoad** - Traverse DTO trees, batch-load relations, run `post_*` hooks
- **ExposeAs / SendTo / Collector** - Pass context down and aggregate values up
- **Custom Relationship + ErDiagram** - Support non-ORM edges and Mermaid ER documentation

### Smart Optimization
- **Auto N+1 Prevention** - DataLoader batch loading for all relationships
- **Level-by-Level Resolution** - Relationships loaded in batches per depth level
- **Paginated Relationships** - Built-in cursor-free pagination for list relationships

### AI-Ready with MCP
- **One-Line MCP Server** - `config_simple_mcp_server(base=BaseEntity)`
- **Progressive Disclosure** - AI discovers schema, understands, then queries
- **Multi-App Support** - Serve multiple databases through one MCP server

## Installation

```bash
pip install sqlmodel-graphql
```

Or with uv:

```bash
uv add sqlmodel-graphql
uv add sqlmodel-graphql[fastmcp]  # include mcp server
```

## Demo

running GraphQL demo:

```bash
uv run python -m demo.app
# and visit localhost:8000/graphql
```

running MCP demo

```bash
uv run --with fastmcp python -m demo.mcp_server   # stdio mode
uv run --with fastmcp python -m demo.mcp_server --http   # http mode
```

running Core API demo

```bash
uv run uvicorn demo.core_api.app:app --reload
# visit /docs or /api/er-diagram
```


## Core API Quick Start

Use Core API mode when you want the same DataLoader-based batching outside GraphQL,
such as FastAPI REST endpoints or service-layer response assembly.

```python
from sqlmodel_graphql import DefineSubset, LoaderRegistry, Resolver

class UserDTO(DefineSubset):
    __subset__ = (User, ("id", "name"))

class TaskDTO(DefineSubset):
    __subset__ = (Task, ("id", "title", "owner_id"))
    owner: UserDTO | None = None

registry = LoaderRegistry(entities=[User, Task], session_factory=async_session)

tasks = [TaskDTO(id=t.id, title=t.title, owner_id=t.owner_id) for t in orm_tasks]
result = await Resolver(registry).resolve(tasks)
```

Core API mode also supports:

- implicit or explicit `AutoLoad()`
- `post_*` derived fields
- `ExposeAs`, `SendTo`, `Collector` cross-layer data flow
- custom `Relationship(...)` loaders and `ErDiagram.from_sqlmodel(...)`

See `demo.core_api.app` for a complete FastAPI example.


## Quick Start

### 1. Define Your Models

```python
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship, select
from sqlmodel_graphql import query, mutation

class BaseEntity(SQLModel):
    """Base class for all entities."""
    pass

class User(BaseEntity, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str
    posts: list["Post"] = Relationship(
        back_populates="author",
        sa_relationship_kwargs={"order_by": "Post.id"},
    )

    @query
    async def get_all(cls, limit: int = 10) -> list['User']:
        """Get all users."""
        async with get_session() as session:
            stmt = select(cls).limit(limit)
            result = await session.exec(stmt)
            return list(result.all())
    # Generates GraphQL field: userGetAll(limit: Int): [User!]!

    @query
    async def get_by_id(cls, id: int) -> Optional['User']:
        """Get a user by ID."""
        async with get_session() as session:
            stmt = select(cls).where(cls.id == id)
            result = await session.exec(stmt)
            return result.first()
    # Generates GraphQL field: userGetById(id: Int!): User

    @mutation
    async def create(cls, name: str, email: str) -> 'User':
        """Create a new user."""
        async with get_session() as session:
            user = cls(name=name, email=email)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user
    # Generates GraphQL field: userCreate(name: String!, email: String!): User!

class Post(BaseEntity, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    content: str = ""
    author_id: int = Field(foreign_key="user.id")
    author: Optional[User] = Relationship(back_populates="posts")
```

**Note on relationships:** For list relationships, add `sa_relationship_kwargs={"order_by": "Entity.column"}` to enable pagination support.

### 2. Create Handler (Auto-generates SDL)

```python
from sqlmodel_graphql import GraphQLHandler

# With pagination support:
handler = GraphQLHandler(
    base=BaseEntity,
    session_factory=async_session,
    enable_pagination=True,
)

# Get the SDL if needed
sdl = handler.get_sdl()
print(sdl)
```

### 3. Execute Queries

> **Try it live:** Run ` uv run uvicorn demo.app:app --reload` to start a FastAPI server with GraphiQL at http://localhost:8000/graphql

```python
from sqlmodel_graphql import GraphQLHandler

handler = GraphQLHandler(
    base=BaseEntity,
    session_factory=async_session,
    enable_pagination=True,
)

# Relationships are resolved via DataLoader (no N+1)
result = await handler.execute("""
{
  userGetAll(limit: 5) {
    id
    name
    posts(limit: 3) {
      items {
        title
        author { name }
      }
      pagination { has_more total_count }
    }
  }
}
""")
```

### How Relationship Resolution Works

Relationships are resolved automatically via DataLoader — no manual eager loading needed.

**Execution flow:**
1. Root `@query` method returns entity instances (scalar fields only)
2. Framework walks the GraphQL selection tree level-by-level
3. At each level, collects FK values and batch-loads relationships via DataLoader
4. For paginated lists, uses `ROW_NUMBER()` window functions for efficient per-parent pagination

**Benefits:**
- **Automatic N+1 Prevention**: All relationships loaded in batched queries
- **Pagination Support**: `limit`/`offset` on list relationships with `has_more` and `total_count`
- **Zero Configuration**: No `selectinload` or `load_only` needed in user code

## Auto-Generated Standard Queries

Pass `AutoQueryConfig` to `GraphQLHandler` to automatically generate `by_id` and `by_filter` queries for every entity — no `@query` decorator needed.

### Configuration

```python
from sqlmodel_graphql import GraphQLHandler, AutoQueryConfig

config = AutoQueryConfig(
    session_factory=async_session,   # Required: async session factory
    default_limit=10,                # Default limit for by_filter
    generate_by_id=True,             # Generate by_id query
    generate_by_filter=True,         # Generate by_filter query
)

handler = GraphQLHandler(
    base=BaseEntity,
    auto_query_config=config,
    session_factory=async_session,
    enable_pagination=True,
)
```

When `auto_query_config` is provided, the handler discovers **all** entity subclasses (not only those with decorators) and attaches standard queries.

### Generated Queries

For an entity named `User` with primary key `id`:

| Method | GraphQL Field | Return Type | Description |
|--------|--------------|-------------|-------------|
| `by_id` | `userById(id: Int!): User` | `User \| None` | Find a single entity by primary key |
| `by_filter` | `userByFilter(filter: UserFilterInput, limit: Int): [User!]!` | `list[User]` | Filter entities by field values |

**FilterInput** is auto-generated per entity. All fields are optional — only non-`None` values are used as `WHERE` conditions (exact match).

### Example

```graphql
# Get by ID
{
  userById(id: 1) {
    id
    name
    email
    posts { title }
  }
}

# Filter by fields
{
  userByFilter(filter: { name: "Alice" }, limit: 5) {
    id
    name
    email
  }
}

# List all (no filter)
{
  userByFilter(limit: 20) {
    id
    name
  }
}
```

**Notes:**
- `by_id` requires exactly one primary key field (detected from `id` field or `primary_key=True`).
- `by_filter` supports exact match only; for complex queries, write custom `@query` methods.
- Existing methods on the entity are not overridden.

## MCP Integration

Turn your SQLModel entities into AI-ready tools with a single function call.

### Simple MCP Server (Single App)

For single-application scenarios with one database:

```python
from sqlmodel_graphql.mcp import config_simple_mcp_server
from myapp.models import BaseEntity

# Create simplified MCP server - only 3 tools, no app_name required
mcp = config_simple_mcp_server(
    base=BaseEntity,
    name="My Blog API",
    desc="Blog system with users and posts"
)

# Run for AI assistants (Claude Desktop, etc.)
mcp.run()  # stdio mode (default)
# mcp.run(transport="streamable-http")  # HTTP mode
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base` | `type` | Required | SQLModel base class. All subclasses with `@query`/`@mutation` decorators will be automatically discovered. |
| `name` | `str` | `"SQLModel GraphQL API"` | Name of the MCP server (shown in MCP clients). |
| `desc` | `str \| None` | `None` | Optional description for the GraphQL schema (used for both Query and Mutation type descriptions). |
| `allow_mutation` | `bool` | `False` | If `True`, registers `graphql_mutation` tool and includes Mutation type in schema. Default is read-only mode. |

**Available Tools (3 tools):**

| Tool | Description |
|------|-------------|
| `get_schema()` | Get the complete GraphQL schema in SDL format |
| `graphql_query(query)` | Execute GraphQL queries |
| `graphql_mutation(mutation)` | Execute GraphQL mutations |

**Example: AI Query Flow:**

```
AI: What's available?
    → get_schema() → Returns full SDL

AI: Get users with their posts
    → graphql_query(query="{ userGetUsers(limit: 10) { id name posts { title } } }")

AI: Create a new user
    → graphql_mutation(mutation="mutation { userCreate(name: \"Alice\", email: \"alice@example.com\") { id name } }")
```

### Multi-App MCP Server

For scenarios with multiple independent databases:

```python
from sqlmodel_graphql.mcp import create_mcp_server
from myapp.blog_models import BlogBaseEntity
from myapp.shop_models import ShopBaseEntity

apps = [
    {
        "name": "blog",
        "base": BlogBaseEntity,
        "description": "Blog system API",
    },
    {
        "name": "shop",
        "base": ShopBaseEntity,
        "description": "E-commerce system API",
    }
]

mcp = create_mcp_server(apps=apps, name="My Multi-App API")
mcp.run()
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `apps` | `list[AppConfig]` | Required | List of app configurations. Each app has its own GraphQL schema and independent database. |
| `name` | `str` | `"Multi-App SQLModel GraphQL API"` | Name of the MCP server (shown in MCP clients). |
| `allow_mutation` | `bool` | `False` | If `True`, registers mutation-related tools (`list_mutations`, `get_mutation_schema`, `graphql_mutation`). Default is read-only mode. |

**AppConfig Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Unique identifier for the application (e.g., "blog", "shop"). |
| `base` | `type[SQLModel]` | Yes | SQLModel base class for this application. |
| `description` | `str \| None` | No | Human-readable description of the application. |
| `query_description` | `str \| None` | No | Description for the Query type in GraphQL schema. |
| `mutation_description` | `str \| None` | No | Description for the Mutation type in GraphQL schema. |

**Available Tools (8 tools with app routing):**

| Tool | Description |
|------|-------------|
| `list_apps()` | List all available applications |
| `list_queries(app_name)` | List queries for an app |
| `list_mutations(app_name)` | List mutations for an app |
| `get_query_schema(name, app_name)` | Get query schema details |
| `get_mutation_schema(name, app_name)` | Get mutation schema details |
| `graphql_query(query, app_name)` | Execute GraphQL queries |
| `graphql_mutation(mutation, app_name)` | Execute GraphQL mutations |

### Installation

```bash
pip install sqlmodel-graphql[fastmcp]
```

### Running MCP Server

```bash
uv run --with fastmcp python -m demo.mcp_server   # stdio mode
uv run --with fastmcp python -m demo.mcp_server --http   # http mode
```

## API Reference

### `@query`

Mark a method as a GraphQL query. The field name is auto-generated as `{entityName}{MethodName}` in camelCase.

```python
@query
async def get_all(cls, limit: int = 10) -> list['User']:
    """Get all users."""  # Docstring becomes the field description
    ...
# Generates: userGetAll(limit: Int): [User!]!
```

### `@mutation`

Mark a method as a GraphQL mutation. The field name is auto-generated as `{entityName}{MethodName}` in camelCase.

```python
@mutation
async def create(cls, name: str, email: str) -> 'User':
    """Create a new user."""
    ...
# Generates: userCreate(name: String!, email: String!): User!
```

### `GraphQLHandler`

Execute GraphQL queries against SQLModel entities with auto-discovery.

```python
# Recommended: Use base class with session_factory
handler = GraphQLHandler(
    base=BaseEntity,
    session_factory=async_session,
    enable_pagination=True,
)

# Execute queries
result = await handler.execute("{ userGetAll { id name posts { items { title } } } }")

# Get SDL
sdl = handler.get_sdl()

# Get GraphiQL HTML (for interactive playground)
html = handler.get_graphiql_html()  # defaults to /graphql endpoint
html = handler.get_graphiql_html(endpoint="/api/graphql")  # custom endpoint
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base` | `type` | Required | SQLModel base class for entity discovery. |
| `session_factory` | `Callable \| None` | `None` | Async session factory for DataLoader queries. Required for relationship resolution. |
| `auto_query_config` | `AutoQueryConfig \| None` | `None` | Auto-generate by_id/by_filter queries. |
| `enable_pagination` | `bool` | `False` | Enable pagination for list relationships. |
| `query_description` | `str \| None` | `None` | Custom description for Query type. |
| `mutation_description` | `str \| None` | `None` | Custom description for Mutation type. |

**Auto-Discovery Features:**
- Automatically finds all SQLModel subclasses with `@query/@mutation` decorators
- Includes all related entities through Relationship fields
- Supports custom base classes for better organization
- Recursive discovery of nested relationships

## License

MIT License
