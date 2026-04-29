"""Tests for QueryExecutor — GraphQL query execution with DataLoader resolution."""

from __future__ import annotations

import pytest
from sqlmodel import SQLModel, select

from sqlmodel_graphql.decorator import mutation, query
from sqlmodel_graphql.execution.query_executor import QueryExecutor
from sqlmodel_graphql.loader.registry import LoaderRegistry, RelationshipInfo
from sqlmodel_graphql.query_parser import FieldSelection, QueryParser
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

    async def test_paginated_serialization_only_returns_selected_fields(self):
        """Paginated relationship responses should not include unselected items."""
        executor = _make_executor(enable_pagination=True)

        class PageItem(SQLModel, table=False):
            id: int
            name: str

        rel_info = RelationshipInfo(
            name="posts",
            direction="ONETOMANY",
            fk_field="author_id",
            target_entity=PageItem,
            is_list=True,
            loader=object,
        )
        child_sel = QueryParser().parse("{ posts { pagination { total_count } } }")["posts"]

        result = executor._serialize_relationship_value(
            value={
                "items": [PageItem(id=1, name="A")],
                "pagination": {"total_count": 1, "has_more": False},
            },
            rel_info=rel_info,
            child_sel=child_sel,
        )

        assert "items" not in result
        assert result["pagination"] == {"total_count": 1}

    def test_extract_page_args_rejects_negative_values(self):
        """Negative pagination arguments should fail fast."""
        executor = _make_executor(enable_pagination=True)

        class Rel:
            default_page_size = 20
            max_page_size = 100

        with pytest.raises(ValueError, match="limit must be greater than or equal to 0"):
            executor._extract_page_args(
                FieldSelection(arguments={"limit": -1}),
                Rel(),
            )

        with pytest.raises(ValueError, match="offset must be greater than or equal to 0"):
            executor._extract_page_args(
                FieldSelection(arguments={"offset": -1}),
                Rel(),
            )


# ──────────────────────────────────────────────────────────
# Split loader by type — GraphQL e2e tests
# ──────────────────────────────────────────────────────────


def _make_split_executor(session_factory=None) -> QueryExecutor:
    """Build executor with split_loader_by_type=True."""
    if session_factory is None:
        session_factory = get_test_session_factory()
    registry = LoaderRegistry(
        entities=[FixtureUser, FixtureSprint, FixtureTask],
        session_factory=session_factory,
        split_loader_by_type=True,
    )
    return QueryExecutor(registry)


class TestQueryExecutorSplitMode:
    """GraphQL end-to-end tests for split_loader_by_type."""

    @pytest.mark.usefixtures("test_db")
    async def test_split_mode_returns_correct_results(self):
        """Split mode should execute a relationship query correctly."""
        executor = _make_split_executor()
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
            None, None, parsed, query_methods, {},
            [FixtureTask, FixtureUser, FixtureSprint],
        )

        tasks = result["data"]["tasks"]
        assert len(tasks) == 4
        for task in tasks:
            assert task["owner"] is not None
            assert "id" in task["owner"]
            assert "name" in task["owner"]

    @pytest.mark.usefixtures("test_db")
    async def test_split_mode_separate_loaders_for_different_selections(self):
        """Two root queries accessing the same relationship with different
        field selections should create separate loader instances in split mode,
        each with its own _query_meta."""
        executor = _make_split_executor()
        session_factory = get_test_session_factory()
        registry = executor._registry

        class TaskQuery(SQLModel, table=False):
            @query
            async def get_all(cls):
                async with session_factory() as session:
                    return list((await session.exec(select(FixtureTask))).all())

        method = _get_bound_method(TaskQuery, "get_all")
        query_methods = {
            "tasks": (FixtureTask, method),
            "otherTasks": (FixtureTask, method),
        }
        gql = "{ tasks { owner { id name } } otherTasks { owner { id email } } }"
        parsed = QueryParser().parse(gql)

        result = await executor.execute_query(
            gql, None, None, parsed, query_methods, {},
            [FixtureTask, FixtureUser, FixtureSprint],
        )

        # Verify results are correct for both root fields
        for task in result["data"]["tasks"]:
            assert task["owner"] is not None
            assert "name" in task["owner"]
        for task in result["data"]["otherTasks"]:
            assert task["owner"] is not None
            assert "email" in task["owner"]

        # Verify registry has 2 separate loader instances for owner M2O
        rel_info = registry.get_relationship(FixtureTask, "owner")
        loader_cls = rel_info.loader
        inner = registry._loader_instances[loader_cls]
        assert isinstance(inner, dict)  # split mode: nested dict
        assert len(inner) == 2

        type_keys = set(inner.keys())
        assert frozenset({"id", "name"}) in type_keys
        assert frozenset({"id", "email"}) in type_keys

        # Each loader has its own _query_meta matching its type_key
        for tk, loader in inner.items():
            meta_fields = set(loader._query_meta["fields"])
            assert meta_fields == tk

    @pytest.mark.usefixtures("test_db")
    async def test_split_mode_nested_relationships(self):
        """Split mode with nested relationships (sprint -> tasks -> owner)."""
        executor = _make_split_executor()
        session_factory = get_test_session_factory()

        class SprintQuery(SQLModel, table=False):
            @query
            async def get_all(cls):
                async with session_factory() as session:
                    return list((await session.exec(select(FixtureSprint))).all())

        method = _get_bound_method(SprintQuery, "get_all")
        query_methods = {"sprints": (FixtureSprint, method)}
        parsed = QueryParser().parse(
            "{ sprints { id name tasks { id title owner { id name } } } }"
        )

        result = await executor.execute_query(
            "{ sprints { id name tasks { id title owner { id name } } } }",
            None, None, parsed, query_methods, {},
            [FixtureTask, FixtureUser, FixtureSprint],
        )

        sprints = result["data"]["sprints"]
        assert len(sprints) == 2
        for sprint in sprints:
            assert "tasks" in sprint
            for task in sprint["tasks"]:
                assert task["owner"] is not None
                assert "name" in task["owner"]

    @pytest.mark.usefixtures("test_db")
    async def test_default_mode_single_loader_with_merged_fields(self):
        """Default mode uses a single shared loader instance whose _query_meta
        fields reflect the queried selection."""
        session_factory = get_test_session_factory()
        registry = LoaderRegistry(
            entities=[FixtureUser, FixtureSprint, FixtureTask],
            session_factory=session_factory,
            # split_loader_by_type=False (default)
        )
        executor = QueryExecutor(registry)

        class TaskQuery(SQLModel, table=False):
            @query
            async def get_all(cls):
                async with session_factory() as session:
                    return list((await session.exec(select(FixtureTask))).all())

        method = _get_bound_method(TaskQuery, "get_all")
        query_methods = {"tasks": (FixtureTask, method)}
        parsed = QueryParser().parse("{ tasks { owner { id name } } }")

        await executor.execute_query(
            "{ tasks { owner { id name } } }",
            None, None, parsed, query_methods, {},
            [FixtureTask, FixtureUser, FixtureSprint],
        )

        # Default mode: flat cache, single instance per loader_cls
        rel_info = registry.get_relationship(FixtureTask, "owner")
        loader_cls = rel_info.loader
        instance = registry._loader_instances[loader_cls]
        assert not isinstance(instance, dict)
        meta_fields = set(instance._query_meta["fields"])
        assert meta_fields == {"id", "name"}
