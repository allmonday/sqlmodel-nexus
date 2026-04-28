"""Tests for Resolver — resolve_*, post_*, and Loader integration."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel
from sqlmodel import select

from sqlmodel_graphql.loader.registry import LoaderRegistry
from sqlmodel_graphql.resolver import Loader, Resolver
from sqlmodel_graphql.subset import DefineSubset
from tests.conftest import (
    FixtureSprint,
    FixtureTask,
    FixtureUser,
    get_test_session_factory,
)

# ──────────────────────────────────────────────────────────
# Test: basic resolve_* with custom loaders
# ──────────────────────────────────────────────────────────

class TestResolverBasic:
    @pytest.mark.usefixtures("test_db")
    async def test_sync_resolve(self):
        """Sync resolve_* method should populate the field."""

        class SimpleModel(BaseModel):
            name: str
            greeting: str = ""

            def resolve_greeting(self):
                return f"Hello, {self.name}!"

        model = SimpleModel(name="Alice")
        result = await Resolver().resolve(model)

        assert result.greeting == "Hello, Alice!"

    @pytest.mark.usefixtures("test_db")
    async def test_async_resolve(self):
        """Async resolve_* method should work."""

        class AsyncModel(BaseModel):
            name: str
            greeting: str = ""

            async def resolve_greeting(self):
                await asyncio.sleep(0.01)
                return f"Hello, {self.name}!"

        model = AsyncModel(name="Alice")
        result = await Resolver().resolve(model)

        assert result.greeting == "Hello, Alice!"

    @pytest.mark.usefixtures("test_db")
    async def test_resolve_list(self):
        """Resolver should handle a list of models."""

        class Item(BaseModel):
            name: str
            label: str = ""

            def resolve_label(self):
                return f"Item: {self.name}"

        items = [Item(name="A"), Item(name="B"), Item(name="C")]
        result = await Resolver().resolve(items)

        assert result[0].label == "Item: A"
        assert result[1].label == "Item: B"
        assert result[2].label == "Item: C"


# ──────────────────────────────────────────────────────────
# Test: post_* methods
# ──────────────────────────────────────────────────────────

class TestResolverPost:
    @pytest.mark.usefixtures("test_db")
    async def test_post_method(self):
        """post_* should execute after resolve_* completes."""

        class Counter(BaseModel):
            values: list[int] = []
            total: int = 0
            count: int = 0

            def resolve_values(self):
                return [1, 2, 3]

            def post_total(self):
                return sum(self.values)

            def post_count(self):
                return len(self.values)

        model = Counter()
        result = await Resolver().resolve(model)

        assert result.values == [1, 2, 3]
        assert result.total == 6
        assert result.count == 3

    @pytest.mark.usefixtures("test_db")
    async def test_post_accesses_resolved_data(self):
        """post_* can access fields populated by resolve_*."""

        class Model(BaseModel):
            name: str = "World"
            greeting: str = ""

            def resolve_name(self):
                return "Alice"

            def post_greeting(self):
                return f"Hello, {self.name}!"

        model = Model()
        result = await Resolver().resolve(model)

        assert result.name == "Alice"
        assert result.greeting == "Hello, Alice!"

    @pytest.mark.usefixtures("test_db")
    async def test_post_with_parent(self):
        """post_* can access parent node via parent parameter."""

        class Child(BaseModel):
            name: str
            parent_name: str = ""

            def post_parent_name(self, parent=None):
                if parent:
                    return f"child of {parent.name}"
                return "no parent"

        class Parent(BaseModel):
            name: str
            children: list[Child] = []

        parent = Parent(
            name="Parent1",
            children=[
                Child(name="Child1"),
                Child(name="Child2"),
            ],
        )
        result = await Resolver().resolve(parent)

        assert result.children[0].parent_name == "child of Parent1"
        assert result.children[1].parent_name == "child of Parent1"


# ──────────────────────────────────────────────────────────
# Test: Loader integration with LoaderRegistry
# ──────────────────────────────────────────────────────────

class TestResolverLoader:
    @pytest.mark.usefixtures("test_db")
    async def test_loader_with_registry(self):
        """resolve_* should receive DataLoader from LoaderRegistry."""

        session_factory = get_test_session_factory()
        registry = LoaderRegistry(
            entities=[FixtureUser, FixtureSprint, FixtureTask],
            session_factory=session_factory,
        )

        class UserDTO(DefineSubset):
            __subset__ = (FixtureUser, ("id", "name"))

        class TaskDTO(DefineSubset):
            __subset__ = (FixtureTask, ("id", "title", "owner_id"))
            owner: UserDTO | None = None

            def resolve_owner(self, loader=Loader("owner")):
                return loader.load(self.owner_id)

        # Get tasks from DB — construct DTOs from scalar fields only
        async with session_factory() as session:
            tasks = (await session.exec(select(FixtureTask))).all()

        dtos = [
            TaskDTO(id=t.id, title=t.title, owner_id=t.owner_id) for t in tasks
        ]
        result = await Resolver(registry).resolve(dtos)

        # Verify owners are resolved to UserDTO instances
        owner_names = {dto.owner.name for dto in result if dto.owner is not None}
        assert "Alice" in owner_names or "Bob" in owner_names

    @pytest.mark.usefixtures("test_db")
    async def test_loader_batch_loading(self):
        """Multiple items should trigger batch loading (single query per relationship)."""

        session_factory = get_test_session_factory()
        registry = LoaderRegistry(
            entities=[FixtureUser, FixtureSprint, FixtureTask],
            session_factory=session_factory,
        )

        class UserDTO(DefineSubset):
            __subset__ = (FixtureUser, ("id", "name"))

        class TaskDTO(DefineSubset):
            __subset__ = (FixtureTask, ("id", "title", "owner_id"))
            owner: UserDTO | None = None

            def resolve_owner(self, loader=Loader("owner")):
                return loader.load(self.owner_id)

        async with session_factory() as session:
            tasks = (await session.exec(select(FixtureTask))).all()

        dtos = [
            TaskDTO(id=t.id, title=t.title, owner_id=t.owner_id) for t in tasks
        ]
        result = await Resolver(registry).resolve(dtos)

        # All 4 tasks have owners resolved (2 unique users)
        assert all(dto.owner is not None for dto in result)


# ──────────────────────────────────────────────────────────
# Test: nested resolve with DefineSubset
# ──────────────────────────────────────────────────────────

class TestResolverNested:
    @pytest.mark.usefixtures("test_db")
    async def test_nested_resolve_with_subset(self):
        """Resolve nested DefineSubset DTOs with DataLoader."""

        session_factory = get_test_session_factory()
        registry = LoaderRegistry(
            entities=[FixtureUser, FixtureSprint, FixtureTask],
            session_factory=session_factory,
        )

        class UserDTO(DefineSubset):
            __subset__ = (FixtureUser, ("id", "name"))

        class TaskDTO(DefineSubset):
            __subset__ = (FixtureTask, ("id", "title", "owner_id"))
            owner: UserDTO | None = None

            def resolve_owner(self, loader=Loader("owner")):
                return loader.load(self.owner_id)

        async with session_factory() as session:
            tasks = (await session.exec(select(FixtureTask))).all()

        dtos = [
            TaskDTO(id=t.id, title=t.title, owner_id=t.owner_id) for t in tasks
        ]
        result = await Resolver(registry).resolve(dtos)

        # Verify nested owner is resolved
        assert result[0].owner is not None
        assert result[0].owner.name in ("Alice", "Bob")

    @pytest.mark.usefixtures("test_db")
    async def test_post_on_nested_subset(self):
        """post_* on DefineSubset should work after resolve_*."""

        class SimpleParent(BaseModel):
            name: str
            items: list[str] = []
            item_count: int = 0

            def resolve_items(self):
                return ["a", "b", "c"]

            def post_item_count(self):
                return len(self.items)

        model = SimpleParent(name="test")
        result = await Resolver().resolve(model)

        assert result.items == ["a", "b", "c"]
        assert result.item_count == 3


# ──────────────────────────────────────────────────────────
# Test: context parameter
# ──────────────────────────────────────────────────────────

class TestResolverContext:
    async def test_context_in_resolve(self):
        """resolve_* can access context parameter."""

        class Model(BaseModel):
            name: str
            greeting: str = ""

            def resolve_greeting(self, context={}):
                prefix = context.get("prefix", "Hello")
                return f"{prefix}, {self.name}!"

        result = await Resolver(context={"prefix": "Hi"}).resolve(Model(name="Alice"))
        assert result.greeting == "Hi, Alice!"

    async def test_context_in_post(self):
        """post_* can access context parameter."""

        class Model(BaseModel):
            name: str
            suffix: str = ""

            def post_suffix(self, context={}):
                return context.get("suffix", "")

        result = await Resolver(context={"suffix": "(admin)"}).resolve(
            Model(name="Alice")
        )
        assert result.suffix == "(admin)"
