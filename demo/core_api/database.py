"""Database configuration and seed data for the Core API demo."""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from demo.core_api.models import Sprint, Tag, Task, User

engine = create_async_engine("sqlite+aiosqlite:///core_api_demo.db", echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Create tables and seed initial data."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with async_session() as session:
        existing = await session.exec(select(User))
        if existing.first():
            return

        # --- Users ---
        users = [
            User(name="Alice"),
            User(name="Bob"),
            User(name="Charlie"),
            User(name="Diana"),
        ]
        for u in users:
            session.add(u)
        await session.commit()
        for u in users:
            await session.refresh(u)

        # --- Sprints ---
        sprints = [
            Sprint(name="Sprint 1"),
            Sprint(name="Sprint 2"),
            Sprint(name="Sprint 3"),
        ]
        for s in sprints:
            session.add(s)
        await session.commit()
        for s in sprints:
            await session.refresh(s)

        # --- Tasks ---
        tasks_data = [
            # Sprint 1 tasks
            ("Setup CI/CD", sprints[0].id, users[0].id, True),
            ("Design database schema", sprints[0].id, users[1].id, True),
            ("Implement auth module", sprints[0].id, users[0].id, False),
            ("Write unit tests", sprints[0].id, users[2].id, False),
            # Sprint 2 tasks
            ("Build REST API", sprints[1].id, users[1].id, True),
            ("Add pagination support", sprints[1].id, users[0].id, True),
            ("Implement search", sprints[1].id, users[3].id, False),
            ("Code review", sprints[1].id, users[2].id, False),
            # Sprint 3 tasks
            ("Performance optimization", sprints[2].id, users[0].id, False),
            ("Deploy to production", sprints[2].id, users[3].id, False),
        ]
        for title, sprint_id, owner_id, done in tasks_data:
            t = Task(title=title, sprint_id=sprint_id, owner_id=owner_id, done=done)
            session.add(t)
        await session.commit()

        # --- Tags ---
        tags = [
            Tag(name="backend"),
            Tag(name="frontend"),
            Tag(name="devops"),
            Tag(name="testing"),
            Tag(name="urgent"),
        ]
        for t in tags:
            session.add(t)
        await session.commit()
