"""SQLModel entity definitions for the Core API demo.

Sprint -> Task (one-to-many), Task -> User (many-to-one).
Matches the pydantic-resolve README example pattern.

Level 5 adds Tag entity and a custom non-ORM relationship
(Task -> Tags via __relationships__).
"""

from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

from sqlmodel_graphql import Relationship as CustomRelationship


class User(SQLModel, table=True):
    __tablename__ = "core_api_user"

    id: int | None = Field(default=None, primary_key=True)
    name: str


class Sprint(SQLModel, table=True):
    __tablename__ = "core_api_sprint"

    id: int | None = Field(default=None, primary_key=True)
    name: str

    tasks: list["Task"] = Relationship(
        back_populates="sprint",
        sa_relationship_kwargs={"order_by": "Task.id"},
    )


class Tag(SQLModel, table=True):
    """Tag entity — attached to Tasks via a custom loader (no ORM association table)."""
    __tablename__ = "core_api_tag"

    id: int | None = Field(default=None, primary_key=True)
    name: str


# ── Custom loader for Task -> Tags (non-ORM relationship) ──

async def _tags_by_task_loader(task_ids: list[int]) -> list[list[Tag]]:
    """Load tags for tasks. Uses a simple in-memory mapping.

    In production this would query an association table, e.g.:
        SELECT t.*, tt.task_id FROM core_api_tag t
        JOIN core_api_task_tag tt ON t.id = tt.tag_id
        WHERE tt.task_id IN (:task_ids)
    """
    from demo.core_api.database import async_session
    from sqlmodel import select, col

    async with async_session() as session:
        # For demo simplicity, return all tags for each task
        # In a real app you'd join through an association table
        all_tags = (await session.exec(select(Tag))).all()

    return [list(all_tags) for _ in task_ids]


class Task(SQLModel, table=True):
    __tablename__ = "core_api_task"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    done: bool = False

    sprint_id: int = Field(foreign_key="core_api_sprint.id")
    owner_id: int | None = Field(default=None, foreign_key="core_api_user.id")

    sprint: Optional["Sprint"] = Relationship(back_populates="tasks")
    owner: Optional["User"] = Relationship()

    # Custom non-ORM relationship: load tags via a hand-written async loader
    __relationships__ = [
        CustomRelationship(
            fk="id",
            target=Tag,
            name="tags",
            loader=_tags_by_task_loader,
            is_list=True,
            description="Task tags (loaded via custom loader, not ORM)",
        )
    ]
