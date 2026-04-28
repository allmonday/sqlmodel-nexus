"""Core API Demo — FastAPI application.

Demonstrates sqlmodel-graphql's Core API mode:
- DefineSubset: independent DTOs from SQLModel entities
- AutoLoad: automatic relationship loading with ORM->DTO conversion
- Resolver: model-driven traversal with resolve_/post_ methods
- ExposeAs/SendTo/Collector: cross-layer data flow
- __relationships__: custom non-ORM relationships with hand-written loaders
- ErDiagram: Mermaid ER diagram generation

Run:
    uv run uvicorn demo.core_api.app:app --reload

Endpoints:
    GET /api/tasks              — Task list with auto-loaded owner
    GET /api/sprints            — Sprint list with derived fields (post_*)
    GET /api/sprints/{id}/detail — Sprint detail with cross-layer flow
    GET /api/sprints/with-tags  — Sprint list with custom-loaded tags
    GET /api/er-diagram         — Mermaid ER diagram
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import select

from demo.core_api.database import async_session, init_db
from demo.core_api.dtos import (
    SprintDetail,
    SprintSummary,
    SprintWithTags,
    TaskSummary,
)
from demo.core_api.models import Sprint, Tag, Task, User
from sqlmodel_graphql import ErDiagram, Resolver
from sqlmodel_graphql.loader import LoaderRegistry

# LoaderRegistry inspects ORM metadata and creates DataLoaders for all
# relationships between the provided entities.
registry = LoaderRegistry(
    entities=[User, Sprint, Task, Tag],
    session_factory=async_session,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Core API Demo",
    description="sqlmodel-graphql Core API mode demo",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": "Core API Demo",
        "endpoints": {
            "tasks": "/api/tasks — Task list with owner (resolve_* + Loader)",
            "sprints": "/api/sprints — Sprint list with derived fields (post_*)",
            "sprint_detail": "/api/sprints/{id}/detail — Cross-layer data flow",
            "sprints_with_tags": "/api/sprints/with-tags — Custom __relationships__ + AutoLoad",
            "er_diagram": "/api/er-diagram — Mermaid ER diagram",
            "docs": "/docs — FastAPI docs",
        },
    }


@app.get("/api/tasks")
async def get_tasks():
    """Level 2: resolve_* + Loader — load related data via DataLoader.

    Each TaskSummary has a resolve_owner method that calls
    loader.load(self.owner_id). The DataLoader batches all owner_id
    values and executes a single query.
    """
    async with async_session() as session:
        result = await session.exec(select(Task))
        tasks = [
            TaskSummary(id=t.id, title=t.title, sprint_id=t.sprint_id,
                        owner_id=t.owner_id, done=t.done)
            for t in result.all()
        ]
    return await Resolver(registry).resolve(tasks)


@app.get("/api/sprints")
async def get_sprints():
    """Level 3: post_* — derived fields computed after children are resolved.

    SprintSummary.resolve_tasks loads tasks via DataLoader,
    then each TaskSummary.resolve_owner loads owners,
    then post_task_count and post_contributor_names run.
    """
    async with async_session() as session:
        result = await session.exec(select(Sprint))
        sprints = [
            SprintSummary(id=s.id, name=s.name)
            for s in result.all()
        ]
    return await Resolver(registry).resolve(sprints)


@app.get("/api/sprints/{sprint_id}/detail")
async def get_sprint_detail(sprint_id: int):
    """Level 4: ExposeAs + SendTo + Collector — cross-layer data flow.

    - SprintDetail exposes 'sprint_name' to descendants via ExposeAs
    - TaskDetail.post_full_title reads sprint_name from ancestor_context
    - TaskDetail.owner is collected by SprintDetail.post_contributors
    """
    async with async_session() as session:
        result = await session.exec(
            select(Sprint).where(Sprint.id == sprint_id)
        )
        sprint = result.first()
        if sprint is None:
            return {"error": "Sprint not found"}

    dto = SprintDetail(id=sprint.id, name=sprint.name)
    result = await Resolver(registry).resolve(dto)
    return result


@app.get("/api/er-diagram")
async def get_er_diagram():
    """ErDiagram — generate Mermaid ER diagram from SQLModel metadata.

    Includes both ORM relationships and custom __relationships__.
    """
    diagram = ErDiagram.from_sqlmodel([User, Sprint, Task, Tag])
    return {"mermaid": diagram.to_mermaid()}


@app.get("/api/sprints/with-tags")
async def get_sprints_with_tags():
    """Level 5: Custom __relationships__ + AutoLoad.

    Demonstrates mixing ORM relationships (sprint -> tasks, task -> owner)
    with custom non-ORM relationships (task -> tags via __relationships__).

    - SprintWithTags.tasks: ORM one-to-many (Sprint -> Task)
    - TaskWithTags.owner: ORM many-to-one (Task -> User)
    - TaskWithTags.tags: Custom relationship from __relationships__
      loaded via a hand-written async batch loader
    - post_tag_count: derived field counting custom-loaded tags
    """
    async with async_session() as session:
        result = await session.exec(select(Sprint))
        sprints = [
            SprintWithTags(id=s.id, name=s.name)
            for s in result.all()
        ]
    return await Resolver(registry).resolve(sprints)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
