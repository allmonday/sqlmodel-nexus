"""Tests for decorator module — @query and @mutation decorators."""

from __future__ import annotations

from sqlmodel import SQLModel

from sqlmodel_graphql.decorator import mutation, query


class TestQueryDecorator:
    def test_query_marks_method(self):
        """@query should set _graphql_query = True on the function."""

        class User(SQLModel, table=False):
            @query
            async def get_all(cls):
                pass

        assert User.get_all._graphql_query is True

    def test_query_returns_classmethod(self):
        """@query should convert the method to a classmethod."""

        class User(SQLModel, table=False):
            @query
            async def get_all(cls):
                pass

        assert isinstance(User.__dict__["get_all"], classmethod)

    def test_query_preserves_function_name(self):
        """@query should preserve the original function name."""

        class User(SQLModel, table=False):
            @query
            async def get_by_id(cls, id: int):
                pass

        assert User.get_by_id.__func__.__name__ == "get_by_id"

    def test_query_docstring_preserved(self):
        """@query should preserve docstring."""

        class User(SQLModel, table=False):
            @query
            async def get_all(cls):
                """Get all users."""
                pass

        assert User.get_all.__func__.__doc__ == "Get all users."


class TestMutationDecorator:
    def test_mutation_marks_method(self):
        """@mutation should set _graphql_mutation = True on the function."""

        class User(SQLModel, table=False):
            @mutation
            async def create(cls):
                pass

        assert User.create._graphql_mutation is True

    def test_mutation_returns_classmethod(self):
        """@mutation should convert the method to a classmethod."""

        class User(SQLModel, table=False):
            @mutation
            async def create(cls):
                pass

        assert isinstance(User.__dict__["create"], classmethod)

    def test_mutation_preserves_function_name(self):
        """@mutation should preserve the original function name."""

        class User(SQLModel, table=False):
            @mutation
            async def delete(cls, id: int):
                pass

        assert User.delete.__func__.__name__ == "delete"

    def test_mutation_docstring_preserved(self):
        """@mutation should preserve docstring."""

        class User(SQLModel, table=False):
            @mutation
            async def create(cls):
                """Create a user."""
                pass

        assert User.create.__func__.__doc__ == "Create a user."

    def test_query_and_mutation_coexist(self):
        """@query and @mutation on different methods should not interfere."""

        class User(SQLModel, table=False):
            @query
            async def get_all(cls):
                """Get users."""
                pass

            @mutation
            async def create(cls):
                """Create user."""
                pass

        assert User.get_all._graphql_query is True
        assert not hasattr(User.get_all, "_graphql_mutation")
        assert User.create._graphql_mutation is True
        assert not hasattr(User.create, "_graphql_query")
