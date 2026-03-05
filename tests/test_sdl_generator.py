"""Tests for SDL generator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import pytest
from sqlmodel import Field, SQLModel

from sqlmodel_graphql import SDLGenerator, mutation, query, QueryMeta

if TYPE_CHECKING:
    pass


# Define entities at module level to avoid metadata conflicts
class UserForTest(SQLModel):
    """Test User entity without table mapping."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str

    @query(name="users")
    async def get_all(cls, limit: int = 10, query_meta: Optional[QueryMeta] = None) -> list[UserForTest]:  # type: ignore[misc]
        """Get all users with optional query optimization."""
        # In real usage, query_meta would be used with QueryBuilder
        # to optimize the database query
        return [
            UserForTest(id=1, name="Alice", email="alice@example.com"),
            UserForTest(id=2, name="Bob", email="bob@example.com"),
        ][:limit]

    @query(name="user")
    async def get_by_id(cls, id: int, query_meta: Optional[QueryMeta] = None) -> Optional[UserForTest]:
        """Get user by ID."""
        users = {
            1: UserForTest(id=1, name="Alice", email="alice@example.com"),
            2: UserForTest(id=2, name="Bob", email="bob@example.com"),
        }
        return users.get(id)

    @mutation(name="createUser")
    async def create(cls, name: str, email: str, query_meta: Optional[QueryMeta] = None) -> UserForTest:
        """Create a new user."""
        return UserForTest(id=3, name=name, email=email)


class PostForTest(SQLModel):
    """Test Post entity without table mapping."""

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    content: str = ""
    author_id: int


class TestSDLGenerator:
    """Test cases for SDLGenerator."""

    def test_generate_types(self) -> None:
        """Test that GraphQL types are generated correctly."""
        generator = SDLGenerator([UserForTest, PostForTest])
        sdl = generator.generate()

        assert "type UserForTest" in sdl
        assert "type PostForTest" in sdl
        assert "id: Int" in sdl
        assert "name: String!" in sdl
        assert "email: String!" in sdl

    def test_generate_query_type(self) -> None:
        """Test that Query type is generated correctly."""
        generator = SDLGenerator([UserForTest])
        sdl = generator.generate()

        assert "type Query" in sdl
        assert "users(limit: Int): [UserForTest!]!" in sdl
        assert "user(id: Int!): UserForTest" in sdl

    def test_generate_mutation_type(self) -> None:
        """Test that Mutation type is generated correctly."""
        generator = SDLGenerator([UserForTest])
        sdl = generator.generate()

        assert "type Mutation" in sdl
        assert "createUser(name: String!, email: String!): UserForTest!" in sdl

    def test_snake_case_preserved(self) -> None:
        """Test that snake_case field names are preserved (no conversion to camelCase)."""
        generator = SDLGenerator([PostForTest])
        sdl = generator.generate()

        # author_id should remain as snake_case
        assert "author_id: Int!" in sdl

    def test_query_meta_not_in_sdl(self) -> None:
        """Test that query_meta parameter is not included in SDL."""
        generator = SDLGenerator([UserForTest])
        sdl = generator.generate()

        # query_meta should not appear in the generated SDL
        assert "query_meta" not in sdl
        assert "QueryMeta" not in sdl

        # But other parameters should be there
        assert "limit: Int" in sdl
        assert "id: Int!" in sdl
        assert "name: String!" in sdl
        assert "email: String!" in sdl
