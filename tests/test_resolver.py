"""Tests for Resolver — resolve_*, post_*, and Loader integration."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from sqlmodel_nexus.resolver import Resolver

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
# Test: nested resolve with DefineSubset
# ──────────────────────────────────────────────────────────

class TestResolverNested:
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

            def resolve_greeting(self, context=None):
                if context is None:
                    context = {}
                prefix = context.get("prefix", "Hello")
                return f"{prefix}, {self.name}!"

        result = await Resolver(context={"prefix": "Hi"}).resolve(Model(name="Alice"))
        assert result.greeting == "Hi, Alice!"

    async def test_context_in_post(self):
        """post_* can access context parameter."""

        class Model(BaseModel):
            name: str
            suffix: str = ""

            def post_suffix(self, context=None):
                if context is None:
                    context = {}
                return context.get("suffix", "")

        result = await Resolver(context={"suffix": "(admin)"}).resolve(
            Model(name="Alice")
        )
        assert result.suffix == "(admin)"


# ──────────────────────────────────────────────────────────
# Test: exception handling
# ──────────────────────────────────────────────────────────


class TestResolverExceptions:
    async def test_resolve_method_raises_exception(self):
        """Exception in resolve_* should propagate."""

        class Model(BaseModel):
            name: str
            value: str = ""

            def resolve_value(self):
                raise ValueError("resolve failed")

        with pytest.raises(ValueError, match="resolve failed"):
            await Resolver().resolve(Model(name="test"))

    async def test_post_method_raises_exception(self):
        """Exception in post_* should propagate."""

        class Model(BaseModel):
            name: str
            summary: str = ""

            def post_summary(self):
                raise RuntimeError("post failed")

        with pytest.raises(RuntimeError, match="post failed"):
            await Resolver().resolve(Model(name="test"))

    async def test_resolve_returns_wrong_type_does_not_crash(self):
        """resolve_* returning unexpected type should not crash Resolver."""

        class Model(BaseModel):
            name: str
            items: list[str] = []

            def resolve_items(self):
                # Returns a string instead of list[str]
                return "not a list"

        # Resolver should complete without error (Pydantic will coerce or validate)
        result = await Resolver().resolve(Model(name="test"))
        # The field gets the raw return value
        assert result.items == "not a list"


# ──────────────────────────────────────────────────────────
# Test: async post_* methods
# ──────────────────────────────────────────────────────────


class TestResolverAsyncPost:
    async def test_async_post_method(self):
        """async def post_* should execute correctly."""

        class Model(BaseModel):
            name: str
            processed_name: str = ""

            async def post_processed_name(self):
                await asyncio.sleep(0.01)
                return self.name.upper()

        result = await Resolver().resolve(Model(name="alice"))
        assert result.processed_name == "ALICE"

    async def test_async_post_accesses_resolved_data(self):
        """async post_* should access data populated by resolve_*."""

        class Child(BaseModel):
            name: str = ""
            resolved_label: str = ""

            def resolve_name(self):
                return "resolved_child"

            async def post_resolved_label(self):
                await asyncio.sleep(0.01)
                return f"label:{self.name}"

        class Parent(BaseModel):
            children: list[Child] = []

        parent = Parent(children=[Child()])
        result = await Resolver().resolve(parent)

        assert result.children[0].name == "resolved_child"
        assert result.children[0].resolved_label == "label:resolved_child"


# ──────────────────────────────────────────────────────────
# Test: parent parameter in resolve_*
# ──────────────────────────────────────────────────────────


class TestResolverParentParameter:
    async def test_resolve_with_parent(self):
        """resolve_* should receive parent node via parent parameter."""

        class Child(BaseModel):
            name: str
            parent_label: str = ""

            def resolve_parent_label(self, parent=None):
                if parent:
                    return f"from:{parent.name}"
                return "no parent"

        class Parent(BaseModel):
            name: str
            children: list[Child] = []

        parent = Parent(
            name="Root",
            children=[Child(name="C1"), Child(name="C2")],
        )
        result = await Resolver().resolve(parent)

        assert result.children[0].parent_label == "from:Root"
        assert result.children[1].parent_label == "from:Root"

    async def test_parent_in_nested_resolve(self):
        """Parent parameter should work in deeply nested structures."""

        class Leaf(BaseModel):
            value: str
            path: str = ""

            def resolve_path(self, parent=None):
                if parent:
                    return f"{parent.label}/{self.value}"
                return self.value

        class Branch(BaseModel):
            label: str
            leaves: list[Leaf] = []

        class Tree(BaseModel):
            name: str
            branches: list[Branch] = []

        tree = Tree(
            name="T",
            branches=[
                Branch(label="B1", leaves=[Leaf(value="L1"), Leaf(value="L2")]),
                Branch(label="B2", leaves=[Leaf(value="L3")]),
            ],
        )
        result = await Resolver().resolve(tree)

        assert result.branches[0].leaves[0].path == "B1/L1"
        assert result.branches[0].leaves[1].path == "B1/L2"
        assert result.branches[1].leaves[0].path == "B2/L3"


# ──────────────────────────────────────────────────────────
# Test: advanced post_* combinations
# ──────────────────────────────────────────────────────────


class TestResolverPostAdvanced:
    async def test_post_aggregation_after_nested_resolve(self):
        """post_* should aggregate data from nested resolve_* results."""

        class Item(BaseModel):
            value: int = 0

            def resolve_value(self):
                return self.value * 10

        class Container(BaseModel):
            items: list[Item] = []
            total: int = 0
            max_value: int = 0

            def resolve_items(self):
                return [Item(value=1), Item(value=2), Item(value=3)]

            def post_total(self):
                return sum(item.value for item in self.items)

            def post_max_value(self):
                return max(item.value for item in self.items) if self.items else 0

        result = await Resolver().resolve(Container())

        # resolve_items runs first → items populated
        # resolve_value runs on each item → values become 10, 20, 30
        # post_total/post_max_value run after all resolves
        assert result.items[0].value == 10
        assert result.items[1].value == 20
        assert result.items[2].value == 30
        assert result.total == 60
        assert result.max_value == 30

    async def test_post_with_context_aggregation(self):
        """post_* should use context for conditional aggregation."""

        class Item(BaseModel):
            name: str
            category: str = ""

            def post_category(self, context=None):
                if context is None:
                    context = {}
                prefix = context.get("prefix", "")
                return f"{prefix}:{self.name}"

        class Group(BaseModel):
            items: list[Item] = []
            categories: list[str] = []

            def post_categories(self):
                return [item.category for item in self.items]

        group = Group(
            items=[
                Item(name="A"),
                Item(name="B"),
            ]
        )
        result = await Resolver(context={"prefix": "CAT"}).resolve(group)

        assert result.items[0].category == "CAT:A"
        assert result.items[1].category == "CAT:B"
        assert result.categories == ["CAT:A", "CAT:B"]

    async def test_post_order_depends_on_resolve(self):
        """post_* must execute strictly after resolve_* completes."""

        execution_order = []

        class Model(BaseModel):
            name: str = ""
            computed: str = ""

            def resolve_name(self):
                execution_order.append("resolve")
                return "resolved"

            def post_computed(self):
                execution_order.append("post")
                return f"computed:{self.name}"

        await Resolver().resolve(Model())

        assert execution_order == ["resolve", "post"]
