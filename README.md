# SQLModel GraphQL


[![pypi](https://img.shields.io/pypi/v/sqlmodel-graphql.svg)](https://pypi.python.org/pypi/sqlmodel-graphql)
[![PyPI Downloads](https://static.pepy.tech/badge/sqlmodel-graphql/month)](https://pepy.tech/projects/sqlmodel-graphql)
![Python Versions](https://img.shields.io/pypi/pyversions/sqlmodel-graphql)

**From SQLModel to Running GraphQL API + MCP Server in Minutes**

sqlmodel-graphql is the fastest way to build a minimum viable system:

- **Zero Config GraphQL** - SQLModel classes → GraphQL schema automatically
- **@query/@mutation Decorators** - Mark methods, get endpoints instantly
- **GraphiQL Built-in** - Interactive debugging playground
- **One-Line MCP Server** - Expose APIs to AI assistants
- **Auto N+1 Prevention** - Query optimization handled for you

No schema files. No resolvers. No boilerplate.
Just add decorators to your SQLModel classes.

## 30-Second Quick Start

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

### Smart Optimization
- **Auto N+1 Prevention** - `selectinload` and `load_only` generated automatically
- **Query-Aware Loading** - Only fetch requested fields and relationships
- **QueryMeta Injection** - Framework analyzes queries and optimizes database calls

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
uv add sqlmodel-graphql[mcp]  # include mcp server
```

## Demo

running GraphQL demo:

```bash
uv run python -m demo.app 
# and visit localhost:8000/graphql
```

running MCP demo

```bash
uv run --with mcp python -m demo.mcp_server   # stdio mode
uv run --with mcp python -m demo.mcp_server --http   # http mode
```


## Quick Start

### 1. Define Your Models

```python
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship, select
from sqlmodel_graphql import query, mutation, QueryMeta

class BaseEntity(SQLModel):
    """Base class for all entities."""
    pass

class User(BaseEntity, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str
    posts: list["Post"] = Relationship(back_populates="author")

    @query
    async def get_all(cls, limit: int = 10, query_meta: QueryMeta | None = None) -> list['User']:
        """Get all users with optional query optimization."""
        async with get_session() as session:
            stmt = select(cls).limit(limit)
            if query_meta:
                # Apply optimization: only load requested fields and relationships
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())
    # Generates GraphQL field: userGetAll(limit: Int): [User!]!

    @query
    async def get_by_id(cls, id: int, query_meta: QueryMeta | None = None) -> Optional['User']:
        """Get a user by ID."""
        async with get_session() as session:
            stmt = select(cls).where(cls.id == id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()
    # Generates GraphQL field: userGetById(id: Int!): User

    @mutation
    async def create(cls, name: str, email: str, query_meta: QueryMeta | None = None) -> 'User':
        """Create a new user. query_meta is injected for relationship loading."""
        async with get_session() as session:
            user = cls(name=name, email=email)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            # Re-query with query_meta to load relationships if requested
            if query_meta:
                stmt = select(cls).where(cls.id == user.id)
                stmt = stmt.options(*query_meta.to_options(cls))
                result = await session.exec(stmt)
                return result.first()
            return user
    # Generates GraphQL field: userCreate(name: String!, email: String!): User!

class Post(BaseEntity, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    content: str = ""
    author_id: int = Field(foreign_key="user.id")
    author: Optional[User] = Relationship(back_populates="posts")
```

### Understanding query_meta

The `query_meta` parameter is automatically injected by the framework to optimize your database queries. It analyzes the GraphQL query's field selections and generates SQLAlchemy optimizations to prevent N+1 queries.

**How it works:**

1. Framework parses GraphQL query: `{ userGetAll { name posts { title } } }`
2. Creates QueryMeta with field selections and relationships
3. Injects it into your `@query` method (if the parameter exists)
4. `query_meta.to_options(Entity)` generates optimized SQLAlchemy options

**Benefits:**

- **Automatic N+1 Prevention**: Related data is loaded in batches, not individual queries
- **Field Selection**: Only requested fields are loaded from database
- **Zero Configuration**: Works automatically, no manual optimization needed

**Example transformation:**

```
GraphQL Query:                         SQLAlchemy Optimization:
────────────────                      ────────────────────────
{ userGetAll {                         select(User).options(
  name                                   load_only(User.name),
  posts {                                selectinload(User.posts).options(
    title                                  load_only(Post.title)
  }                                      )
}                                      )
```

Without `query_meta`, loading 10 users with posts would execute:
- 1 query for users
- 10 queries for posts (N+1 problem!)

With `query_meta`, it executes:
- 1 query for users
- 1 query for all posts (batched!)

**Usage Pattern:**

```python
@query
async def get_users(cls, query_meta: QueryMeta | None = None) -> list['User']:
    async with get_session() as session:
        stmt = select(cls)
        if query_meta:
            stmt = stmt.options(*query_meta.to_options(cls))
        result = await session.exec(stmt)
        return list(result.all())
# Generates: userGetUsers: [User!]!
```

**Key Points:**

- `query_meta` is optional (`QueryMeta | None = None`) - only injected if the parameter exists
- Always check `if query_meta:` before using
- Works with nested relationships of any depth
- For mutations, only injected when returning entity types (not scalars)

### 2. Create Handler (Auto-generates SDL)

```python
from sqlmodel_graphql import GraphQLHandler

# Create handler - SDL is auto-generated from your models
handler = GraphQLHandler(base=BaseEntity)

# Get the SDL if needed
sdl = handler.get_sdl()
print(sdl)
```

Output:

```graphql
type User {
  id: Int
  name: String!
  email: String!
  posts: [Post!]!
}

type Post {
  id: Int
  title: String!
  content: String!
  author_id: Int!
  author: User
}

type Query {
  """Get all users with optional query optimization."""
  userGetAll(limit: Int): [User!]!

  """Get a user by ID."""
  userGetById(id: Int!): User
}

type Mutation {
  """Create a new user. query_meta is injected for relationship loading."""
  userCreate(name: String!, email: String!): User!
}
```

### 3. Execute Queries with GraphQLHandler

> **Try it live:** Run ` uv run uvicorn demo.app:app --reload` to start a FastAPI server with GraphiQL at http://localhost:8000/graphql

```python
from sqlmodel_graphql import GraphQLHandler

# Create handler with base class - auto-discovers all entities
handler = GraphQLHandler(base=BaseEntity)

# Execute a GraphQL query
result = await handler.execute("""
{
  userGetAll(limit: 5) {
    id
    name
    posts {
      title
      author {
        name
      }
    }
  }
}
""")

# Result includes nested relationships automatically:
# {
#   "data": {
#     "userGetAll": [
#       {
#         "id": 1,
#         "name": "Alice",
#         "posts": [
#           {"title": "Hello World", "author": {"name": "Alice"}},
#           {"title": "GraphQL Tips", "author": {"name": "Alice"}}
#         ]
#       }
#     ]
#   }
# }
```

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
pip install sqlmodel-graphql[mcp]
```

### Running MCP Server

```bash
uv run --with mcp python -m demo.mcp_server   # stdio mode
uv run --with mcp python -m demo.mcp_server --http   # http mode
```

## API Reference

### `@query`

Mark a method as a GraphQL query. The field name is auto-generated as `{entityName}{MethodName}` in camelCase.

```python
@query
async def get_all(cls, limit: int = 10, query_meta: Optional[QueryMeta] = None) -> list['User']:
    """Get all users."""  # Docstring becomes the field description
    ...
# Generates: userGetAll(limit: Int): [User!]!
```

### `@mutation`

Mark a method as a GraphQL mutation. The field name is auto-generated as `{entityName}{MethodName}` in camelCase.

```python
@mutation
async def create(cls, name: str, email: str, query_meta: QueryMeta = None) -> 'User':
    """Create a new user."""
    async with get_session() as session:
        user = cls(name=name, email=email)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        # Re-query with query_meta to load relationships if needed
        if query_meta:
            stmt = select(cls).where(cls.id == user.id)
            stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()
        return user
# Generates: userCreate(name: String!, email: String!): User!
```

**Note:** `query_meta` is only injected when the method has the parameter in its signature AND the return type is an entity. For scalar returns (e.g., `bool`, `str`), it is not passed.

### `GraphQLHandler(base)`
Execute GraphQL queries against SQLModel entities with auto-discovery.

```python
# Recommended: Use base class for auto-discovery
handler = GraphQLHandler(base=BaseEntity)

# Execute queries
result = await handler.execute("{ users { id name } }")

# Get SDL
sdl = handler.get_sdl()

# Get GraphiQL HTML (for interactive playground)
html = handler.get_graphiql_html()  # defaults to /graphql endpoint
html = handler.get_graphiql_html(endpoint="/api/graphql")  # custom endpoint
```

**Auto-Discovery Features:**
- Automatically finds all SQLModel subclasses with `@query/@mutation` decorators
- Includes all related entities through Relationship fields
- Supports custom base classes for better organization
- Recursive discovery of nested relationships

### `QueryParser()`

Parse GraphQL queries to QueryMeta.

```python
parser = QueryParser()
metas = parser.parse("{ users { id name } }")
# metas['users'] -> QueryMeta(fields=[...], relationships={...})
```

### `QueryMeta`

Metadata extracted from GraphQL selection set.

```python
@dataclass
class QueryMeta:
    fields: list[FieldSelection]
    relationships: dict[str, RelationshipSelection]

    def to_options(self, entity: type[SQLModel]) -> list[Any]:
        """Convert to SQLAlchemy options for query optimization."""
```

## License

MIT License
