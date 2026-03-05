"""Database configuration for the demo application."""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

# Create async engine with SQLite
engine = create_async_engine("sqlite+aiosqlite:///demo.db", echo=False)

# Create async session factory
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    """Get an async database session."""
    async with async_session() as session:
        yield session


async def init_db() -> None:
    """Initialize database tables and seed data."""
    from sqlmodel import SQLModel
    from models import User, Post

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Seed initial data
    async with async_session() as session:
        # Check if data already exists
        from sqlmodel import select

        existing = await session.exec(select(User))
        if existing.first():
            return

        # Create sample users
        user1 = User(name="Alice", email="alice@example.com")
        user2 = User(name="Bob", email="bob@example.com")
        session.add(user1)
        session.add(user2)
        await session.commit()
        await session.refresh(user1)
        await session.refresh(user2)

        # Create sample posts
        post1 = Post(title="Hello World", content="My first post!", author_id=user1.id)
        post2 = Post(title="GraphQL is Great", content="Learning GraphQL with SQLModel", author_id=user1.id)
        post3 = Post(title="Python Tips", content="Some useful Python tips", author_id=user2.id)
        session.add(post1)
        session.add(post2)
        session.add(post3)
        await session.commit()
