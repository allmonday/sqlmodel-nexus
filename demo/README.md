# SQLModel GraphQL Demo

This demo showcases the SQLModel GraphQL library with a GraphiQL interface.

## Running the Demo

```bash
# From project root
uv sync --extra demo

# Start the server
cd demo && uv run uvicorn app:app --reload
```

## Accessing the Interface

- **GraphiQL UI**: http://localhost:8000/graphql
- **GraphQL Endpoint**: POST to http://localhost:8000/graphql
- **Schema (SDL)**: http://localhost:8000/schema
- **API Docs**: http://localhost:8000/docs

## Example Queries

### Get all users with their posts

```graphql
query GetUsers {
  users(limit: 10) {
    id
    name
    email
    posts {
      id
      title
      content
    }
  }
}
```

### Get a specific user

```graphql
query GetUser {
  user(id: 1) {
    id
    name
    email
    posts {
      title
    }
  }
}
```

### Get all posts with author info

```graphql
query GetPosts {
  posts(limit: 10) {
    id
    title
    content
    author {
      id
      name
      email
    }
  }
}
```

### Create a new user

```graphql
mutation CreateUser {
  createUser(name: "Charlie", email: "charlie@example.com") {
    id
    name
    email
  }
}
```

### Create a new post

```graphql
mutation CreatePost {
  createPost(title: "My New Post", content: "Hello GraphQL!", authorId: 1) {
    id
    title
    content
    author {
      name
    }
  }
}
```

## Architecture

```
demo/
├── __init__.py     # Package init
├── app.py          # FastAPI app with GraphiQL
├── models.py       # SQLModel entities with @query/@mutation
├── database.py     # Database configuration
└── README.md       # This file
```

## How It Works

1. **Entities** (`models.py`): Define SQLModel classes with `@query` and `@mutation` decorators
2. **Handler** (`app.py`): `GraphQLHandler` scans entities and builds query/mutation mappings
3. **Execution**: When a query comes in, the handler parses it and calls the appropriate methods
4. **Optimization**: `QueryMeta` is passed to methods for SQLAlchemy query optimization
