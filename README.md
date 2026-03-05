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
from sqlmodel import SQLModel, Field, Relationship
from sqlmodel_graphql import query, mutation, SDLGenerator, QueryBuilder

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str
    posts: list["Post"] = Relationship(back_populates="author")

    @query(name='users')
    async def get_all(cls, limit: int = 10) -> list['User']:
        return await fetch_users(limit)

    @query(name='user')
    async def get_by_id(cls, id: int) -> Optional['User']:
        return await fetch_user(id)

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
  authorId: Int!
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

### 3. Optimize Queries with QueryMeta

```python
from sqlmodel_graphql import QueryParser, QueryBuilder

# Parse GraphQL query
parser = QueryParser()
query_metas = parser.parse("""
{
  users {
    id
    name
    posts {
      title
    }
  }
}
""")

# Build optimized SQLAlchemy query
builder = QueryBuilder(User)
stmt = builder.build(query_metas['users'])

# The generated query uses:
# - load_only(User.id, User.name)
# - selectinload(User.posts).options(load_only(Post.title))
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
  QueryBuilder.build()
       ↓
  select(User).options(
    load_only(User.id, User.name),
    selectinload(User.posts).options(load_only(Post.title))
  )
```

## API Reference

### `@query(name=None, description=None)`

Mark a method as a GraphQL query.

```python
@query(name='users', description='Get all users')
async def get_all(cls, limit: int = 10) -> list['User']:
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

### `QueryParser()`

Parse GraphQL queries to QueryMeta.

```python
parser = QueryParser()
metas = parser.parse("{ users { id name } }")
```

### `QueryBuilder(entity)`

Build optimized SQLAlchemy queries from QueryMeta.

```python
builder = QueryBuilder(User)
stmt = builder.build(query_meta)
```

## License

MIT License
