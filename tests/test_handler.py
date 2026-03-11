"""Tests for GraphQLHandler."""

from __future__ import annotations

import pytest
from sqlmodel import Field, Relationship, SQLModel

from sqlmodel_graphql import GraphQLHandler, QueryMeta, mutation, query


# Define test base class
class HandlerTestBase(SQLModel):
    """Base class for test entities."""

    pass


class HandlerTestUser(HandlerTestBase, table=False):
    """Test user entity."""

    id: int = Field(primary_key=True)
    name: str
    email: str

    @query(name="test_users")
    async def get_all(
        cls, limit: int = 10, query_meta: QueryMeta | None = None
    ) -> list[HandlerTestUser]:
        """Get all test users."""
        return [
            HandlerTestUser(id=1, name="Alice", email="alice@example.com"),
            HandlerTestUser(id=2, name="Bob", email="bob@example.com"),
        ][:limit]

    @query(name="test_user")
    async def get_by_id(
        cls, id: int, query_meta: QueryMeta | None = None
    ) -> HandlerTestUser | None:
        """Get test user by ID."""
        return HandlerTestUser(id=id, name="Test", email="test@example.com")


class HandlerTestPost(HandlerTestBase, table=False):
    """Test post entity."""

    id: int = Field(primary_key=True)
    title: str
    content: str = ""

    @query(name="test_posts")
    async def get_all(cls, query_meta: QueryMeta | None = None) -> list[HandlerTestPost]:
        """Get all test posts."""
        return []

    @mutation(name="create_test_post")
    async def create(cls, title: str, content: str, query_meta: QueryMeta) -> HandlerTestPost:
        """Create a test post."""
        return HandlerTestPost(id=1, title=title, content=content)


class HandlerTestNoDecorators(HandlerTestBase, table=False):
    """Entity without @query or @mutation decorators - should be ignored."""

    id: int = Field(primary_key=True)
    name: str


class TestDiscoverFromBase:
    """Tests for _discover_from_base method."""

    def test_discovers_entities_with_query(self) -> None:
        """Test that entities with @query are discovered."""
        handler = GraphQLHandler(base=HandlerTestBase)

        entity_names = [e.__name__ for e in handler.entities]
        assert "HandlerTestUser" in entity_names
        assert "HandlerTestPost" in entity_names

    def test_discovers_entities_with_mutation(self) -> None:
        """Test that entities with @mutation are discovered."""
        handler = GraphQLHandler(base=HandlerTestBase)

        entity_names = [e.__name__ for e in handler.entities]
        assert "HandlerTestPost" in entity_names  # Has @mutation

    def test_ignores_entities_without_decorators(self) -> None:
        """Test that entities without @query/@mutation are ignored."""
        handler = GraphQLHandler(base=HandlerTestBase)

        entity_names = [e.__name__ for e in handler.entities]
        assert "HandlerTestNoDecorators" not in entity_names


class TestGraphQLHandlerWithBase:
    """Tests for GraphQLHandler with base parameter."""

    @pytest.fixture
    def handler(self) -> GraphQLHandler:
        """Create handler with base parameter."""
        return GraphQLHandler(base=HandlerTestBase)

    def test_handler_creates_sdl_generator(self, handler: GraphQLHandler) -> None:
        """Test that handler creates SDL generator with discovered entities."""
        sdl = handler.get_sdl()

        assert "type HandlerTestUser" in sdl
        assert "type HandlerTestPost" in sdl

    def test_handler_discovers_query_methods(self, handler: GraphQLHandler) -> None:
        """Test that handler discovers query methods."""
        assert "test_users" in handler._query_methods
        assert "test_user" in handler._query_methods
        assert "test_posts" in handler._query_methods

    def test_handler_discovers_mutation_methods(self, handler: GraphQLHandler) -> None:
        """Test that handler discovers mutation methods."""
        assert "create_test_post" in handler._mutation_methods

    @pytest.mark.asyncio
    async def test_execute_query(self, handler: GraphQLHandler) -> None:
        """Test executing a query."""
        result = await handler.execute("{ test_users { id name } }")

        assert "data" in result
        assert "test_users" in result["data"]
        assert len(result["data"]["test_users"]) == 2
        assert result["data"]["test_users"][0]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_execute_mutation(self, handler: GraphQLHandler) -> None:
        """Test executing a mutation."""
        result = await handler.execute(
            'mutation { create_test_post(title: "Hello", content: "World") { id title } }'
        )

        assert "data" in result
        assert "create_test_post" in result["data"]
        assert result["data"]["create_test_post"]["title"] == "Hello"

    @pytest.mark.asyncio
    async def test_introspection_query(self, handler: GraphQLHandler) -> None:
        """Test introspection query."""
        result = await handler.execute("{ __schema { queryType { name } } }")

        assert "data" in result
        assert result["data"]["__schema"]["queryType"]["name"] == "Query"


