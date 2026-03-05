"""Integration tests for query_meta with SQLite database."""

from typing import TYPE_CHECKING, List, Optional

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import Field, Relationship, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sqlmodel_graphql import QueryParser
from sqlmodel_graphql.types import FieldSelection, QueryMeta, RelationshipSelection

if TYPE_CHECKING:
    pass


# Test entities with relationships
class User(SQLModel, table=True):
    """User entity for testing."""

    __test__ = False  # Tell pytest this is not a test class

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str
    posts: List["Post"] = Relationship(back_populates="author")


class Post(SQLModel, table=True):
    """Post entity for testing."""

    __test__ = False

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    content: str = ""
    author_id: int = Field(foreign_key="user.id")
    author: Optional[User] = Relationship(back_populates="posts")


@pytest_asyncio.fixture
async def engine():
    """Create async SQLite engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine):
    """Create async session."""
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def sample_data(session):
    """Create sample data for testing."""
    user1 = User(id=1, name="Alice", email="alice@example.com")
    user2 = User(id=2, name="Bob", email="bob@example.com")
    post1 = Post(id=1, title="Post 1", content="Content 1", author_id=1)
    post2 = Post(id=2, title="Post 2", content="Content 2", author_id=1)
    post3 = Post(id=3, title="Post 3", content="Content 3", author_id=2)

    session.add(user1)
    session.add(user2)
    session.add(post1)
    session.add(post2)
    session.add(post3)
    await session.commit()


class TestQueryParser:
    """Test QueryParser with entity field names."""

    def test_parse_simple_fields(self) -> None:
        """Test parsing simple field selection."""
        parser = QueryParser(entity_field_names={"id", "name", "email", "posts"})
        query = """
        query {
            users {
                id
                name
            }
        }
        """
        result = parser.parse(query)
        assert "users" in result
        assert result["users"].get_field_names() == ["id", "name"]

    def test_parse_with_relationships(self) -> None:
        """Test parsing with relationship selection."""
        parser = QueryParser(entity_field_names={"id", "name", "email", "posts"})
        query = """
        query {
            users {
                id
                name
                posts {
                    title
                }
            }
        }
        """
        result = parser.parse(query)
        assert "posts" in result["users"].relationships
        assert result["users"].relationships["posts"].get_field_names() == ["title"]


class TestQueryMetaIntegration:
    """Test QueryMeta.to_options() with real SQLite database."""

    @pytest.mark.asyncio
    async def test_to_options_field_selection(self, session, sample_data) -> None:
        """Test to_options with field selection only."""
        query_meta = QueryMeta(
            fields=[FieldSelection(name="name")],
            relationships={},
        )

        # Use to_options API
        stmt = select(User).options(*query_meta.to_options(User))
        result = await session.exec(stmt)
        users = result.all()

        assert len(users) == 2
        assert users[0].name in ["Alice", "Bob"]

    @pytest.mark.asyncio
    async def test_to_options_with_relationships(self, session, sample_data) -> None:
        """Test to_options with relationships."""
        query_meta = QueryMeta(
            fields=[FieldSelection(name="id"), FieldSelection(name="name")],
            relationships={
                "posts": RelationshipSelection(
                    name="posts",
                    fields=[FieldSelection(name="title")],
                    relationships={},
                )
            },
        )

        # Use to_options API
        stmt = select(User).options(*query_meta.to_options(User))
        result = await session.exec(stmt)
        users = result.all()

        assert len(users) == 2
        for user in users:
            if user.name == "Alice":
                assert len(user.posts) == 2
            elif user.name == "Bob":
                assert len(user.posts) == 1

    @pytest.mark.asyncio
    async def test_to_options_in_query_method(self, session, sample_data) -> None:
        """Test using to_options in a @query decorated method."""
        # Simulate usage within a @query decorated method
        async def get_users(
            session: AsyncSession,
            query_meta: Optional[QueryMeta] = None
        ) -> list[User]:
            stmt = select(User)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(User))
            result = await session.exec(stmt)
            return list(result.all())

        query_meta = QueryMeta(
            fields=[FieldSelection(name="name")],
            relationships={},
        )

        users = await get_users(session, query_meta)
        assert len(users) == 2

    @pytest.mark.asyncio
    async def test_full_flow_with_parser(self, session, sample_data) -> None:
        """Test full flow: parse GraphQL -> to_options -> execute."""
        # Parse GraphQL query
        parser = QueryParser(entity_field_names={"id", "name", "email", "posts"})
        graphql_query = """
        query {
            users {
                id
                name
                posts {
                    title
                }
            }
        }
        """
        query_meta_dict = parser.parse(graphql_query)
        query_meta = query_meta_dict["users"]

        # Build optimized query using to_options
        stmt = select(User).options(*query_meta.to_options(User))

        # Execute
        result = await session.exec(stmt)
        users = result.all()

        assert len(users) == 2
        # Verify the data structure matches what we queried
        for user in users:
            assert user.id is not None
            assert user.name is not None
            # email was NOT in the query, but should still be accessible
            # (SQLModel loads it, but in production this reduces DB load)
            for post in user.posts:
                assert post.title is not None
