"""
GraphQL Demo FastAPI Application
Provides a GraphiQL interface for querying SQLModel entities.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any

from sqlmodel_graphql import GraphQLHandler
from models import User, Post
from database import init_db

# GraphiQL HTML (loaded via CDN)
GRAPHIQL_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GraphiQL - SQLModel GraphQL Demo</title>
  <style>
    body { margin: 0; }
    #graphiql { height: 100dvh; }
    .loading {
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 2rem;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
  </style>
  <link rel="stylesheet" href="https://esm.sh/graphiql/dist/style.css" />
  <link rel="stylesheet" href="https://esm.sh/@graphiql/plugin-explorer/dist/style.css" />
  <script type="importmap">
    {
      "imports": {
        "react": "https://esm.sh/react@19.1.0",
        "react/jsx-runtime": "https://esm.sh/react@19.1.0/jsx-runtime",
        "react-dom": "https://esm.sh/react-dom@19.1.0",
        "react-dom/client": "https://esm.sh/react-dom@19.1.0/client",
        "@emotion/is-prop-valid": "data:text/javascript,",
        "graphiql": "https://esm.sh/graphiql?standalone&external=react,react-dom,@graphiql/react,graphql",
        "graphiql/": "https://esm.sh/graphiql/",
        "@graphiql/plugin-explorer": "https://esm.sh/@graphiql/plugin-explorer?standalone&external=react,@graphiql/react,graphql",
        "@graphiql/react": "https://esm.sh/@graphiql/react?standalone&external=react,react-dom,graphql,@emotion/is-prop-valid",
        "@graphiql/toolkit": "https://esm.sh/@graphiql/toolkit?standalone&external=graphql",
        "graphql": "https://esm.sh/graphql@16.11.0"
      }
    }
  </script>
</head>
<body>
  <div id="graphiql">
    <div class="loading">Loading GraphiQL...</div>
  </div>
  <script type="module">
    import React from 'react';
    import ReactDOM from 'react-dom/client';
    import { GraphiQL, HISTORY_PLUGIN } from 'graphiql';
    import { createGraphiQLFetcher } from '@graphiql/toolkit';
    import { explorerPlugin } from '@graphiql/plugin-explorer';

    const fetcher = createGraphiQLFetcher({ url: '/graphql' });
    const plugins = [HISTORY_PLUGIN, explorerPlugin()];

    function App() {
      return React.createElement(GraphiQL, {
        fetcher: fetcher,
        plugins: plugins,
        defaultQuery: `# Welcome to SQLModel GraphQL Demo!
#
# Try these queries:

# Get all users
query GetUsers {
  users(limit: 10) {
    id
    name
    email
  }
}

# Get a specific user by ID
query GetUser {
  user(id: 1) {
    id
    name
    email
  }
}

# Get all posts
query GetPosts {
  posts(limit: 10) {
    id
    title
    content
    author_id
  }
}

# Get posts by author
query GetPostsByAuthor {
  posts_by_author(author_id: 1, limit: 10) {
    id
    title
    content
  }
}

# Create a new user
mutation CreateUser {
  create_user(name: "Charlie", email: "charlie@example.com") {
    id
    name
    email
  }
}

# Create a new post
mutation CreatePost {
  create_post(title: "My New Post", content: "Hello GraphQL!", author_id: 1) {
    id
    title
    content
    author_id
  }
}
`
      });
    }

    const container = document.getElementById('graphiql');
    const root = ReactDOM.createRoot(container);
    root.render(React.createElement(App));
  </script>
</body>
</html>
"""


class GraphQLRequest(BaseModel):
    """GraphQL request model."""

    query: str
    variables: Optional[Dict[str, Any]] = None
    operation_name: Optional[str] = None


# Create GraphQL handler
handler = GraphQLHandler(entities=[User, Post])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await init_db()
    yield


# Create FastAPI application
app = FastAPI(
    title="SQLModel GraphQL Demo",
    description="Demo application for SQLModel GraphQL with GraphiQL interface",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/graphql", response_class=HTMLResponse)
async def graphiql_playground():
    """GraphiQL interactive query interface."""
    return GRAPHIQL_HTML


@app.post("/graphql")
async def graphql_endpoint(req: GraphQLRequest):
    """GraphQL query endpoint."""
    return await handler.execute(
        query=req.query,
        variables=req.variables,
        operation_name=req.operation_name,
    )


@app.get("/schema", response_class=PlainTextResponse)
async def get_schema():
    """Get GraphQL schema in SDL format."""
    return handler.get_sdl()


@app.get("/")
async def root():
    """Root endpoint with usage instructions."""
    return {
        "message": "SQLModel GraphQL Demo Server",
        "endpoints": {
            "graphiql": "/graphql (GET - GraphiQL UI)",
            "graphql": "/graphql (POST - Query endpoint)",
            "schema": "/schema (GET - SDL schema)",
            "docs": "/docs (GET - FastAPI docs)",
        },
        "example_queries": [
            "query { users { id name } }",
            "query { user(id: 1) { name email } }",
            "mutation { create_user(name: 'Test', email: 'test@example.com') { id } }",
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
