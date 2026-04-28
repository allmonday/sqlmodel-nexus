"""Tests for DefineSubset — independent DTO layer from SQLModel entities."""

from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel
from sqlmodel import Field, SQLModel

from sqlmodel_graphql.context import scan_expose_fields
from sqlmodel_graphql.subset import (
    SUBSET_REFERENCE,
    DefineSubset,
    get_subset_source,
)

# ──────────────────────────────────────────────────────────
# Test entities
# ──────────────────────────────────────────────────────────

class SampleUser(SQLModel, table=False):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str


class SamplePost(SQLModel, table=False):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    content: str
    author_id: int = Field(foreign_key="sample_user.id")


# ──────────────────────────────────────────────────────────
# Test: basic field selection
# ──────────────────────────────────────────────────────────


class TestDefineSubsetBasic:
    def test_subset_creates_pydantic_model(self):
        """DefineSubset should create a pure Pydantic BaseModel, not SQLModel."""

        class UserSummary(DefineSubset):
            __subset__ = (SampleUser, ("id", "name"))

        assert issubclass(UserSummary, BaseModel)
        # Should NOT be a SQLModel with table=True
        assert not issubclass(UserSummary, SQLModel) or not getattr(
            UserSummary, "__tablename__", None
        )

    def test_subset_only_includes_selected_fields(self):
        """Only selected fields should appear in the DTO."""

        class UserSummary(DefineSubset):
            __subset__ = (SampleUser, ("id", "name"))

        assert "id" in UserSummary.model_fields
        assert "name" in UserSummary.model_fields
        assert "email" not in UserSummary.model_fields

    def test_subset_model_validate(self):
        """DTO should be creatable from source entity via model_validate."""

        class UserSummary(DefineSubset):
            __subset__ = (SampleUser, ("id", "name"))

        user = SampleUser(id=1, name="Alice", email="alice@test.com")
        dto = UserSummary.model_validate(user)

        assert dto.id == 1
        assert dto.name == "Alice"
        # email should not be present (or None)
        assert not hasattr(dto, "email") or dto.email is None

    def test_subset_source_registration(self):
        """Source entity should be registered in the subset registry."""

        class UserSummary(DefineSubset):
            __subset__ = (SampleUser, ("id", "name"))

        assert get_subset_source(UserSummary) is SampleUser
        assert getattr(UserSummary, SUBSET_REFERENCE, None) is SampleUser

    def test_subset_preserves_field_types(self):
        """Field types should be preserved from the source entity."""

        class UserSummary(DefineSubset):
            __subset__ = (SampleUser, ("id", "name"))

        assert UserSummary.model_fields["id"].annotation == int | None
        assert UserSummary.model_fields["name"].annotation == str


# ──────────────────────────────────────────────────────────
# Test: FK field handling
# ──────────────────────────────────────────────────────────

class TestDefineSubsetFK:
    def test_fk_field_hidden_from_output(self):
        """FK fields should have exclude=True, hiding them from serialization."""

        class PostSummary(DefineSubset):
            __subset__ = (SamplePost, ("id", "title", "author_id"))

        assert "author_id" in PostSummary.model_fields
        # FK field should be excluded from serialization
        assert PostSummary.model_fields["author_id"].exclude is True

    def test_fk_field_available_internally(self):
        """FK fields should still be accessible in code even if excluded from output."""

        class PostSummary(DefineSubset):
            __subset__ = (SamplePost, ("id", "title", "author_id"))

        post = SamplePost(id=1, title="Hello", content="World", author_id=42)
        dto = PostSummary.model_validate(post)

        # Internal access works
        assert dto.author_id == 42
        # But serialization excludes it
        data = dto.model_dump()
        assert "author_id" not in data

    def test_fk_without_select(self):
        """If FK is not in field list, it should not appear in DTO."""

        class PostSummary(DefineSubset):
            __subset__ = (SamplePost, ("id", "title"))

        assert "author_id" not in PostSummary.model_fields


# ──────────────────────────────────────────────────────────
# Test: extra fields
# ──────────────────────────────────────────────────────────

