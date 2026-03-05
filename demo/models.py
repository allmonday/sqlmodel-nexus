"""SQLModel entity definitions for the demo application."""

from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel, select

from sqlmodel_graphql import mutation, query, QueryMeta


class User(SQLModel, table=True):
    """User entity."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str

    @query(name="users", description="Get all users with optional limit")
    async def get_all(
        cls, limit: int = 10, query_meta: QueryMeta = None
    ) -> list[User]:
        """Get all users with optional limit."""
        from database import async_session

        async with async_session() as session:
            stmt = select(cls).limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @query(name="user", description="Get a user by ID")
    async def get_by_id(cls, id: int, query_meta: QueryMeta = None) -> Optional[User]:
        """Get a user by ID."""
        from database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.id == id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

    @mutation(name="create_user", description="Create a new user")
    async def create(cls, name: str, email: str) -> User:
        """Create a new user."""
        from database import async_session

        async with async_session() as session:
            user = cls(name=name, email=email)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user


class Post(SQLModel, table=True):
    """Post entity."""

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    content: str
    author_id: int = Field(foreign_key="user.id")

    @query(name="posts", description="Get all posts with optional limit")
    async def get_all(
        cls, limit: int = 10, query_meta: QueryMeta = None
    ) -> list[Post]:
        """Get all posts with optional limit."""
        from database import async_session

        async with async_session() as session:
            stmt = select(cls).limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @query(name="post", description="Get a post by ID")
    async def get_by_id(cls, id: int, query_meta: QueryMeta = None) -> Optional[Post]:
        """Get a post by ID."""
        from database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.id == id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

    @query(name="posts_by_author", description="Get posts by author ID")
    async def get_by_author(
        cls, author_id: int, limit: int = 10, query_meta: QueryMeta = None
    ) -> list[Post]:
        """Get posts by author ID."""
        from database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.author_id == author_id).limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @mutation(name="create_post", description="Create a new post")
    async def create(cls, title: str, content: str, author_id: int) -> Post:
        """Create a new post."""
        from database import async_session

        async with async_session() as session:
            post = cls(title=title, content=content, author_id=author_id)
            session.add(post)
            await session.commit()
            await session.refresh(post)
            return post
