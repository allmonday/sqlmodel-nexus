"""Test the standard query (by_id, by_filter) generation functionality."""

from __future__ import annotations

from sqlmodel import Field, SQLModel

from sqlmodel_graphql import AutoQueryConfig, GraphQLHandler, add_standard_queries


def test_standard_queries_functionality():
    """Test that standard queries can be added and generate correct SDL."""
    # Create test entities
    class TestBase(SQLModel):
        id: int | None = Field(default=None, primary_key=True)

    class TestUser(TestBase, table=False):
        name: str
        email: str
        age: int | None = None

    # Mock session factory
    async def async_session_factory():
        mock_session = type("", (), {})()
        mock_session.exec = lambda _: type("", (), {"first": lambda: None})()
        mock_session.__aenter__ = lambda self: self
        mock_session.__aexit__ = lambda *args: None
        return mock_session

    # Add standard queries
    config = AutoQueryConfig(session_factory=async_session_factory)
    add_standard_queries([TestUser], config)

    # Verify methods exist
    assert hasattr(TestUser, "by_id")
    assert hasattr(TestUser, "by_filter")
    assert hasattr(TestUser, "_filter_input_type")

    # Generate SDL
    handler = GraphQLHandler(base=TestBase)
    sdl = handler.get_sdl()

    # Verify SDL contains expected content
    assert "testUserById" in sdl
    assert "testUserByFilter" in sdl
    assert "input TestUserFilterInput" in sdl
    assert "name: String" in sdl
    assert "email: String" in sdl
    assert "age: Int" in sdl


def test_disable_standard_queries():
    """Test that standard queries can be disabled."""
    # Create test entities
    class TestBase2(SQLModel):
        id: int | None = Field(default=None, primary_key=True)

    class TestUser2(TestBase2, table=False):
        name: str
        email: str

    # Mock session factory
    async def async_session_factory():
        mock_session = type("", (), {})()
        mock_session.exec = lambda _: type("", (), {"first": lambda: None})()
        mock_session.__aenter__ = lambda self: self
        mock_session.__aexit__ = lambda *args: None
        return mock_session

    # Add standard queries with disabled
    config = AutoQueryConfig(
        session_factory=async_session_factory,
        enabled=False,
    )
    add_standard_queries([TestUser2], config)

    # Verify methods not added
    assert not hasattr(TestUser2, "by_id")
    assert not hasattr(TestUser2, "by_filter")


def test_only_generate_by_filter():
    """Test that we can generate only by_filter."""
    # Create test entities
    class TestBase3(SQLModel):
        id: int | None = Field(default=None, primary_key=True)

    class TestUser3(TestBase3, table=False):
        name: str
        email: str

    # Mock session factory
    async def async_session_factory():
        mock_session = type("", (), {})()
        mock_session.exec = lambda _: type("", (), {"first": lambda: None})()
        mock_session.__aenter__ = lambda self: self
        mock_session.__aexit__ = lambda *args: None
        return mock_session

    # Add standard queries with only by_filter
    config = AutoQueryConfig(
        session_factory=async_session_factory,
        generate_by_id=False,
    )
    add_standard_queries([TestUser3], config)

    # Verify methods
    assert not hasattr(TestUser3, "by_id")
    assert hasattr(TestUser3, "by_filter")


def test_dont_override_existing_methods():
    """Test that existing methods are not overridden."""
    # Create test entities
    class TestBase4(SQLModel):
        id: int | None = Field(default=None, primary_key=True)

    class TestUser4(TestBase4, table=False):
        name: str
        email: str

        @staticmethod
        def by_id():
            return "existing method"

        @staticmethod
        def by_filter():
            return "existing filter"

    # Mock session factory
    async def async_session_factory():
        mock_session = type("", (), {})()
        mock_session.exec = lambda _: type("", (), {"first": lambda: None})()
        mock_session.__aenter__ = lambda self: self
        mock_session.__aexit__ = lambda *args: None
        return mock_session

    # Add standard queries
    config = AutoQueryConfig(session_factory=async_session_factory)
    add_standard_queries([TestUser4], config)

    # Verify existing methods are preserved
    assert TestUser4.by_id() == "existing method"
    assert TestUser4.by_filter() == "existing filter"
