"""SQLModel entity definitions for the Core API demo.

Entity relationship graph:

    Project ──1:N──→ Sprint ──1:N──→ Task ──1:N──→ Comment
                                        │                │
                                        N:1              N:1
                                        ↓                ↓
                                       User ←────────────┘
                                        │
                                  TaskLabel (M:N 关联表)
                                        │
                                        ↓
                                      Label

Also includes a custom non-ORM relationship: Task -> Tag via __relationships__.
"""

from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

from sqlmodel_nexus import Relationship as CustomRelationship


class User(SQLModel, table=True):
    __tablename__ = "core_api_user"

    id: int | None = Field(default=None, primary_key=True)
    name: str

    comments: list["Comment"] = Relationship(back_populates="author")


class Project(SQLModel, table=True):
    __tablename__ = "core_api_project"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str = ""

    sprints: list["Sprint"] = Relationship(back_populates="project")


class Sprint(SQLModel, table=True):
    __tablename__ = "core_api_sprint"

    id: int | None = Field(default=None, primary_key=True)
    name: str

    project_id: int | None = Field(default=None, foreign_key="core_api_project.id")

    project: Optional["Project"] = Relationship(back_populates="sprints")
    tasks: list["Task"] = Relationship(
        back_populates="sprint",
        sa_relationship_kwargs={"order_by": "Task.id"},
    )


class Tag(SQLModel, table=True):
    """Tag entity — attached to Tasks via a custom loader (no ORM association table)."""
    __tablename__ = "core_api_tag"

    id: int | None = Field(default=None, primary_key=True)
    name: str


class TaskLabel(SQLModel, table=True):
    """Association table for Task ↔ Label many-to-many."""
    __tablename__ = "core_api_task_label"

    task_id: int = Field(foreign_key="core_api_task.id", primary_key=True)
    label_id: int = Field(foreign_key="core_api_label.id", primary_key=True)


class Comment(SQLModel, table=True):
    __tablename__ = "core_api_comment"

    id: int | None = Field(default=None, primary_key=True)
    content: str

    task_id: int = Field(foreign_key="core_api_task.id")
    author_id: int = Field(foreign_key="core_api_user.id")

    task: Optional["Task"] = Relationship(back_populates="comments")
    author: Optional["User"] = Relationship(back_populates="comments")


# ── Custom loader for Task -> Tags (non-ORM relationship) ──

async def _tags_by_task_loader(task_ids: list[int]) -> list[list[Tag]]:
    """Load tags for tasks. Uses a simple in-memory mapping.

    In production this would query an association table, e.g.:
        SELECT t.*, tt.task_id FROM core_api_tag t
        JOIN core_api_task_tag tt ON t.id = tt.tag_id
        WHERE tt.task_id IN (:task_ids)
    """
    from sqlmodel import select

    from demo.core_api.database import async_session

    async with async_session() as session:
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
    comments: list["Comment"] = Relationship(back_populates="task")
    labels: list["Label"] = Relationship(back_populates="tasks", link_model=TaskLabel)

    # Custom non-ORM relationship: load tags via a hand-written async loader
    __relationships__ = [
        CustomRelationship(
            fk="id",
            target=list[Tag],
            name="tags",
            loader=_tags_by_task_loader,
            description="Task tags (loaded via custom loader, not ORM)",
        )
    ]


class Label(SQLModel, table=True):
    """Label entity — attached to Tasks via many-to-many (TaskLabel association)."""
    __tablename__ = "core_api_label"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    color: str = "#999999"

    tasks: list["Task"] = Relationship(back_populates="labels", link_model=TaskLabel)
