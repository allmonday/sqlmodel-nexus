"""Test infrastructure: database setup and shared fixtures."""

from typing import Optional

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import Field, Relationship, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

# ──────────────────────────────────────────────────────────
# Test models (Sprint / Task / User for resolve/post/context testing)
# ──────────────────────────────────────────────────────────

class TestBase(SQLModel):
    """Base class for test entities."""
    pass


class TestUser(TestBase, table=True):
    __tablename__ = "test_user"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str

    tasks: list["TestTask"] = Relationship(
        back_populates="owner",
        sa_relationship_kwargs={"order_by": "TestTask.id"},
    )


class TestSprint(TestBase, table=True):
    __tablename__ = "test_sprint"

    id: int | None = Field(default=None, primary_key=True)
    name: str

    tasks: list["TestTask"] = Relationship(
        back_populates="sprint",
        sa_relationship_kwargs={"order_by": "TestTask.id"},
    )


class TestTask(TestBase, table=True):
    __tablename__ = "test_task"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    sprint_id: int = Field(foreign_key="test_sprint.id")
    owner_id: int = Field(foreign_key="test_user.id")

    sprint: Optional["TestSprint"] = Relationship(back_populates="tasks")
    owner: Optional["TestUser"] = Relationship(back_populates="tasks")


# ──────────────────────────────────────────────────────────
# Database engine and session factory
# ──────────────────────────────────────────────────────────

_engine = None
_session_factory = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
        )
    return _engine


def get_test_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def init_test_db():
    """Create all tables."""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def seed_test_data():
    """Insert seed data for testing."""
    session_factory = get_test_session_factory()
    async with session_factory() as session:
        # Check existing
        result = await session.exec(select(TestUser))
        if result.first():
            return

        # Users
        users = [
            TestUser(name="Alice", email="alice@test.com"),
            TestUser(name="Bob", email="bob@test.com"),
        ]
        for u in users:
            session.add(u)
        await session.commit()
        for u in users:
            await session.refresh(u)

        # Sprints
        sprints = [
            TestSprint(name="Sprint 1"),
            TestSprint(name="Sprint 2"),
        ]
        for s in sprints:
            session.add(s)
        await session.commit()
        for s in sprints:
            await session.refresh(s)

        # Tasks
        tasks = [
            TestTask(title="Task A", sprint_id=sprints[0].id, owner_id=users[0].id),
            TestTask(title="Task B", sprint_id=sprints[0].id, owner_id=users[1].id),
            TestTask(title="Task C", sprint_id=sprints[1].id, owner_id=users[0].id),
            TestTask(title="Task D", sprint_id=sprints[1].id, owner_id=users[1].id),
        ]
        for t in tasks:
            session.add(t)
        await session.commit()
        for t in tasks:
            await session.refresh(t)


@pytest_asyncio.fixture
async def test_db():
    """Create tables and seed data for resolve/post/context tests.

    Not autouse — only used by tests that need the test models.
    """
    await init_test_db()
    await seed_test_data()
    yield
    # Cleanup: drop tables to ensure isolation between tests
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
