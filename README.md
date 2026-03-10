# SQLModel GraphQL


[![pypi](https://img.shields.io/pypi/v/sqlmodel-graphql.svg)](https://pypi.python.org/pypi/sqlmodel-graphql)
[![PyPI Downloads](https://static.pepy.tech/badge/sqlmodel-graphql/month)](https://pepy.tech/projects/sqlmodel-graphql)
![Python Versions](https://img.shields.io/pypi/pyversions/sqlmodel-graphql)

**Generate GraphQL APIs & MCP from SQLModel — zero configuration required**

No schema files. No resolvers. No boilerplate.

Just decorators and Python. Your SQLModel classes become GraphQL APIs instantly.

Plus: expose your GraphQL via MCP to AI assistants (Claude, GPT, etc.) with **three-layer progressive disclosure** — AI discovers what's available, understands the schema, then executes queries efficiently.

## Features

- **Automatic SDL Generation**: Generate GraphQL schema from SQLModel classes
- **@query/@mutation Decorators**: Mark methods as GraphQL operations
- **Query Optimization**: Parse GraphQL queries to generate optimized SQLAlchemy queries
- **N+1 Prevention**: Automatic `selectinload` and `load_only` generation
- **MCP Integration**: Expose GraphQL as MCP tools with progressive disclosure for minimal context usage

## Installation

```bash
pip install sqlmodel-graphql
```

Or with uv:

```bash
uv add sqlmodel-graphql
uv add sqlmodel-graphql[mcp]  # include mcp server
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

    @query(name='users')
    async def get_all(cls, limit: int = 10, query_meta: QueryMeta | None = None) -> list['User']:
        """Get all users with optional query optimization."""
        async with get_session() as session:
            stmt = select(cls).limit(limit)
            if query_meta:
                # Apply optimization: only load requested fields and relationships
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @query(name='user')
    async def get_by_id(cls, id: int, query_meta: QueryMeta | None = None) -> Optional['User']:
        async with get_session() as session:
            stmt = select(cls).where(cls.id == id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

    @mutation(name='createUser')
    async def create(cls, name: str, email: str, query_meta: QueryMeta) -> 'User':
        """Create a new user. query_meta is injected for relationship loading."""
        async with get_session() as session:
            user = cls(name=name, email=email)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            # Re-query with query_meta to load relationships if requested
            stmt = select(cls).where(cls.id == user.id)
            stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

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

1. Framework parses GraphQL query: `{ users { name posts { title } } }`
2. Creates QueryMeta with field selections and relationships
3. Injects it into your `@query` method
4. `query_meta.to_options(Entity)` generates optimized SQLAlchemy options

**Benefits:**

- **Automatic N+1 Prevention**: Related data is loaded in batches, not individual queries
- **Field Selection**: Only requested fields are loaded from database
- **Zero Configuration**: Works automatically, no manual optimization needed

**Example transformation:**

```
GraphQL Query:                    SQLAlchemy Optimization:
────────────────                 ────────────────────────
{ users {                         select(User).options(
  name                              load_only(User.name),
  posts {                           selectinload(User.posts).options(
    title                             load_only(Post.title)
  }                                 )
}                                 )
```

Without `query_meta`, loading 10 users with posts would execute:
- 1 query for users
- 10 queries for posts (N+1 problem!)

With `query_meta`, it executes:
- 1 query for users
- 1 query for all posts (batched!)

**Usage Pattern:**

```python
@query(name='users')
async def get_users(cls, query_meta: QueryMeta | None = None) -> list['User']:
    async with get_session() as session:
        stmt = select(cls)
        if query_meta:
            stmt = stmt.options(*query_meta.to_options(cls))
        result = await session.exec(stmt)
        return list(result.all())
```

**Key Points:**

- `query_meta` is optional (`QueryMeta | None = None`)
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
  author: User!
}

type Query {
  users(limit: Int): [User!]!
  user(id: Int!): User
}

type Mutation {
  createUser(name: String!, email: String!): User!
}
```

### 3. Execute Queries with GraphQLHandler

```python
from sqlmodel_graphql import GraphQLHandler

# Create handler with base class - auto-discovers all entities
handler = GraphQLHandler(base=BaseEntity)

# Execute a GraphQL query
result = await handler.execute("""
{
  users(limit: 5) {
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
#     "users": [
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

```python
from sqlmodel_graphql.mcp import create_mcp_server
from myapp.models import BaseEntity

# Create MCP server from your base class
# All SQLModel subclasses with @query/@mutation decorators are auto-discovered
mcp = create_mcp_server(
    base=BaseEntity,
    name="My Blog API"
)

# Run for AI assistants (Claude Desktop, etc.)
mcp.run()  # stdio mode (default)
# mcp.run(transport="streamable-http")  # HTTP mode
```

### Available MCP Tools

The server exposes six tools with three-layer progressive disclosure:

**Layer 1 - Discover:**
- **list_queries** - List all available queries with names and descriptions
- **list_mutations** - List all available mutations with names and descriptions

**Layer 2 - Understand:**
- **get_query_schema** - Get detailed schema for a specific query (SDL or introspection format)
- **get_mutation_schema** - Get detailed schema for a specific mutation

**Layer 3 - Execute:**
- **graphql_query** - Execute GraphQL queries directly
- **graphql_mutation** - Execute GraphQL mutations directly

### Example: AI Query Flow

```
AI: What queries are available?
    → list_queries() → Returns: [{"name": "users", "description": "Get all users"}, ...]

AI: Tell me about the "users" query
    → get_query_schema(name="users", response_type="sdl")
    → Returns:
       # Query
       users(limit: Int): [User!]!

       # Related Types
       type User {
         id: Int!
         name: String!
         email: String!
         posts: [Post!]!
       }

AI: Get users with their posts
    → graphql_query(query="{ users(limit: 10) { id name posts { title } } }")

AI: Create a new user
    → graphql_mutation(query="mutation { createUser(name: \"Alice\", email: \"alice@example.com\") { id name } }")
```

### Why MCP?

**Three-Layer Progressive Disclosure:**
- Layer 1: Lightweight operation lists (~50 tokens)
- Layer 2: On-demand schema details with SDL format
- Layer 3: Direct GraphQL execution

**Benefits:**
- AI discovers schema dynamically
- SDL format is compact and AI-friendly
- Standard GraphQL syntax - no custom formats to learn
- Minimal context usage for large schemas

### Installation

```bash
# Core library
pip install sqlmodel-graphql[mcp]
```

### Running MCP Server

```bash
# demo/mcp_server.py
uv run python --with mcp demo/mcp_server.py           # stdio mode
uv run python --with mcp demo/mcp_server.py --http    # HTTP mode
```

## API Reference

### `@query(name=None, description=None)`

Mark a method as a GraphQL query.

```python
@query(name='users', description='Get all users')
async def get_all(cls, limit: int = 10, query_meta: Optional[QueryMeta] = None) -> list['User']:
    ...
```

### `@mutation(name=None, description=None)`

Mark a method as a GraphQL mutation. If the mutation returns an entity type, `query_meta` is automatically injected.

```python
@mutation(name='createUser')
async def create(cls, name: str, email: str, query_meta: QueryMeta) -> 'User':
    """Create a new user."""
    async with get_session() as session:
        user = cls(name=name, email=email)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        # Re-query with query_meta to load relationships
        stmt = select(cls).where(cls.id == user.id)
        stmt = stmt.options(*query_meta.to_options(cls))
        result = await session.exec(stmt)
        return result.first()
```

**Note:** `query_meta` is only injected when the return type is an entity. For scalar returns (e.g., `bool`, `str`), it is not passed.

### `SDLGenerator(entities)`

Generate GraphQL SDL from SQLModel classes.

```python
generator = SDLGenerator([User, Post])
sdl = generator.generate()
```

### `GraphQLHandler(base)`
Execute GraphQL queries against SQLModel entities with auto-discovery.

```python
# Recommended: Use base class for auto-discovery
handler = GraphQLHandler(base=BaseEntity)

# Execute queries
result = await handler.execute("{ users { id name } }")

# Get SDL
sdl = handler.get_sdl()
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