class TestDefineSubsetExtraFields:
    def test_extra_field_declaration(self):
        """Extra fields can be declared in the DefineSubset class body."""

        class UserSummary(DefineSubset):
            __subset__ = (SampleUser, ("id", "name"))
            display_name: str = ""

        assert "display_name" in UserSummary.model_fields
        dto = UserSummary(id=1, name="Alice", display_name="Alice (Admin)")
        assert dto.display_name == "Alice (Admin)"

    def test_extra_field_with_none_default(self):
        """Extra fields with Optional type and None default."""

        class UserSummary(DefineSubset):
            __subset__ = (SampleUser, ("id", "name"))
            nickname: str | None = None

        dto = UserSummary(id=1, name="Alice")
        assert dto.nickname is None

    def test_subset_field_reannotation_allowed(self):
        """Subset fields can be re-annotated with metadata (e.g., ExposeAs)."""


        from sqlmodel_graphql.context import ExposeAs

        class ReAnnotatedSubset(DefineSubset):
            __subset__ = (SampleUser, ("id", "name"))
            name: Annotated[str, ExposeAs("user_name")]

        # ExposeAs metadata should be present on the 'name' field
        expose = scan_expose_fields(ReAnnotatedSubset)
        assert expose == {"name": "user_name"}

        # Field should still work normally
        instance = ReAnnotatedSubset(id=1, name="test")
        assert instance.name == "test"


# ──────────────────────────────────────────────────────────
# Test: validation errors
# ──────────────────────────────────────────────────────────

class TestDefineSubsetValidation:
    def test_missing_subset_definition(self):
        """Class without __subset__ should raise ValueError."""

        with pytest.raises(ValueError, match="must define"):

            class BadSubset(DefineSubset):
                pass

    def test_invalid_field_name(self):
        """Non-existent field should raise AttributeError."""

        with pytest.raises(AttributeError, match="does not exist"):

            class BadSubset(DefineSubset):
                __subset__ = (SampleUser, ("id", "nonexistent"))

    def test_non_string_field_name(self):
        """Non-string field name should raise TypeError."""

        with pytest.raises(TypeError, match="must be a string"):

            class BadSubset(DefineSubset):
                __subset__ = (SampleUser, ("id", 123))  # type: ignore

    def test_duplicate_field_name(self):
        """Duplicate field name should raise ValueError."""

        with pytest.raises(ValueError, match="duplicate"):

            class BadSubset(DefineSubset):
                __subset__ = (SampleUser, ("id", "id"))

    def test_non_sqlmodel_entity(self):
        """Non-SQLModel entity should raise TypeError."""

        with pytest.raises(TypeError, match="SQLModel"):

            class BadSubset(DefineSubset):
                __subset__ = (str, ("upper",))  # type: ignore


# ──────────────────────────────────────────────────────────
# Test: methods
# ──────────────────────────────────────────────────────────

class TestDefineSubsetMethods:
    def test_post_method_attached(self):
        """post_* methods should be attached to the generated class."""

        class UserSummary(DefineSubset):
            __subset__ = (SampleUser, ("id", "name"))
            greeting: str = ""

            def post_greeting(self):
                return f"Hello, {self.name}!"

        assert hasattr(UserSummary, "post_greeting")
        dto = UserSummary(id=1, name="Alice")
        assert dto.post_greeting() == "Hello, Alice!"

    def test_resolve_method_attached(self):
        """resolve_* methods should be attached to the generated class."""

        class UserSummary(DefineSubset):
            __subset__ = (SampleUser, ("id", "name"))
            extra: str = ""

            def resolve_extra(self):
                return "resolved"

        assert hasattr(UserSummary, "resolve_extra")
        dto = UserSummary(id=1, name="Alice")
        assert dto.resolve_extra() == "resolved"


# ──────────────────────────────────────────────────────────
# Test: nested subsets
# ──────────────────────────────────────────────────────────

class TestDefineSubsetNested:
    def test_nested_subset_reference(self):
        """One DefineSubset can reference another as a field type."""

        class UserBrief(DefineSubset):
            __subset__ = (SampleUser, ("id", "name"))

        class PostBrief(DefineSubset):
            __subset__ = (SamplePost, ("id", "title"))
            author: UserBrief | None = None

        assert "author" in PostBrief.model_fields
        dto = PostBrief(id=1, title="Hello", author=UserBrief(id=42, name="Alice"))
        assert dto.author.name == "Alice"


# ──────────────────────────────────────────────────────────
# Test: SQLModel type validation for relationship fields
# ──────────────────────────────────────────────────────────

# Need table=True entities for SQLAlchemy relationship inspection
from tests.conftest import TestSprint, TestTask, TestUser, get_test_session_factory


