# SQLModel GraphQL

GraphQL SDL generation and query optimization for SQLModel.

## Features

- **Automatic SDL Generation**: Generate GraphQL schema from SQLModel classes
- **@query/@mutation Decorators**: Mark methods as GraphQL operations
- **Query Optimization**: Parse GraphQL queries to generate optimized SQLAlchemy queries
- **N+1 Prevention**: Automatic `selectinload` and `load_only` generation

## Installation

```bash
pip install sqlmodel-graphql
```

Or with uv:

```bash
uv add sqlmodel-graphql
```

## Quick Start

### 1. Define Your Models

```python
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship, select
from sqlmodel_graphql import query, mutation, QueryMeta

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str
    posts: list["Post"] = Relationship(back_populates="author")

    @query(name='users')
    async def get_all(cls, limit: int = 10, query_meta: Optional[QueryMeta] = None) -> list['User']:
        """Get all users with optional query optimization."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).limit(limit)
            if query_meta:
                # Apply optimization: only load requested fields and relationships
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @query(name='user')
    async def get_by_id(cls, id: int, query_meta: Optional[QueryMeta] = None) -> Optional['User']:
        return await fetch_user(id, query_meta)

    @mutation(name='createUser')
    async def create(cls, name: str, email: str) -> 'User':
        return await create_user(name, email)

class Post(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    content: str = ""
    author_id: int = Field(foreign_key="user.id")
    author: User = Relationship(back_populates="posts")
```

### 2. Generate GraphQL SDL

```python
from sqlmodel_graphql import SDLGenerator

generator = SDLGenerator([User, Post])
sdl = generator.generate()
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

handler = GraphQLHandler(entities=[User, Post])

# Execute a GraphQL query
result = await handler.execute("""
{
  users(limit: 5) {
    id
    name
    posts {
      title
    }
  }
}
""")

# Result:
# {
#   "data": {
#     "users": [
#       {"id": 1, "name": "Alice", "posts": [{"title": "Hello World"}]},
#       {"id": 2, "name": "Bob", "posts": [{"title": "GraphQL is Great"}]}
#     ]
#   }
# }
```

## How It Works

```
GraphQL Query                        QueryMeta
─────────────                        ─────────
{ users {                            QueryMeta(
  id                                   fields=[FieldSelection('id'), FieldSelection('name')],
  name                                 relationships={
  posts {                                'posts': RelationshipSelection(
    title                                  fields=[FieldSelection('title')]
  }                                     }
}                                     }
)
       ↓
  query_meta.to_options(User)
       ↓
  select(User).options(
    load_only(User.id, User.name),
    selectinload(User.posts).options(load_only(Post.title))
  )
```

### Query Optimization Flow

1. **GraphQLHandler** receives the query
2. **QueryParser** parses the selection set into **QueryMeta**
3. **QueryMeta** is injected into your `@query` method as `query_meta` parameter
4. **query_meta.to_options(entity)** generates SQLAlchemy options:
   - `load_only()` for requested scalar fields
   - `selectinload()` for requested relationships
5. Database query only fetches what's needed, preventing N+1 problems

## API Reference

### `@query(name=None, description=None)`

Mark a method as a GraphQL query.

```python
@query(name='users', description='Get all users')
async def get_all(cls, limit: int = 10, query_meta: Optional[QueryMeta] = None) -> list['User']:
    ...
```

### `@mutation(name=None, description=None)`

Mark a method as a GraphQL mutation.

```python
@mutation(name='createUser')
async def create(cls, name: str, email: str) -> 'User':
    ...
```

### `SDLGenerator(entities)`

Generate GraphQL SDL from SQLModel classes.

```python
generator = SDLGenerator([User, Post])
sdl = generator.generate()
```

### `GraphQLHandler(entities)`

Execute GraphQL queries against SQLModel entities.

```python
handler = GraphQLHandler(entities=[User, Post])
result = await handler.execute("{ users { id name } }")
```

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
