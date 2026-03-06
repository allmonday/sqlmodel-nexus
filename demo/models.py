"""SQLModel entity definitions for the demo application."""

from typing import Optional

from sqlmodel import Field, Relationship, SQLModel, select

from sqlmodel_graphql import mutation, query, QueryMeta


class BaseEntity(SQLModel):
    """Base class for all demo entities."""

    pass


class User(BaseEntity, table=True):
    """User entity."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str

    # Relationship: User has many posts
    posts: list["Post"] = Relationship(back_populates="author")

    # Relationship: User has many comments
    comments: list["Comment"] = Relationship(back_populates="author")

    @query(name="users", description="Get all users with optional limit")
    async def get_all(
        cls, limit: int = 10, query_meta: Optional[QueryMeta] = None
    ) -> list["User"]:
        """Get all users with optional limit."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @query(name="user", description="Get a user by ID")
    async def get_by_id(cls, id: int, query_meta: Optional[QueryMeta] = None) -> Optional["User"]:
        """Get a user by ID."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.id == id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

    @mutation(name="create_user", description="Create a new user")
    async def create(cls, name: str, email: str) -> "User":
        """Create a new user (idempotent)."""
        from demo.database import async_session

        async with async_session() as session:
            # Idempotency check: return existing user if email already exists
            existing = await session.exec(select(cls).where(cls.email == email))
            if existing.first():
                return existing.first()

            user = cls(name=name, email=email)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user


class Post(BaseEntity, table=True):
    """Post entity."""

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    content: str
    author_id: int = Field(foreign_key="user.id")

    # Relationship: Post belongs to User
    author: Optional["User"] = Relationship(back_populates="posts")

    # Relationship: Post has many comments
    comments: list["Comment"] = Relationship(back_populates="post")

    @query(name="posts", description="Get all posts with optional limit")
    async def get_all(
        cls, limit: int = 10, query_meta: Optional[QueryMeta] = None
    ) -> list["Post"]:
        """Get all posts with optional limit."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @query(name="post", description="Get a post by ID")
    async def get_by_id(cls, id: int, query_meta: Optional[QueryMeta] = None) -> Optional["Post"]:
        """Get a post by ID."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.id == id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

    @query(name="posts_by_author", description="Get posts by author ID")
    async def get_by_author(
        cls, author_id: int, limit: int = 10, query_meta: Optional[QueryMeta] = None
    ) -> list["Post"]:
        """Get posts by author ID."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.author_id == author_id).limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @mutation(name="create_post", description="Create a new post")
    async def create(cls, title: str, content: str, author_id: int) -> "Post":
        """Create a new post (idempotent)."""
        from demo.database import async_session

        async with async_session() as session:
            # Idempotency check: return existing post if same title + author
            existing = await session.exec(
                select(cls).where(cls.title == title, cls.author_id == author_id)
            )
            if existing.first():
                return existing.first()

            post = cls(title=title, content=content, author_id=author_id)
            session.add(post)
            await session.commit()
            await session.refresh(post)
            return post


class Comment(BaseEntity, table=True):
    """Comment entity."""

    id: Optional[int] = Field(default=None, primary_key=True)
    content: str
    post_id: int = Field(foreign_key="post.id")
    author_id: int = Field(foreign_key="user.id")

    # Relationship: Comment belongs to Post
    post: Optional["Post"] = Relationship(back_populates="comments")

    # Relationship: Comment belongs to User
    author: Optional["User"] = Relationship(back_populates="comments")

    @query(name="comments", description="Get all comments with optional limit")
    async def get_all(
        cls, limit: int = 10, query_meta: Optional[QueryMeta] = None
    ) -> list["Comment"]:
        """Get all comments with optional limit."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @query(name="comment", description="Get a comment by ID")
    async def get_by_id(cls, id: int, query_meta: Optional[QueryMeta] = None) -> Optional["Comment"]:
        """Get a comment by ID."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.id == id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

    @query(name="comments_by_post", description="Get comments by post ID")
    async def get_by_post(
        cls, post_id: int, limit: int = 10, query_meta: Optional[QueryMeta] = None
    ) -> list["Comment"]:
        """Get comments by post ID."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.post_id == post_id).limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @query(name="comments_by_author", description="Get comments by author ID")
    async def get_by_author(
        cls, author_id: int, limit: int = 10, query_meta: Optional[QueryMeta] = None
    ) -> list["Comment"]:
        """Get comments by author ID."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.author_id == author_id).limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @mutation(name="create_comment", description="Create a new comment")
    async def create(cls, content: str, post_id: int, author_id: int) -> "Comment":
        """Create a new comment (idempotent)."""
        from demo.database import async_session

        async with async_session() as session:
            # Idempotency check: return existing comment if same content + post + author
            existing = await session.exec(
                select(cls).where(
                    cls.content == content,
                    cls.post_id == post_id,
                    cls.author_id == author_id,
                )
            )
            if existing.first():
                return existing.first()

            comment = cls(content=content, post_id=post_id, author_id=author_id)
            session.add(comment)
            await session.commit()
            await session.refresh(comment)
            return comment