class TestSQLModelRelationshipTypeValidation:
    def test_raw_sqlmodel_type_on_relationship_raises(self):
        """Using a raw SQLModel entity as relationship field type should raise TypeError."""

        with pytest.raises(TypeError, match="must use a DTO type"):

            class TaskBad(DefineSubset):
                __subset__ = (TestTask, ("id", "title", "owner_id"))
                owner: TestUser | None = None  # raw SQLModel → error

    def test_sqlmodel_in_list_raises(self):
        """Using raw SQLModel in list[Entity] should raise TypeError."""

        with pytest.raises(TypeError, match="must use a DTO type"):

            class SprintBad(DefineSubset):
                __subset__ = (TestSprint, ("id", "name"))
                tasks: list[TestTask] = []  # raw SQLModel in list → error

    def test_sqlmodel_in_annotated_raises(self):
        """Using Annotated[Entity, ...] should raise TypeError."""

        from sqlmodel_graphql import SendTo

        with pytest.raises(TypeError, match="must use a DTO type"):

            class TaskBadAnnotated(DefineSubset):
                __subset__ = (TestTask, ("id", "title", "owner_id"))
                owner: Annotated[TestUser | None, SendTo("owners")] = None

    def test_dto_type_on_relationship_works(self):
        """Using a DefineSubset DTO type for relationship field should work fine."""

        class UserDTO(DefineSubset):
            __subset__ = (TestUser, ("id", "name"))

        class TaskDTO(DefineSubset):
            __subset__ = (TestTask, ("id", "title", "owner_id"))
            owner: UserDTO | None = None

        assert "owner" in TaskDTO.model_fields

    def test_dto_in_list_works(self):
        """Using list[DTO] for one-to-many relationship should work fine."""

        class TaskDTO(DefineSubset):
            __subset__ = (TestTask, ("id", "title", "owner_id"))

        class SprintDTO(DefineSubset):
            __subset__ = (TestSprint, ("id", "name"))
            tasks: list[TaskDTO] = []

        assert "tasks" in SprintDTO.model_fields

    def test_non_relationship_field_allows_any_type(self):
        """Fields that don't match a relationship name should accept any type."""

        class TaskDTO(DefineSubset):
            __subset__ = (TestTask, ("id", "title", "owner_id"))
            # 'assignee' does NOT match any relationship on TestTask
            # (relationships are 'owner' and 'sprint')
            assignee: TestUser | None = None

        # Should not raise — 'assignee' is not a relationship name
        assert "assignee" in TaskDTO.model_fields


# ──────────────────────────────────────────────────────────
# Test: SubsetConfig
# ──────────────────────────────────────────────────────────


