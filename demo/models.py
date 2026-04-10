"""SQLModel entity definitions for the demo application."""

from typing import Optional

from sqlmodel import Field, Relationship, SQLModel, select

from sqlmodel_graphql import QueryMeta, mutation, query


class BaseEntity(SQLModel):
    """Base class for all demo entities."""

    pass


# Input types for mutations
class CreateUserInput(SQLModel):
    """Input type for creating a new user."""

    name: str
    email: str


class CreatePostInput(SQLModel):
    """Input type for creating a new post."""

    title: str
    content: str
    author_id: int


class UserFavoritePost(BaseEntity, table=True):
    """User-Post favorite relationship (many-to-many link table).

    This is a link table connecting User and Post in a many-to-many relationship.
    Following SQLModel best practices, we only define the foreign keys here.
    """

    __tablename__ = "user_favorite_post"

    user_id: int = Field(foreign_key="user.id", primary_key=True)
    post_id: int = Field(foreign_key="post.id", primary_key=True)


class User(BaseEntity, table=True):
    """User entity."""

    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str

    # Relationship: User has many posts
    posts: list["Post"] = Relationship(back_populates="author")

    # Relationship: User has many comments
    comments: list["Comment"] = Relationship(back_populates="author")

    # Relationship: User has many favorite posts (many-to-many, through link table)
    favorite_posts: list["Post"] = Relationship(
        back_populates="favorited_by_users",
        link_model=UserFavoritePost
    )

    @query
    async def get_users(cls, limit: int = 10, query_meta: QueryMeta | None = None) -> list["User"]:
        """Get all users with optional limit."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @query
    async def get_user(cls, id: int, query_meta: QueryMeta | None = None) -> Optional["User"]:
        """Get a user by ID."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.id == id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

    @mutation
    async def create_user(
        cls, name: str, email: str, query_meta: QueryMeta | None = None
    ) -> "User":
        """Create a new user (idempotent)."""
        from demo.database import async_session

        async with async_session() as session:
            # Idempotency check: return existing user if email already exists
            existing = await session.exec(select(cls).where(cls.email == email))
            if existing.first():
                stmt = select(cls).where(cls.id == existing.first().id)
                if query_meta:
                    stmt = stmt.options(*query_meta.to_options(cls))
                result = await session.exec(stmt)
                return result.first()

            user = cls(name=name, email=email)
            session.add(user)
            await session.commit()
            await session.refresh(user)

            # Re-query with query_meta to load relationships
            stmt = select(cls).where(cls.id == user.id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

    @mutation
    async def create_user_with_input(
        cls, input: CreateUserInput, query_meta: QueryMeta | None = None
    ) -> "User":
        """Create a new user using Input type (idempotent)."""
        from demo.database import async_session

        async with async_session() as session:
            # Idempotency check: return existing user if email already exists
            existing = await session.exec(select(cls).where(cls.email == input.email))
            if existing.first():
                stmt = select(cls).where(cls.id == existing.first().id)
                if query_meta:
                    stmt = stmt.options(*query_meta.to_options(cls))
                result = await session.exec(stmt)
                return result.first()

            user = cls(name=input.name, email=input.email)
            session.add(user)
            await session.commit()
            await session.refresh(user)

            # Re-query with query_meta to load relationships
            stmt = select(cls).where(cls.id == user.id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

    @mutation
    async def add_favorite(
        cls, user_id: int, post_id: int, query_meta: QueryMeta | None = None
    ) -> "User":
        """Add a post to user's favorites (idempotent)."""
        from demo.database import async_session

        async with async_session() as session:
            # Get user
            user = await session.get(cls, user_id)
            if not user:
                raise ValueError("User not found")

            # Get post
            post = await session.get(Post, post_id)
            if not post:
                raise ValueError("Post not found")

            # Check if already favorited (idempotent)
            if post not in user.favorite_posts:
                user.favorite_posts.append(post)
                await session.commit()

            # Return user with relationships loaded
            stmt = select(cls).where(cls.id == user_id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

    @mutation
    async def remove_favorite(cls, user_id: int, post_id: int) -> bool:
        """Remove a post from user's favorites."""
        from demo.database import async_session

        async with async_session() as session:
            user = await session.get(cls, user_id)
            if not user:
                return False

            post = await session.get(Post, post_id)
            if not post:
                return False

            if post in user.favorite_posts:
                user.favorite_posts.remove(post)
                await session.commit()
                return True
            return False


class Post(BaseEntity, table=True):
    """Post entity."""

    id: int | None = Field(default=None, primary_key=True)
    title: str
    content: str
    author_id: int = Field(foreign_key="user.id")

    # Relationship: Post belongs to User
    author: Optional["User"] = Relationship(back_populates="posts")

    # Relationship: Post has many comments
    comments: list["Comment"] = Relationship(back_populates="post")

    # Relationship: Post has many favoriting users (many-to-many, through link table)
    favorited_by_users: list["User"] = Relationship(
        back_populates="favorite_posts",
        link_model=UserFavoritePost
    )

    @query
    async def get_posts(cls, limit: int = 10, query_meta: QueryMeta | None = None) -> list["Post"]:
        """Get all posts with optional limit."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @query
    async def get_post(cls, id: int, query_meta: QueryMeta | None = None) -> Optional["Post"]:
        """Get a post by ID."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.id == id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

    @query
    async def get_posts_by_author(
        cls, author_id: int, limit: int = 10, query_meta: QueryMeta | None = None
    ) -> list["Post"]:
        """Get posts by author ID."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.author_id == author_id).limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @mutation
    async def create_post(
        cls, title: str, content: str, author_id: int, query_meta: QueryMeta | None = None
    ) -> "Post":
        """Create a new post (idempotent)."""
        from demo.database import async_session

        async with async_session() as session:
            # Idempotency check: return existing post if same title + author
            existing = await session.exec(
                select(cls).where(cls.title == title, cls.author_id == author_id)
            )
            if existing.first():
                stmt = select(cls).where(cls.id == existing.first().id)
                if query_meta:
                    stmt = stmt.options(*query_meta.to_options(cls))
                result = await session.exec(stmt)
                return result.first()

            post = cls(title=title, content=content, author_id=author_id)
            session.add(post)
            await session.commit()
            await session.refresh(post)

            # Re-query with query_meta to load relationships
            stmt = select(cls).where(cls.id == post.id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

    @mutation
    async def create_post_with_input(
        cls, input: CreatePostInput, query_meta: QueryMeta | None = None
    ) -> "Post":
        """Create a new post using Input type (idempotent)."""
        from demo.database import async_session

        async with async_session() as session:
            # Idempotency check: return existing post if same title + author
            existing = await session.exec(
                select(cls).where(cls.title == input.title, cls.author_id == input.author_id)
            )
            if existing.first():
                stmt = select(cls).where(cls.id == existing.first().id)
                if query_meta:
                    stmt = stmt.options(*query_meta.to_options(cls))
                result = await session.exec(stmt)
                return result.first()

            post = cls(title=input.title, content=input.content, author_id=input.author_id)
            session.add(post)
            await session.commit()
            await session.refresh(post)

            # Re-query with query_meta to load relationships
            stmt = select(cls).where(cls.id == post.id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()


class Comment(BaseEntity, table=True):
    """Comment entity."""

    id: int | None = Field(default=None, primary_key=True)
    content: str
    post_id: int = Field(foreign_key="post.id")
    author_id: int = Field(foreign_key="user.id")

    # Relationship: Comment belongs to Post
    post: Optional["Post"] = Relationship(back_populates="comments")

    # Relationship: Comment belongs to User
    author: Optional["User"] = Relationship(back_populates="comments")

    @query
    async def get_comments(
        cls, limit: int = 10, query_meta: QueryMeta | None = None
    ) -> list["Comment"]:
        """Get all comments with optional limit."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @query
    async def get_comment(cls, id: int, query_meta: QueryMeta | None = None) -> Optional["Comment"]:
        """Get a comment by ID."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.id == id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

    @query
    async def get_comments_by_post(
        cls, post_id: int, limit: int = 10, query_meta: QueryMeta | None = None
    ) -> list["Comment"]:
        """Get comments by post ID."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.post_id == post_id).limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @query
    async def get_comments_by_author(
        cls, author_id: int, limit: int = 10, query_meta: QueryMeta | None = None
    ) -> list["Comment"]:
        """Get comments by author ID."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.author_id == author_id).limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @mutation
    async def create_comment(
        cls, content: str, post_id: int, author_id: int, query_meta: QueryMeta | None = None
    ) -> "Comment":
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
                stmt = select(cls).where(cls.id == existing.first().id)
                if query_meta:
                    stmt = stmt.options(*query_meta.to_options(cls))
                result = await session.exec(stmt)
                return result.first()

            comment = cls(content=content, post_id=post_id, author_id=author_id)
            session.add(comment)
            await session.commit()
            await session.refresh(comment)

            # Re-query with query_meta to load relationships
            stmt = select(cls).where(cls.id == comment.id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()
