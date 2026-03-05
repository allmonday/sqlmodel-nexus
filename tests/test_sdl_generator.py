"""Tests for SDL generator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import pytest
from sqlmodel import Field, SQLModel

from sqlmodel_graphql import SDLGenerator, mutation, query

if TYPE_CHECKING:
    pass


# Define entities at module level to avoid metadata conflicts
class UserForTest(SQLModel):
    """Test User entity without table mapping."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str

    @query(name="users")
    async def get_all(cls, limit: int = 10) -> list[UserForTest]:  # type: ignore[misc]
        return []

    @query(name="user")
    async def get_by_id(cls, id: int) -> Optional[UserForTest]:
        return None

    @mutation(name="createUser")
    async def create(cls, name: str, email: str) -> UserForTest:
        return UserForTest(name=name, email=email)


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

    def test_camel_case_conversion(self) -> None:
        """Test that snake_case is converted to camelCase."""
        generator = SDLGenerator([PostForTest])
        sdl = generator.generate()

        # author_id should become authorId
        assert "authorId: Int!" in sdl
