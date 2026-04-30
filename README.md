# SQLModel Nexus

> From SQLModel to running GraphQL API, Core API DTOs, and MCP Server — with zero boilerplate.

[![pypi](https://img.shields.io/pypi/v/sqlmodel-nexus.svg)](https://pypi.python.org/pypi/sqlmodel-nexus)
[![PyPI Downloads](https://static.pepy.tech/badge/sqlmodel-nexus/month)](https://pepy.tech/projects/sqlmodel-nexus)
![Python Versions](https://img.shields.io/pypi/pyversion/sqlmodel-nexus)

## Read This README in Order

We reuse one example throughout: **Sprint → Task → User**.

- A `Sprint` has many `Task`s
- A `Task` has one `owner` (a `User`)
- The API also wants derived fields such as `task_count` and `contributors`

The concepts appear in this order on purpose:

1. **GraphQL Mode** — the fastest path from SQLModel to a running API
2. **Core API Mode** — DefineSubset DTOs for REST endpoints, progressing from implicit auto-loading to `resolve_*`, `post_*`, and cross-layer data flow
3. **MCP Server** — expose the same models to AI assistants

## What sqlmodel-nexus Gives You

| Need | What you write | What the framework does |
|------|----------------|-------------------------|
| GraphQL API | `@query` / `@mutation` on SQLModel methods | Auto-generates SDL, resolves relationships via DataLoader |
| REST / use-case DTOs | `DefineSubset` + field declarations | Implicit auto-loading, N+1 prevention, ORM→DTO conversion |
| Derived fields | `post_*` methods | Runs after all nested data is resolved |
| Cross-layer data flow | `ExposeAs`, `SendTo`, `Collector` | Pass context down or aggregate values up |
| Non-ORM relationships | `Relationship(...)` on entity | Same DataLoader infra, same auto-loading |
| AI-ready APIs | `config_simple_mcp_server(base=...)` | Progressive-disclosure MCP tools |

## Install

```bash
pip install sqlmodel-nexus
pip install sqlmodel-nexus[fastmcp]  # with MCP support
```

---

## GraphQL Mode

The fastest path: SQLModel + `@query` decorator → running GraphQL API.

### 30-Second Quick Start

```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Relationship, select
from sqlmodel_nexus import query, mutation, GraphQLHandler

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str

class Post(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    author_id: int = Field(foreign_key="user.id")
    author: User | None = Relationship(back_populates="posts")

    @query
    async def get_all(cls, limit: int = 10) -> list['Post']:
        """Get all posts."""
        async with get_session() as session:
            return (await session.exec(select(cls).limit(limit))).all()

    @mutation
    async def create(cls, title: str, author_id: int) -> 'Post':
        """Create a new post."""
        async with get_session() as session:
            post = cls(title=title, author_id=author_id)
            session.add(post)
            await session.commit()
            await session.refresh(post)
            return post

handler = GraphQLHandler(base=SQLModel, session_factory=async_session)

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

Run `uvicorn app:app` and visit `http://localhost:8000/graphql`.

### Relationships Auto-Resolved

Relationships are resolved automatically via DataLoader. No `selectinload`, no manual joins:

```graphql
{
  postGetAll(limit: 5) {
    id
    title
    author { name email }
  }
}
```

The framework walks the GraphQL selection tree level-by-level, collects FK values, and batch-loads via DataLoader. **One query per relationship, regardless of result size.**

### Pagination

Add `order_by` to list relationships for automatic pagination support:

```python
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    posts: list["Post"] = Relationship(
        back_populates="author",
        sa_relationship_kwargs={"order_by": "Post.id"},
    )

handler = GraphQLHandler(base=SQLModel, session_factory=async_session, enable_pagination=True)
```

```graphql
{
  userGetAll {
    name
    posts(limit: 3, offset: 0) {
      items { title }
      pagination { has_more total_count }
    }
  }
}
```

### Auto-Generated Standard Queries

Skip `@query` decorators entirely — let the framework generate `by_id` and `by_filter` for every entity:

```python
from sqlmodel_nexus import GraphQLHandler, AutoQueryConfig

handler = GraphQLHandler(
    base=SQLModel,
    session_factory=async_session,
    auto_query_config=AutoQueryConfig(session_factory=async_session),
)
```

```graphql
{ userById(id: 1) { name email } }
{ userByFilter(filter: { name: "Alice" }, limit: 5) { id name } }
```

---

## Core API Mode

Use Core API mode when you want the same DataLoader-based batching outside GraphQL — for FastAPI REST endpoints, service-layer response assembly, or any use-case DTO.

The concepts progress in order: **auto-loading → resolve_\* → post_\* → cross-layer flow**.

### Step 1: DefineSubset + Implicit Auto-Loading

The simplest Core API case: select fields from SQLModel entities, declare relationship fields — they load automatically.

```python
from sqlmodel import SQLModel
from sqlmodel_nexus import DefineSubset, ErManager

class UserDTO(DefineSubset):
    __subset__ = (User, ("id", "name"))

class TaskDTO(DefineSubset):
    __subset__ = (Task, ("id", "title", "owner_id"))
    owner: UserDTO | None = None   # name matches Task.owner relationship → auto-loaded

class SprintDTO(DefineSubset):
    __subset__ = (Sprint, ("id", "name"))
    tasks: list[TaskDTO] = []      # name matches Sprint.tasks relationship → auto-loaded

# App startup — once
er = ErManager(base=SQLModel, session_factory=async_session)
Resolver = er.create_resolver()

# Per request
async def get_sprints():
    async with async_session() as session:
        sprints = (await session.exec(select(Sprint))).all()
    dtos = [SprintDTO(id=s.id, name=s.name) for s in sprints]
    return await Resolver().resolve(dtos)
```

**How it works:**
- `ErManager` discovers all SQLModel entities and their ORM relationships
- `create_resolver()` returns a Resolver class bound to that entity graph
- When resolving, if a field name matches a relationship and the DTO type is compatible with the target entity, it's loaded via DataLoader automatically
- FK fields (like `owner_id`) are hidden from serialization output but available internally

This is the Core API equivalent of GraphQL's relationship resolution — same DataLoader batching, zero `resolve_*` methods needed for standard relationships.

### Step 2: `resolve_*` for Custom Loading

Use `resolve_*` when implicit auto-loading doesn't fit: the field name doesn't match a relationship, or you need custom logic.

```python
from pydantic_resolve import Loader

async def comments_loader(task_ids: list[int]) -> list[list[Comment]]:
    """Batch load comments for multiple tasks."""
    ...

class TaskDTO(DefineSubset):
    __subset__ = (Task, ("id", "title", "owner_id"))
    owner: UserDTO | None = None          # implicit — matches Task.owner
    comments: list[CommentDTO] = []       # custom — no matching relationship
    comment_count: int = 0

    def resolve_comments(self, loader=Loader(comments_loader)):
        """Load comments via a custom batch function."""
        return loader.load(self.id)

    def post_comment_count(self):
        return len(self.comments)
```

`Loader` accepts a DataLoader class or an async batch function:

```python
# By DataLoader class
def resolve_tags(self, loader=Loader(TagLoader)):
    return loader.load(self.id)

# By async batch function
async def load_permissions(user_ids):
    ...
def resolve_permissions(self, loader=Loader(load_permissions)):
    return loader.load(self.owner_id)
```

A useful mental model: **`resolve_*` means "this field needs data from outside the current node."**

### Step 3: `post_*` — Derived Fields After Children Are Ready

`post_*` runs after all `resolve_*` and auto-loading completes for the current subtree. Use it for counts, aggregations, formatting — anything that depends on already-loaded data.

```python
class SprintDTO(DefineSubset):
    __subset__ = (Sprint, ("id", "name"))
    tasks: list[TaskDTO] = []
    task_count: int = 0
    contributor_names: list[str] = []

    def post_task_count(self):
        return len(self.tasks)

    def post_contributor_names(self):
        return sorted({t.owner.name for t in self.tasks if t.owner})
```

Execution order for one SprintDTO:

1. Implicit auto-load → `tasks` filled with TaskDTOs
2. Each TaskDTO → implicit auto-load → `owner` filled
3. `post_task_count` → `len(self.tasks)` = 2
4. `post_contributor_names` → extract unique owner names

| Question | `resolve_*` | `post_*` |
|----------|-------------|----------|
| Needs external IO? | Yes | Usually no |
| Runs before descendants are ready? | Yes | No |
| Good for counts, sums, labels? | Sometimes | Yes |

### Step 4: Cross-Layer Data Flow

Reach for these tools only when parent and child nodes need to coordinate.

- **`ExposeAs`**: send ancestor data downward (parent → descendant)
- **`SendTo` + `Collector`**: send child data upward (descendant → ancestor)

```python
from typing import Annotated
from sqlmodel_nexus import ExposeAs, SendTo, Collector

class SprintDTO(DefineSubset):
    __subset__ = (Sprint, ("id", "name"))
    name: Annotated[str, ExposeAs('sprint_name')]     # expose to descendants
    tasks: list[TaskDTO] = []
    contributors: list[UserDTO] = []

    def post_contributors(self, collector=Collector('contributors')):
        return collector.values()                      # collect from descendants

class TaskDTO(DefineSubset):
    __subset__ = (Task, ("id", "title", "owner_id"))
    owner: Annotated[UserDTO | None, SendTo('contributors')] = None  # send upward
    full_title: str = ""

    def post_full_title(self, ancestor_context):
        return f"{ancestor_context['sprint_name']} / {self.title}"   # read from ancestor
```

Use this only when the shape of the tree matters:
- A child needs ancestor context (sprint name, permissions)
- A parent needs to aggregate values from many descendants (contributors, tags)

### Step 5: Custom Relationships

For relationships that aren't in the ORM (cross-service calls, computed edges), declare them on the entity:

```python
from sqlmodel_nexus import Relationship

async def tags_loader(task_ids: list[int]) -> list[list[Tag]]:
    """Batch load tags for multiple tasks."""
    ...

class Task(SQLModel, table=True):
    __relationships__ = [
        Relationship(fk="id", target=list[Tag], name="tags", loader=tags_loader)
    ]
    id: int | None = Field(default=None, primary_key=True)
    title: str

class TagDTO(DefineSubset):
    __subset__ = (Tag, ("id", "name"))

class TaskDTO(DefineSubset):
    __subset__ = (Task, ("id", "title"))
    tags: list[TagDTO] = []   # name matches custom relationship → auto-loaded
```

Custom relationships use the same DataLoader infrastructure and work with implicit auto-loading.

---

## MCP Integration

Expose your SQLModel APIs to AI assistants with one function call.

### Simple MCP Server

```python
from sqlmodel_nexus.mcp import config_simple_mcp_server

mcp = config_simple_mcp_server(base=SQLModel, name="My API")
mcp.run()  # stdio mode
```

Tools: `get_schema()`, `graphql_query(query)`, `graphql_mutation(mutation)`.

### Multi-App MCP Server

```python
from sqlmodel_nexus.mcp import create_mcp_server

mcp = create_mcp_server(
    apps=[
        {"name": "blog", "base": BlogBase, "description": "Blog API"},
        {"name": "shop", "base": ShopBase, "description": "Shop API"},
    ],
    name="Multi-App API",
)
mcp.run()
```

Tools include `list_apps()`, `list_queries(app_name)`, `get_query_schema(name, app_name)`, `graphql_query(query, app_name)`, etc.

```bash
pip install sqlmodel-nexus[fastmcp]
```

---

## Demo

```bash
# GraphQL playground
uv run python -m demo.app
# visit localhost:8000/graphql

# Core API (REST)
uv run uvicorn demo.core_api.app:app --reload
# visit /docs

# MCP server
uv run --with fastmcp python -m demo.mcp_server
```

## License

MIT License