# ============================================================================
# Tests for Relationship-based entity discovery
# ============================================================================


class HandlerTestAuthor(HandlerTestBase, table=False):
    """Author with @query - root entity."""

    id: int = Field(primary_key=True)
    name: str
    books: list[HandlerTestBook] = Relationship(back_populates="author")

    @query(name="test_authors")
    async def get_all(cls) -> list[HandlerTestAuthor]:
        """Get all test authors."""
        return []


class HandlerTestBook(HandlerTestBase, table=False):
    """Book WITHOUT @query/@mutation - discovered via Relationship."""

    id: int = Field(primary_key=True)
    title: str
    author_id: int = Field(foreign_key="handler_test_author.id")
    author: HandlerTestAuthor | None = Relationship(back_populates="books")


class HandlerTestIsolated(HandlerTestBase, table=False):
    """Isolated entity - no decorators AND no relationships - should NOT be discovered."""

    id: int = Field(primary_key=True)
    data: str


class TestDiscoverFromBaseWithRelationships:
    """Tests for _discover_from_base with Relationship traversal."""

    def test_discovers_root_entities_with_decorators(self) -> None:
        """Test that root entities with @query are discovered."""
        handler = GraphQLHandler(base=HandlerTestBase)

        entity_names = [e.__name__ for e in handler.entities]
        # Root entity: has @query
        assert "HandlerTestAuthor" in entity_names

    def test_discovers_related_entities_without_decorators(self) -> None:
        """Test that entities related via Relationship are discovered even without decorators."""
        handler = GraphQLHandler(base=HandlerTestBase)

        entity_names = [e.__name__ for e in handler.entities]
        # Related entity: no decorators but connected via Relationship
        assert "HandlerTestBook" in entity_names

    def test_ignores_isolated_entities_without_decorators(self) -> None:
        """Test that isolated entities without decorators are NOT discovered."""
        handler = GraphQLHandler(base=HandlerTestBase)

        entity_names = [e.__name__ for e in handler.entities]
        # Isolated entity: no decorators and no relationships
        assert "HandlerTestIsolated" not in entity_names

    def test_sdl_includes_related_entity_types(self) -> None:
        """Test that SDL generation includes related entity types."""
        handler = GraphQLHandler(base=HandlerTestBase)
        sdl = handler.get_sdl()

        # SDL should include the related entity type
        assert "type HandlerTestBook" in sdl
        assert "type HandlerTestAuthor" in sdl


# ============================================================================
# Tests for list[str] argument handling
# ============================================================================


class HandlerTestListArg(HandlerTestBase, table=False):
    """Test entity with list[str] argument."""

    id: int = Field(primary_key=True)
    tags: list[str] = Field(default_factory=list)

    @query(name="test_by_tags")
    async def get_by_tags(
        cls, tags: list[str], query_meta: QueryMeta | None = None
    ) -> list[HandlerTestListArg]:
        """Get items by tags list."""
        return [HandlerTestListArg(id=i, tags=tags) for i in range(len(tags))]


class TestListStrArgument:
    """Tests for list[str] argument handling with literal values."""

    @pytest.fixture
    def handler(self) -> GraphQLHandler:
        """Create handler with base parameter."""
        return GraphQLHandler(base=HandlerTestBase)

    @pytest.mark.asyncio
    async def test_list_str_argument_literal(self, handler: GraphQLHandler) -> None:
        """Test executing a query with list[str] argument as literal."""
        result = await handler.execute('{ test_by_tags(tags: ["tag1", "tag2"]) { id tags } }')

        assert "data" in result
        assert "test_by_tags" in result["data"]
        assert len(result["data"]["test_by_tags"]) == 2
        assert result["data"]["test_by_tags"][0]["tags"] == ["tag1", "tag2"]

    @pytest.mark.asyncio
    async def test_list_str_argument_empty(self, handler: GraphQLHandler) -> None:
        """Test executing a query with empty list[str] argument."""
        result = await handler.execute('{ test_by_tags(tags: []) { id tags } }')

        assert "data" in result
        assert "test_by_tags" in result["data"]
        assert len(result["data"]["test_by_tags"]) == 0
