"""Database configuration for the auth demo application."""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

# Create async engine with SQLite (separate database for auth demo)
engine = create_async_engine("sqlite+aiosqlite:///auth_demo.db", echo=False)

# Create async session factory
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    """Get an async database session."""
    async with async_session() as session:
        yield session


async def init_db() -> None:
    """Initialize database tables and seed data."""
    from sqlmodel import SQLModel

    from auth_demo.models import Comment, Post, User, UserFavoritePost

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Seed initial data
    async with async_session() as session:
        from sqlmodel import select

        existing = await session.exec(select(User))
        if existing.first():
            return

        # Create sample users
        user1 = User(name="Alice", email="alice@example.com")
        user2 = User(name="Bob", email="bob@example.com")
        user3 = User(name="Charlie", email="charlie@example.com")
        session.add(user1)
        session.add(user2)
        session.add(user3)
        await session.commit()
        await session.refresh(user1)
        await session.refresh(user2)
        await session.refresh(user3)

        # Create sample posts
        post1 = Post(title="Hello World", content="My first post!", author_id=user1.id)
        post2 = Post(
            title="GraphQL is Great",
            content="Learning GraphQL with SQLModel",
            author_id=user1.id,
        )
        post3 = Post(title="Python Tips", content="Some useful Python tips", author_id=user2.id)
        session.add(post1)
        session.add(post2)
        session.add(post3)
        await session.commit()
        await session.refresh(post1)
        await session.refresh(post2)
        await session.refresh(post3)

        # Create sample comments
        comment1 = Comment(content="Great post!", post_id=post1.id, author_id=user2.id)
        comment2 = Comment(content="Thanks for sharing!", post_id=post1.id, author_id=user3.id)
        comment3 = Comment(
            content="GraphQL is indeed amazing!",
            post_id=post2.id,
            author_id=user2.id,
        )
        comment4 = Comment(content="Very helpful tips!", post_id=post3.id, author_id=user1.id)
        comment5 = Comment(
            content="I learned a lot from this!", post_id=post3.id, author_id=user3.id
        )
        session.add(comment1)
        session.add(comment2)
        session.add(comment3)
        session.add(comment4)
        session.add(comment5)
        await session.commit()

        # Create sample favorites
        favorite1 = UserFavoritePost(user_id=user2.id, post_id=post1.id)
        favorite2 = UserFavoritePost(user_id=user3.id, post_id=post1.id)
        favorite3 = UserFavoritePost(user_id=user1.id, post_id=post2.id)
        favorite4 = UserFavoritePost(user_id=user3.id, post_id=post3.id)
        favorite5 = UserFavoritePost(user_id=user1.id, post_id=post3.id)
        session.add(favorite1)
        session.add(favorite2)
        session.add(favorite3)
        session.add(favorite4)
        session.add(favorite5)
        await session.commit()