class TestSubsetConfig:
    def test_config_with_fields(self):
        """SubsetConfig(fields=[...]) basic usage."""
        from sqlmodel_graphql.subset import SubsetConfig

        class UserSub(DefineSubset):
            __subset__ = SubsetConfig(
                kls=SampleUser,
                fields=["id", "name"],
            )

        assert "id" in UserSub.model_fields
        assert "name" in UserSub.model_fields
        assert "email" not in UserSub.model_fields
        dto = UserSub(id=1, name="Alice")
        assert dto.id == 1

    def test_config_with_omit_fields(self):
        """SubsetConfig(omit_fields=[...]) inverse selection."""

        from sqlmodel_graphql.subset import SubsetConfig

        class UserSub(DefineSubset):
            __subset__ = SubsetConfig(
                kls=SampleUser,
                omit_fields=["email"],
            )

        assert "id" in UserSub.model_fields
        assert "name" in UserSub.model_fields
        assert "email" not in UserSub.model_fields

    def test_config_with_fields_all(self):
        """SubsetConfig(fields='all') includes all fields."""

        from sqlmodel_graphql.subset import SubsetConfig

        class UserSub(DefineSubset):
            __subset__ = SubsetConfig(
                kls=SampleUser,
                fields="all",
            )

        assert set(UserSub.model_fields.keys()) == set(SampleUser.model_fields.keys())

    def test_config_with_omit_empty(self):
        """SubsetConfig(omit_fields=[]) is equivalent to fields='all'."""

        from sqlmodel_graphql.subset import SubsetConfig

        class UserSub(DefineSubset):
            __subset__ = SubsetConfig(
                kls=SampleUser,
                omit_fields=[],
            )

        assert set(UserSub.model_fields.keys()) == set(SampleUser.model_fields.keys())

    def test_config_with_excluded_fields(self):
        """excluded_fields should set exclude=True and hide from serialization."""

        from sqlmodel_graphql.subset import SubsetConfig

        class UserSub(DefineSubset):
            __subset__ = SubsetConfig(
                kls=SampleUser,
                fields=["id", "name", "email"],
                excluded_fields=["email"],
            )

        dto = UserSub(id=1, name="Alice", email="alice@test.com")
        assert dto.email == "alice@test.com"
        assert UserSub.model_fields["email"].exclude is True
        assert "email" not in dto.model_dump()

    def test_config_with_expose_as(self):
        """expose_as should add ExposeInfo metadata to fields."""

        from sqlmodel_graphql.subset import SubsetConfig

        class UserSub(DefineSubset):
            __subset__ = SubsetConfig(
                kls=SampleUser,
                fields=["id", "name"],
                expose_as=[("name", "user_name")],
            )

        expose = scan_expose_fields(UserSub)
        assert expose == {"name": "user_name"}

    def test_config_with_send_to(self):
        """send_to should add SendToInfo metadata to fields."""

        from sqlmodel_graphql.context import scan_send_to_fields
        from sqlmodel_graphql.subset import SubsetConfig

        class UserSub(DefineSubset):
            __subset__ = SubsetConfig(
                kls=SampleUser,
                fields=["id", "name", "email"],
                send_to=[("email", "email_collector")],
            )

        send_to = scan_send_to_fields(UserSub)
        assert "email" in send_to
        assert send_to["email"] == "email_collector"

    def test_config_with_send_to_tuple(self):
        """send_to with tuple of collector names."""

        from sqlmodel_graphql.context import scan_send_to_fields
        from sqlmodel_graphql.subset import SubsetConfig

        class UserSub(DefineSubset):
            __subset__ = SubsetConfig(
                kls=SampleUser,
                fields=["id", "name", "email"],
                send_to=[("email", ("col_a", "col_b"))],
            )

        send_to = scan_send_to_fields(UserSub)
        assert send_to["email"] == ("col_a", "col_b")

    def test_config_fields_and_omit_exclusive(self):
        """fields + omit_fields both specified should raise ValueError."""

        from sqlmodel_graphql.subset import SubsetConfig

        with pytest.raises(ValueError, match="exclusive"):
            SubsetConfig(
                kls=SampleUser,
                fields=["id"],
                omit_fields=["email"],
            )

    def test_config_missing_both(self):
        """Neither fields nor omit_fields should raise ValueError."""

        from sqlmodel_graphql.subset import SubsetConfig

        with pytest.raises(ValueError, match="must be provided"):
            SubsetConfig(kls=SampleUser)

    def test_config_with_extra_fields(self):
        """SubsetConfig + class body extra fields should coexist."""

        from sqlmodel_graphql.subset import SubsetConfig

        class UserSub(DefineSubset):
            __subset__ = SubsetConfig(
                kls=SampleUser,
                fields=["id", "name"],
            )
            display_name: str = ""

        assert "id" in UserSub.model_fields
        assert "display_name" in UserSub.model_fields

    def test_config_source_registration(self):
        """SubsetConfig-based DTO should register source entity."""

        from sqlmodel_graphql.subset import SubsetConfig

        class UserSub(DefineSubset):
            __subset__ = SubsetConfig(
                kls=SampleUser,
                fields=["id", "name"],
            )

        assert get_subset_source(UserSub) is SampleUser

    def test_config_with_sqlmodel_table_true(self):
        """SubsetConfig with table=True entity (with relationships)."""

        from sqlmodel_graphql.subset import SubsetConfig

        class TaskDTO(DefineSubset):
            __subset__ = SubsetConfig(
                kls=TestTask,
                fields=["id", "title", "owner_id"],
            )

        assert "id" in TaskDTO.model_fields
        assert "title" in TaskDTO.model_fields
        # FK field should be present but excluded
        assert "owner_id" in TaskDTO.model_fields


# ──────────────────────────────────────────────────────────
# Test: SubsetConfig end-to-end integration with Resolver
# ──────────────────────────────────────────────────────────


