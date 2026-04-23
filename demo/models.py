"""SQLModel entity definitions for the demo application."""

from typing import Optional

from sqlmodel import Field, Relationship, SQLModel, select

from sqlmodel_graphql import mutation, query


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
    """User-Post favorite relationship (many-to-many link table)."""

    __tablename__ = "user_favorite_post"

    user_id: int = Field(foreign_key="user.id", primary_key=True)
    post_id: int = Field(foreign_key="post.id", primary_key=True)


class User(BaseEntity, table=True):
    """User entity."""

    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str

    # Relationship: User has many posts
    posts: list["Post"] = Relationship(
        back_populates="author",
        sa_relationship_kwargs={"order_by": "Post.id"},
    )

    # Relationship: User has many comments
    comments: list["Comment"] = Relationship(
        back_populates="author",
        sa_relationship_kwargs={"order_by": "Comment.id"},
    )

    # Relationship: User has many favorite posts (many-to-many, through link table)
    favorite_posts: list["Post"] = Relationship(
        back_populates="favorited_by_users",
        link_model=UserFavoritePost,
        sa_relationship_kwargs={"order_by": "Post.id"},
    )

    @query
    async def get_users(cls, limit: int = 10) -> list["User"]:
        """Get all users with optional limit."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).limit(limit)
            result = await session.exec(stmt)
            return list(result.all())

    @query
    async def get_user(cls, id: int) -> Optional["User"]:
        """Get a user by ID."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.id == id)
            result = await session.exec(stmt)
            return result.first()

    @mutation
    async def create_user(cls, name: str, email: str) -> "User":
        """Create a new user (idempotent)."""
        from demo.database import async_session

        async with async_session() as session:
            existing = await session.exec(select(cls).where(cls.email == email))
            if existing.first():
                stmt = select(cls).where(cls.id == existing.first().id)
                result = await session.exec(stmt)
                return result.first()

            user = cls(name=name, email=email)
            session.add(user)
            await session.commit()
            await session.refresh(user)

            stmt = select(cls).where(cls.id == user.id)
            result = await session.exec(stmt)
            return result.first()

    @mutation
    async def create_user_with_input(cls, input: CreateUserInput) -> "User":
        """Create a new user using Input type (idempotent)."""
        from demo.database import async_session

        async with async_session() as session:
            existing = await session.exec(select(cls).where(cls.email == input.email))
            if existing.first():
                stmt = select(cls).where(cls.id == existing.first().id)
                result = await session.exec(stmt)
                return result.first()

            user = cls(name=input.name, email=input.email)
            session.add(user)
            await session.commit()
            await session.refresh(user)

            stmt = select(cls).where(cls.id == user.id)
            result = await session.exec(stmt)
            return result.first()

    @mutation
    async def add_favorite(cls, user_id: int, post_id: int) -> "User":
        """Add a post to user's favorites (idempotent)."""
        from demo.database import async_session

        async with async_session() as session:
            user = await session.get(cls, user_id)
            if not user:
                raise ValueError("User not found")

            post = await session.get(Post, post_id)
            if not post:
                raise ValueError("Post not found")

            if post not in user.favorite_posts:
                user.favorite_posts.append(post)
                await session.commit()

            stmt = select(cls).where(cls.id == user_id)
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
    comments: list["Comment"] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={"order_by": "Comment.id"},
    )

    # Relationship: Post has many favoriting users (many-to-many, through link table)
    favorited_by_users: list["User"] = Relationship(
        back_populates="favorite_posts",
        link_model=UserFavoritePost,
        sa_relationship_kwargs={"order_by": "User.id"},
    )

    @query
    async def get_posts(cls, limit: int = 10) -> list["Post"]:
        """Get all posts with optional limit."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).limit(limit)
            result = await session.exec(stmt)
            return list(result.all())

    @query
    async def get_post(cls, id: int) -> Optional["Post"]:
        """Get a post by ID."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.id == id)
            result = await session.exec(stmt)
            return result.first()

    @query
    async def get_posts_by_author(
        cls, author_id: int, limit: int = 10
    ) -> list["Post"]:
        """Get posts by author ID."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.author_id == author_id).limit(limit)
            result = await session.exec(stmt)
            return list(result.all())

    @mutation
    async def create_post(cls, title: str, content: str, author_id: int) -> "Post":
        """Create a new post (idempotent)."""
        from demo.database import async_session

        async with async_session() as session:
            existing = await session.exec(
                select(cls).where(cls.title == title, cls.author_id == author_id)
            )
            if existing.first():
                stmt = select(cls).where(cls.id == existing.first().id)
                result = await session.exec(stmt)
                return result.first()

            post = cls(title=title, content=content, author_id=author_id)
            session.add(post)
            await session.commit()
            await session.refresh(post)

            stmt = select(cls).where(cls.id == post.id)
            result = await session.exec(stmt)
            return result.first()

    @mutation
    async def create_post_with_input(cls, input: CreatePostInput) -> "Post":
        """Create a new post using Input type (idempotent)."""
        from demo.database import async_session

        async with async_session() as session:
            existing = await session.exec(
                select(cls).where(cls.title == input.title, cls.author_id == input.author_id)
            )
            if existing.first():
                stmt = select(cls).where(cls.id == existing.first().id)
                result = await session.exec(stmt)
                return result.first()

            post = cls(title=input.title, content=input.content, author_id=input.author_id)
            session.add(post)
            await session.commit()
            await session.refresh(post)

            stmt = select(cls).where(cls.id == post.id)
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
    async def get_comments(cls, limit: int = 10) -> list["Comment"]:
        """Get all comments with optional limit."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).limit(limit)
            result = await session.exec(stmt)
            return list(result.all())

    @query
    async def get_comment(cls, id: int) -> Optional["Comment"]:
        """Get a comment by ID."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.id == id)
            result = await session.exec(stmt)
            return result.first()

    @query
    async def get_comments_by_post(
        cls, post_id: int, limit: int = 10
    ) -> list["Comment"]:
        """Get comments by post ID."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.post_id == post_id).limit(limit)
            result = await session.exec(stmt)
            return list(result.all())

    @query
    async def get_comments_by_author(
        cls, author_id: int, limit: int = 10
    ) -> list["Comment"]:
        """Get comments by author ID."""
        from demo.database import async_session

        async with async_session() as session:
            stmt = select(cls).where(cls.author_id == author_id).limit(limit)
            result = await session.exec(stmt)
            return list(result.all())

    @mutation
    async def create_comment(
        cls, content: str, post_id: int, author_id: int
    ) -> "Comment":
        """Create a new comment (idempotent)."""
        from demo.database import async_session

        async with async_session() as session:
            existing = await session.exec(
                select(cls).where(
                    cls.content == content,
                    cls.post_id == post_id,
                    cls.author_id == author_id,
                )
            )
            if existing.first():
                stmt = select(cls).where(cls.id == existing.first().id)
                result = await session.exec(stmt)
                return result.first()

            comment = cls(content=content, post_id=post_id, author_id=author_id)
            session.add(comment)
            await session.commit()
            await session.refresh(comment)

            stmt = select(cls).where(cls.id == comment.id)
            result = await session.exec(stmt)
            return result.first()
