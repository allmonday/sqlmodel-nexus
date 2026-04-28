"""Tests for Loader refactor (Depends) and AutoLoad."""

from __future__ import annotations

from typing import Annotated

import pytest
from aiodataloader import DataLoader
from pydantic import BaseModel
from sqlmodel import select

from sqlmodel_graphql import AutoLoad
from sqlmodel_graphql.loader.registry import LoaderRegistry
from sqlmodel_graphql.resolver import Depends, Loader, Resolver
from sqlmodel_graphql.subset import DefineSubset
from tests.conftest import (
    TestSprint,
    TestTask,
    TestUser,
    get_test_session_factory,
)

# ──────────────────────────────────────────────────────────
# Test: Loader(Depends) refactored to support multiple types
# ──────────────────────────────────────────────────────────

class TestLoaderDepends:
    def test_loader_returns_depends(self):
        """Loader() should return a Depends instance."""
        dep = Loader("owner")
        assert isinstance(dep, Depends)
        assert dep.dependency == "owner"

    def test_loader_with_none(self):
        """Loader(None) should return Depends with None dependency."""
        dep = Loader(None)
        assert isinstance(dep, Depends)
        assert dep.dependency is None

    def test_loader_with_class(self):
        """Loader(DataLoaderClass) should return Depends with class."""

        class MyLoader(DataLoader):
            async def batch_load_fn(self, keys):
                return [k * 2 for k in keys]

        dep = Loader(MyLoader)
        assert isinstance(dep, Depends)
        assert dep.dependency is MyLoader

    def test_loader_with_function(self):
        """Loader(fn) should return Depends with function."""

        async def my_batch_fn(keys):
            return keys

        dep = Loader(my_batch_fn)
        assert isinstance(dep, Depends)
        assert dep.dependency is my_batch_fn


class TestLoaderWithFunction:
    @pytest.mark.usefixtures("test_db")
    async def test_loader_with_async_batch_fn(self):
        """Loader(async_fn) should wrap function in DataLoader."""

        async def greeting_loader(names):
            return [f"Hello, {name}!" for name in names]

        class Model(BaseModel):
            name: str
            greeting: str = ""

            def resolve_greeting(self, loader=Loader(greeting_loader)):
                return loader.load(self.name)

        model = Model(name="Alice")
        result = await Resolver().resolve(model)

        assert result.greeting == "Hello, Alice!"

    @pytest.mark.usefixtures("test_db")
    async def test_loader_with_dataclass_caching(self):
        """Same function should return same DataLoader instance."""

        call_count = 0

        async def count_loader(keys):
            nonlocal call_count
            call_count += 1
            return [k * 2 for k in keys]

        class Model(BaseModel):
            val: int
            doubled: int = 0

            def resolve_doubled(self, loader=Loader(count_loader)):
                return loader.load(self.val)

        models = [Model(val=1), Model(val=2), Model(val=3)]
        await Resolver().resolve(models)

        # Should batch all 3 into a single call
        assert call_count == 1


class TestLoaderWithDataLoaderClass:
    @pytest.mark.usefixtures("test_db")
    async def test_loader_with_dataloader_subclass(self):
        """Loader(DataLoaderClass) should instantiate and use the class."""

        class ReverseLoader(DataLoader):
            async def batch_load_fn(self, keys):
                return [k[::-1] for k in keys]

        class Model(BaseModel):
            word: str
            reversed: str = ""

            def resolve_reversed(self, loader=Loader(ReverseLoader)):
                return loader.load(self.word)

        model = Model(word="hello")
        result = await Resolver().resolve(model)

        assert result.reversed == "olleh"

    @pytest.mark.usefixtures("test_db")
    async def test_loader_with_dataloader_class_batching(self):
        """DataLoader subclass should batch multiple requests."""

        call_count = 0

        class CountingLoader(DataLoader):
            async def batch_load_fn(self, keys):
                nonlocal call_count
                call_count += 1
                return [k + 10 for k in keys]

        class Model(BaseModel):
            val: int
            result: int = 0

            def resolve_result(self, loader=Loader(CountingLoader)):
                return loader.load(self.val)

        models = [Model(val=1), Model(val=2), Model(val=3)]
        await Resolver().resolve(models)

        assert call_count == 1
        assert models[0].result == 11
        assert models[1].result == 12
        assert models[2].result == 13