class TestSubsetConfigIntegration:
    """End-to-end tests: SubsetConfig metadata flows through Resolver correctly."""

    @pytest.mark.usefixtures("test_db")
    async def test_expose_as_with_resolver(self):
        """SubsetConfig expose_as should work through Resolver end-to-end."""
        from sqlmodel import select

        from sqlmodel_graphql.resolver import Resolver
        from sqlmodel_graphql.subset import SubsetConfig

        class ChildDTO(DefineSubset):
            __subset__ = SubsetConfig(
                kls=TestTask,
                fields=["id", "title"],
            )
            parent_name: str = ""

            def post_parent_name(self, ancestor_context={}):
                return ancestor_context.get("sprint_name", "unknown")

        class ParentDTO(DefineSubset):
            __subset__ = SubsetConfig(
                kls=TestSprint,
                fields=["id", "name"],
                expose_as=[("name", "sprint_name")],
            )
            tasks: list[ChildDTO] = []

        session_factory = get_test_session_factory()
        async with session_factory() as session:
            sprints = (await session.exec(select(TestSprint))).all()

        dtos = [ParentDTO(id=s.id, name=s.name) for s in sprints]
        result = await Resolver().resolve(dtos)

        # ExposeAs('sprint_name') should propagate to children
        for sprint_dto in result:
            for task_dto in sprint_dto.tasks:
                assert task_dto.parent_name == sprint_dto.name

    async def test_send_to_on_extra_field_with_resolver(self):
        """SubsetConfig send_to on an extra field should collect through Resolver."""
        from sqlmodel import select

        from sqlmodel_graphql.context import Collector
        from sqlmodel_graphql.loader.registry import LoaderRegistry
        from sqlmodel_graphql.resolver import Resolver
        from sqlmodel_graphql.subset import SubsetConfig
        from tests.conftest import init_test_db, seed_test_data
        await init_test_db()
        await seed_test_data()

        session_factory = get_test_session_factory()
        registry = LoaderRegistry(
            entities=[TestUser, TestSprint, TestTask],
            session_factory=session_factory,
        )

        class UserDTO(DefineSubset):
            __subset__ = SubsetConfig(kls=TestUser, fields=["id", "name"])

        class TaskDTO(DefineSubset):
            __subset__ = SubsetConfig(
                kls=TestTask,
                fields=["id", "title", "owner_id"],
                send_to=[("owner", "contributors")],
            )
            owner: UserDTO | None = None

        class SprintDTO(DefineSubset):
            __subset__ = SubsetConfig(kls=TestSprint, fields=["id", "name"])
            tasks: list[TaskDTO] = []
            contributors: list[UserDTO] = []

            def post_contributors(self, collector=Collector("contributors")):
                return collector.values()

        async with session_factory() as session:
            sprints = (await session.exec(select(TestSprint))).all()

        dtos = [SprintDTO(id=s.id, name=s.name) for s in sprints]
        result = await Resolver(registry).resolve(dtos)

        # Each sprint should collect owners from tasks via SendTo + Collector
        for sprint_dto in result:
            assert len(sprint_dto.contributors) > 0
            # Contributors should be UserDTO instances loaded via DataLoader
            for c in sprint_dto.contributors:
                assert isinstance(c, UserDTO)
                assert c.name in {"Alice", "Bob"}

    @pytest.mark.usefixtures("test_db")
    async def test_expose_as_and_send_to_combined(self):
        """SubsetConfig expose_as + send_to should work together in Resolver."""
        from sqlmodel import select

        from sqlmodel_graphql.context import Collector
        from sqlmodel_graphql.loader.registry import LoaderRegistry
        from sqlmodel_graphql.resolver import Resolver
        from sqlmodel_graphql.subset import SubsetConfig
        from tests.conftest import init_test_db, seed_test_data
        await init_test_db()
        await seed_test_data()

        session_factory = get_test_session_factory()
        registry = LoaderRegistry(
            entities=[TestUser, TestSprint, TestTask],
            session_factory=session_factory,
        )

        class UserDTO(DefineSubset):
            __subset__ = SubsetConfig(kls=TestUser, fields=["id", "name"])

        class TaskDTO(DefineSubset):
            __subset__ = SubsetConfig(
                kls=TestTask,
                fields=["id", "title", "owner_id"],
                send_to=[("owner", "contributors")],
            )
            owner: UserDTO | None = None
            full_title: str = ""

            def post_full_title(self, ancestor_context={}):
                sprint_name = ancestor_context.get("sprint_name", "unknown")
                return f"{sprint_name} / {self.title}"

        class SprintDTO(DefineSubset):
            __subset__ = SubsetConfig(
                kls=TestSprint,
                fields=["id", "name"],
                expose_as=[("name", "sprint_name")],
            )
            tasks: list[TaskDTO] = []
            contributors: list[UserDTO] = []

            def post_contributors(self, collector=Collector("contributors")):
                return collector.values()

        async with session_factory() as session:
            sprints = (await session.exec(select(TestSprint))).all()

        dtos = [SprintDTO(id=s.id, name=s.name) for s in sprints]
        result = await Resolver(registry).resolve(dtos)

        for sprint_dto in result:
            # ExposeAs: children see sprint_name
            for task_dto in sprint_dto.tasks:
                assert task_dto.full_title == f"{sprint_dto.name} / {task_dto.title}"
            # SendTo + Collector: owners collected
            assert len(sprint_dto.contributors) > 0

    @pytest.mark.usefixtures("test_db")
    async def test_excluded_fields_hidden_in_serialization(self):
        """SubsetConfig excluded_fields should hide fields from model_dump."""
        from sqlmodel import select

        from sqlmodel_graphql.subset import SubsetConfig

        class TaskDTO(DefineSubset):
            __subset__ = SubsetConfig(
                kls=TestTask,
                fields=["id", "title", "owner_id"],
                excluded_fields=["owner_id"],
            )

        session_factory = get_test_session_factory()
        async with session_factory() as session:
            tasks = (await session.exec(select(TestTask))).all()

        dtos = [TaskDTO.model_validate(t) for t in tasks]
        for dto in dtos:
            # Internally accessible
            assert dto.owner_id is not None
            # Hidden from serialization
            assert "owner_id" not in dto.model_dump()

    @pytest.mark.usefixtures("test_db")
    async def test_fields_all_with_relationships(self):
        """SubsetConfig fields='all' should include all scalar fields + implicit AutoLoad."""
        from sqlmodel import select

        from sqlmodel_graphql.loader.registry import LoaderRegistry
        from sqlmodel_graphql.resolver import Resolver
        from sqlmodel_graphql.subset import SubsetConfig
        from tests.conftest import init_test_db, seed_test_data
        await init_test_db()
        await seed_test_data()

        session_factory = get_test_session_factory()
        registry = LoaderRegistry(
            entities=[TestUser, TestSprint, TestTask],
            session_factory=session_factory,
        )

        class UserDTO(DefineSubset):
            __subset__ = SubsetConfig(kls=TestUser, fields="all")

        # Use explicit fields to avoid relationship fields (sprint, owner)
        # that would cause DetachedInstanceError during model_validate
        class TaskDTO(DefineSubset):
            __subset__ = SubsetConfig(
                kls=TestTask,
                fields=["id", "title", "sprint_id", "owner_id"],
            )
            owner: UserDTO | None = None

        async with session_factory() as session:
            tasks = (await session.exec(select(TestTask))).all()

        # Build DTOs manually to avoid DetachedInstanceError from relationship attrs
        dtos = [
            TaskDTO(id=t.id, title=t.title, sprint_id=t.sprint_id, owner_id=t.owner_id)
            for t in tasks
        ]
        result = await Resolver(registry).resolve(dtos)

        # All fields present
        for dto in result:
            assert dto.id is not None
            assert dto.title is not None
            assert dto.owner_id is not None
            # Implicit AutoLoad: owner resolved
            assert dto.owner is not None
            assert dto.owner.name in {"Alice", "Bob"}

    @pytest.mark.usefixtures("test_db")
    async def test_send_to_on_subset_field_with_resolver(self):
        """SubsetConfig send_to on a subset field (not extra) should work."""
        from sqlmodel import select

        from sqlmodel_graphql.context import Collector
        from sqlmodel_graphql.resolver import Resolver
        from sqlmodel_graphql.subset import SubsetConfig

        class TaskDTO(DefineSubset):
            __subset__ = SubsetConfig(
                kls=TestTask,
                fields=["id", "title"],
                send_to=[("title", "all_titles")],
            )

        class SprintDTO(DefineSubset):
            __subset__ = SubsetConfig(kls=TestSprint, fields=["id", "name"])
            tasks: list[TaskDTO] = []
            all_titles: list[str] = []

            def post_all_titles(self, collector=Collector("all_titles")):
                return collector.values()

        session_factory = get_test_session_factory()
        async with session_factory() as session:
            sprints = (await session.exec(select(TestSprint))).all()

        dtos = [SprintDTO(id=s.id, name=s.name) for s in sprints]
        result = await Resolver().resolve(dtos)

        # Collector should have collected task titles
        for sprint_dto in result:
            assert len(sprint_dto.all_titles) == len(sprint_dto.tasks)
            assert all(isinstance(t, str) for t in sprint_dto.all_titles)
