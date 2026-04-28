"""Tests for QueryExecutor — GraphQL query execution with DataLoader resolution."""

from __future__ import annotations

import pytest
from sqlmodel import SQLModel, select

from sqlmodel_graphql.decorator import mutation, query
from sqlmodel_graphql.execution.query_executor import QueryExecutor
from sqlmodel_graphql.loader.registry import LoaderRegistry
from sqlmodel_graphql.query_parser import QueryParser
from tests.conftest import (
    FixtureSprint,
    FixtureTask,
    FixtureUser,
    get_test_session_factory,
)

# ──────────────────────────────────────────────────────────
# Helper: build executor + parse selections
# ──────────────────────────────────────────────────────────


def _make_executor(
    entities=None, session_factory=None, enable_pagination=False
) -> QueryExecutor:
    if entities is None:
        entities = [FixtureUser, FixtureSprint, FixtureTask]
    if session_factory is None:
        session_factory = get_test_session_factory()
    registry = LoaderRegistry(
        entities=entities,
        session_factory=session_factory,
        enable_pagination=enable_pagination,
    )
    return QueryExecutor(registry, enable_pagination=enable_pagination)


def _get_bound_method(entity_cls, method_name: str):
    """Get the bound classmethod from a @query/@mutation decorated method.

    getattr on a classmethod returns a bound method where cls is already
    bound, so the executor can call method(**args) without passing cls.
    """
    return getattr(entity_cls, method_name)


# ──────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────


class TestQueryExecutorBasic:
    @pytest.mark.usefixtures("test_db")
    async def test_execute_simple_query(self):
        """Basic query execution should return data in correct format."""
        executor = _make_executor()
        session_factory = get_test_session_factory()

        class UserQuery(SQLModel, table=False):
            @query
            async def get_all(cls):
                async with session_factory() as session:
                    return list((await session.exec(select(FixtureUser))).all())

        method = _get_bound_method(UserQuery, "get_all")
        query_methods = {"users": (FixtureUser, method)}
        parsed = QueryParser().parse("{ users { id name } }")

        result = await executor.execute_query(
            "{ users { id name } }",
            None,
            None,
            parsed,
            query_methods,
            {},
            [FixtureUser, FixtureSprint, FixtureTask],
        )

        assert "data" in result
        assert "users" in result["data"]
        assert len(result["data"]["users"]) == 2
        names = {u["name"] for u in result["data"]["users"]}
        assert "Alice" in names or "Bob" in names

    @pytest.mark.usefixtures("test_db")
    async def test_execute_mutation(self):
        """Mutation execution should work via mutation_methods."""
        executor = _make_executor()
        session_factory = get_test_session_factory()

        class UserMutation(SQLModel, table=False):
            @mutation
            async def create(cls, name: str):
                async with session_factory() as session:
                    user = FixtureUser(name=name, email=f"{name}@test.com")
                    session.add(user)
                    await session.commit()
                    await session.refresh(user)
                    return user

        method = _get_bound_method(UserMutation, "create")
        mutation_methods = {"createUser": (FixtureUser, method)}
        parsed = QueryParser().parse('mutation { createUser(name: "Eve") { id name } }')

        result = await executor.execute_query(
            'mutation { createUser(name: "Eve") { id name } }',
            None,
            None,
            parsed,
            {},
            mutation_methods,
            [FixtureUser, FixtureSprint, FixtureTask],
        )

        assert "data" in result
        assert result["data"]["createUser"]["name"] == "Eve"

    async def test_execute_returns_error_on_unknown_field(self):
        """Querying an unknown field should produce an error entry."""
        executor = _make_executor()

        result = await executor.execute_query(
            "{ nonexistent { id } }",
            None,
            None,
            {},
            {},
            {},
            [FixtureUser],
        )

        assert "errors" in result
        assert any("nonexistent" in e["message"] for e in result["errors"])

    async def test_execute_handles_exception_in_method(self):
        """Exception in query method should be captured in errors."""
        executor = _make_executor()

        class FailQuery(SQLModel, table=False):
            @query
            async def boom(cls):
                raise RuntimeError("kaboom")

        method = _get_bound_method(FailQuery, "boom")
        query_methods = {"fail": (FixtureUser, method)}
        parsed = QueryParser().parse("{ fail { id } }")

        result = await executor.execute_query(
            "{ fail { id } }",
            None,
            None,
            parsed,
            query_methods,
            {},
            [FixtureUser],
        )

        assert "errors" in result
        assert any("kaboom" in e["message"] for e in result["errors"])

    async def test_execute_query_with_no_data_returns_empty(self):
        """Query with no matching methods should return empty data."""
        executor = _make_executor()

        result = await executor.execute_query(
            "{ users { id } }",
            None,
            None,
            {},
            {},
            {},
            [FixtureUser],
        )

        assert result.get("data") is None or result == {}

    @pytest.mark.usefixtures("test_db")
    async def test_execute_clears_cache_per_request(self):
        """Each execute_query call should clear DataLoader cache."""
        executor = _make_executor()
        session_factory = get_test_session_factory()
        call_count = 0

        class TaskQuery(SQLModel, table=False):
            @query
            async def get_all(cls):
                nonlocal call_count
                call_count += 1
                async with session_factory() as session:
                    return list((await session.exec(select(FixtureTask))).all())

        method = _get_bound_method(TaskQuery, "get_all")
        query_methods = {"tasks": (FixtureTask, method)}
        parsed = QueryParser().parse("{ tasks { id title } }")

        await executor.execute_query(
            "{ tasks { id title } }", None, None, parsed, query_methods, {}, [FixtureTask, FixtureUser, FixtureSprint]
        )
        await executor.execute_query(
            "{ tasks { id title } }", None, None, parsed, query_methods, {}, [FixtureTask, FixtureUser, FixtureSprint]
        )

        assert call_count == 2