class TestLoaderWithStringName:
    @pytest.mark.usefixtures("test_db")
    async def test_loader_with_string_backward_compat(self):
        """Loader('name') should still work for LoaderRegistry lookup."""

        session_factory = get_test_session_factory()
        registry = LoaderRegistry(
            entities=[TestUser, TestSprint, TestTask],
            session_factory=session_factory,
        )

        class UserDTO(DefineSubset):
            __subset__ = (TestUser, ("id", "name"))

        class TaskDTO(DefineSubset):
            __subset__ = (TestTask, ("id", "title", "owner_id"))
            owner: UserDTO | None = None

            def resolve_owner(self, loader=Loader("owner")):
                return loader.load(self.owner_id)

        async with session_factory() as session:
            tasks = (await session.exec(select(TestTask))).all()

        dtos = [
            TaskDTO(id=t.id, title=t.title, owner_id=t.owner_id) for t in tasks
        ]
        result = await Resolver(registry).resolve(dtos)

        # All tasks should have owners resolved
        assert all(dto.owner is not None for dto in result)


# ──────────────────────────────────────────────────────────
# Test: AutoLoad
# ──────────────────────────────────────────────────────────

class TestAutoLoadBasic:
    @pytest.mark.usefixtures("test_db")
    async def test_autoload_many_to_one(self):
        """AutoLoad should auto-resolve many-to-one relationships."""

        session_factory = get_test_session_factory()
        registry = LoaderRegistry(
            entities=[TestUser, TestSprint, TestTask],
            session_factory=session_factory,
        )

        class UserDTO(DefineSubset):
            __subset__ = (TestUser, ("id", "name"))

        class TaskDTO(DefineSubset):
            __subset__ = (TestTask, ("id", "title", "owner_id"))
            owner: Annotated[UserDTO | None, AutoLoad()] = None

        async with session_factory() as session:
            tasks = (await session.exec(select(TestTask))).all()

        dtos = [
            TaskDTO(id=t.id, title=t.title, owner_id=t.owner_id) for t in tasks
        ]
        result = await Resolver(registry).resolve(dtos)

        # All tasks should have owners auto-loaded
        assert all(dto.owner is not None for dto in result)
        owner_names = {dto.owner.name for dto in result}
        assert "Alice" in owner_names
        assert "Bob" in owner_names

    @pytest.mark.usefixtures("test_db")
    async def test_autoload_one_to_many(self):
        """AutoLoad should auto-resolve one-to-many relationships."""

        session_factory = get_test_session_factory()
        registry = LoaderRegistry(
            entities=[TestUser, TestSprint, TestTask],
            session_factory=session_factory,
        )

        class UserDTO(DefineSubset):
            __subset__ = (TestUser, ("id", "name"))

        class TaskDTO(DefineSubset):
            __subset__ = (TestTask, ("id", "title", "owner_id"))
            owner: Annotated[UserDTO | None, AutoLoad()] = None

        class SprintDTO(DefineSubset):
            __subset__ = (TestSprint, ("id", "name"))
            tasks: Annotated[list[TaskDTO], AutoLoad()] = []

        async with session_factory() as session:
            sprints = (await session.exec(select(TestSprint))).all()

        dtos = [SprintDTO(id=s.id, name=s.name) for s in sprints]
        result = await Resolver(registry).resolve(dtos)

        # Each sprint should have tasks auto-loaded
        assert len(result[0].tasks) == 2  # Sprint 1: Task A, Task B
        assert len(result[1].tasks) == 2  # Sprint 2: Task C, Task D

        # Tasks should have owners auto-loaded too (nested AutoLoad)
        assert all(t.owner is not None for t in result[0].tasks)
        assert all(t.owner is not None for t in result[1].tasks)

    @pytest.mark.usefixtures("test_db")
    async def test_autoload_with_post_methods(self):
        """AutoLoad + post_* should work together."""

        session_factory = get_test_session_factory()
        registry = LoaderRegistry(
            entities=[TestUser, TestSprint, TestTask],
            session_factory=session_factory,
        )

        class UserDTO(DefineSubset):
            __subset__ = (TestUser, ("id", "name"))

        class TaskDTO(DefineSubset):
            __subset__ = (TestTask, ("id", "title", "owner_id"))
            owner: Annotated[UserDTO | None, AutoLoad()] = None

        class SprintDTO(DefineSubset):
            __subset__ = (TestSprint, ("id", "name"))
            tasks: Annotated[list[TaskDTO], AutoLoad()] = []
            task_count: int = 0

            def post_task_count(self):
                return len(self.tasks)

        async with session_factory() as session:
            sprints = (await session.exec(select(TestSprint))).all()

        dtos = [SprintDTO(id=s.id, name=s.name) for s in sprints]
        result = await Resolver(registry).resolve(dtos)

        # post_task_count should work after AutoLoad
        assert result[0].task_count == 2
        assert result[1].task_count == 2

        # All tasks should have owners auto-loaded (nested AutoLoad)
        for sprint_dto in result:
            for task_dto in sprint_dto.tasks:
                assert task_dto.owner is not None

    @pytest.mark.usefixtures("test_db")
    async def test_autoload_manual_resolve_takes_priority(self):
        """Manual resolve_* method should take priority over AutoLoad."""

        session_factory = get_test_session_factory()
        registry = LoaderRegistry(
            entities=[TestUser, TestSprint, TestTask],
            session_factory=session_factory,
        )

        class UserDTO(DefineSubset):
            __subset__ = (TestUser, ("id", "name"))

        class TaskDTO(DefineSubset):
            __subset__ = (TestTask, ("id", "title", "owner_id"))
            owner: Annotated[UserDTO | None, AutoLoad()] = None

            # Manual resolve should override AutoLoad
            def resolve_owner(self):
                return UserDTO(id=999, name="Manual Override")

        async with session_factory() as session:
            tasks = (await session.exec(select(TestTask))).all()

        dtos = [
            TaskDTO(id=t.id, title=t.title, owner_id=t.owner_id) for t in tasks
        ]
        result = await Resolver(registry).resolve(dtos)

        # Manual resolve should win over AutoLoad
        assert all(dto.owner.name == "Manual Override" for dto in result)

    @pytest.mark.usefixtures("test_db")
    async def test_autoload_with_nonexistent_fk(self):
        """AutoLoad should handle non-existent FK value gracefully."""

        session_factory = get_test_session_factory()
        registry = LoaderRegistry(
            entities=[TestUser, TestSprint, TestTask],
            session_factory=session_factory,
        )

        class UserDTO(DefineSubset):
            __subset__ = (TestUser, ("id", "name"))

        class TaskDTO(DefineSubset):
            __subset__ = (TestTask, ("id", "title", "owner_id"))
            owner: Annotated[UserDTO | None, AutoLoad()] = None

        # Create a task with a non-existent FK value
        dto = TaskDTO(id=99, title="Orphan", owner_id=9999)
        result = await Resolver(registry).resolve(dto)

        # owner should remain None since no user with id=9999 exists
        assert result.owner is None