class TestQueryExecutorSerialization:
    async def test_serialize_none_result(self):
        """Query returning None should serialize to null."""
        executor = _make_executor()

        class NoneQuery(SQLModel, table=False):
            @query
            async def get_one(cls):
                return None

        method = _get_bound_method(NoneQuery, "get_one")
        query_methods = {"user": (FixtureUser, method)}
        parsed = QueryParser().parse("{ user { id } }")

        result = await executor.execute_query(
            "{ user { id } }", None, None, parsed, query_methods, {}, [FixtureUser]
        )

        assert result["data"]["user"] is None

    @pytest.mark.usefixtures("test_db")
    async def test_serialize_list_result(self):
        """Query returning a list should serialize to list of dicts."""
        executor = _make_executor()
        session_factory = get_test_session_factory()

        class UserQuery(SQLModel, table=False):
            @query
            async def get_all(cls):
                async with session_factory() as session:
                    return list((await session.exec(select(FixtureUser))).all())

        method = _get_bound_method(UserQuery, "get_all")
        query_methods = {"users": (FixtureUser, method)}
        parsed = QueryParser().parse("{ users { id name } }")

        result = await executor.execute_query(
            "{ users { id name } }", None, None, parsed, query_methods, {}, [FixtureUser, FixtureSprint, FixtureTask]
        )

        users = result["data"]["users"]
        assert isinstance(users, list)
        assert len(users) == 2
        assert all(isinstance(u, dict) for u in users)

    @pytest.mark.usefixtures("test_db")
    async def test_execute_with_relationships_resolved(self):
        """Query with nested relationship should resolve via DataLoader."""
        executor = _make_executor()
        session_factory = get_test_session_factory()

        class TaskQuery(SQLModel, table=False):
            @query
            async def get_all(cls):
                async with session_factory() as session:
                    return list((await session.exec(select(FixtureTask))).all())

        method = _get_bound_method(TaskQuery, "get_all")
        query_methods = {"tasks": (FixtureTask, method)}
        parsed = QueryParser().parse("{ tasks { id title owner { id name } } }")

        result = await executor.execute_query(
            "{ tasks { id title owner { id name } } }",
            None,
            None,
            parsed,
            query_methods,
            {},
            [FixtureTask, FixtureUser, FixtureSprint],
        )

        tasks = result["data"]["tasks"]
        assert len(tasks) == 4
        for task in tasks:
            assert "owner" in task
            assert task["owner"] is not None
            assert "name" in task["owner"]