class TestAutoLoadSubsetFields:
    def test_subset_fields_stored(self):
        """DefineSubset should store __subset_fields__."""

        class UserDTO(DefineSubset):
            __subset__ = (TestUser, ("id", "name"))

        assert hasattr(UserDTO, "__subset_fields__")
        assert UserDTO.__subset_fields__ == ["id", "name"]

    def test_subset_fields_includes_fk(self):
        """__subset_fields__ should include FK fields."""

        class TaskDTO(DefineSubset):
            __subset__ = (TestTask, ("id", "title", "owner_id"))

        assert "owner_id" in TaskDTO.__subset_fields__

    def test_subset_fields_excludes_non_selected(self):
        """__subset_fields__ should only include selected fields."""

        class TaskDTO(DefineSubset):
            __subset__ = (TestTask, ("id", "title"))

        assert "owner_id" not in TaskDTO.__subset_fields__
        assert TaskDTO.__subset_fields__ == ["id", "title"]


# ──────────────────────────────────────────────────────────
# Test: Implicit AutoLoad (no annotation needed)
# ──────────────────────────────────────────────────────────

class TestImplicitAutoLoad:
    @pytest.mark.usefixtures("test_db")
    async def test_implicit_many_to_one(self):
        """Fields matching a relationship name should auto-load without AutoLoad()."""

        session_factory = get_test_session_factory()
        registry = LoaderRegistry(
            entities=[TestUser, TestSprint, TestTask],
            session_factory=session_factory,
        )

        class UserDTO(DefineSubset):
            __subset__ = (TestUser, ("id", "name"))

        class TaskDTO(DefineSubset):
            __subset__ = (TestTask, ("id", "title", "owner_id"))
            # No AutoLoad() — field name 'owner' matches Task.owner relationship
            owner: UserDTO | None = None

        async with session_factory() as session:
            tasks = (await session.exec(select(TestTask))).all()

        dtos = [
            TaskDTO(id=t.id, title=t.title, owner_id=t.owner_id) for t in tasks
        ]
        result = await Resolver(registry).resolve(dtos)

        # All tasks should have owners auto-loaded implicitly
        assert all(dto.owner is not None for dto in result)
        owner_names = {dto.owner.name for dto in result}
        assert "Alice" in owner_names
        assert "Bob" in owner_names

    @pytest.mark.usefixtures("test_db")
    async def test_implicit_one_to_many(self):
        """One-to-many fields matching relationship name should auto-load."""

        session_factory = get_test_session_factory()
        registry = LoaderRegistry(
            entities=[TestUser, TestSprint, TestTask],
            session_factory=session_factory,
        )

        class UserDTO(DefineSubset):
            __subset__ = (TestUser, ("id", "name"))

        class TaskDTO(DefineSubset):
            __subset__ = (TestTask, ("id", "title", "owner_id"))
            owner: UserDTO | None = None

        class SprintDTO(DefineSubset):
            __subset__ = (TestSprint, ("id", "name"))
            # No AutoLoad() — field name 'tasks' matches Sprint.tasks relationship
            tasks: list[TaskDTO] = []

        async with session_factory() as session:
            sprints = (await session.exec(select(TestSprint))).all()

        dtos = [SprintDTO(id=s.id, name=s.name) for s in sprints]
        result = await Resolver(registry).resolve(dtos)

        # Each sprint should have tasks auto-loaded
        assert len(result[0].tasks) == 2
        assert len(result[1].tasks) == 2

        # Nested implicit loading: task owners should also be loaded
        assert all(t.owner is not None for t in result[0].tasks)

    @pytest.mark.usefixtures("test_db")
    async def test_implicit_with_post_methods(self):
        """Implicit auto-load + post_* should work together."""

        session_factory = get_test_session_factory()
        registry = LoaderRegistry(
            entities=[TestUser, TestSprint, TestTask],
            session_factory=session_factory,
        )

        class UserDTO(DefineSubset):
            __subset__ = (TestUser, ("id", "name"))

        class TaskDTO(DefineSubset):
            __subset__ = (TestTask, ("id", "title", "owner_id"))
            owner: UserDTO | None = None

        class SprintDTO(DefineSubset):
            __subset__ = (TestSprint, ("id", "name"))
            tasks: list[TaskDTO] = []
            task_count: int = 0

            def post_task_count(self):
                return len(self.tasks)

        async with session_factory() as session:
            sprints = (await session.exec(select(TestSprint))).all()

        dtos = [SprintDTO(id=s.id, name=s.name) for s in sprints]
        result = await Resolver(registry).resolve(dtos)

        assert result[0].task_count == 2
        assert result[1].task_count == 2

    @pytest.mark.usefixtures("test_db")
    async def test_implicit_does_not_trigger_for_non_relationship_fields(self):
        """Fields that don't match a relationship should NOT auto-load."""

        session_factory = get_test_session_factory()
        registry = LoaderRegistry(
            entities=[TestUser, TestSprint, TestTask],
            session_factory=session_factory,
        )

        class UserDTO(DefineSubset):
            __subset__ = (TestUser, ("id", "name"))

        class TaskDTO(DefineSubset):
            __subset__ = (TestTask, ("id", "title", "owner_id"))
            # 'assignee' does NOT match any relationship on TestTask
            # (only 'owner' and 'sprint' are relationships)
            assignee: UserDTO | None = None

        async with session_factory() as session:
            tasks = (await session.exec(select(TestTask))).all()

        dtos = [
            TaskDTO(id=t.id, title=t.title, owner_id=t.owner_id) for t in tasks
        ]
        result = await Resolver(registry).resolve(dtos)

        # 'assignee' should NOT be auto-loaded (no matching relationship)
        assert all(dto.assignee is None for dto in result)

    @pytest.mark.usefixtures("test_db")
    async def test_explicit_autoload_still_works(self):
        """Explicit AutoLoad() annotation should still work."""

        session_factory = get_test_session_factory()
        registry = LoaderRegistry(
            entities=[TestUser, TestSprint, TestTask],
            session_factory=session_factory,
        )

        class UserDTO(DefineSubset):
            __subset__ = (TestUser, ("id", "name"))

        class TaskDTO(DefineSubset):
            __subset__ = (TestTask, ("id", "title", "owner_id"))
            owner: Annotated[UserDTO | None, AutoLoad()] = None

        async with session_factory() as session:
            tasks = (await session.exec(select(TestTask))).all()

        dtos = [
            TaskDTO(id=t.id, title=t.title, owner_id=t.owner_id) for t in tasks
        ]
        result = await Resolver(registry).resolve(dtos)

        assert all(dto.owner is not None for dto in result)
