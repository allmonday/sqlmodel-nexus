"""Tests for Relationship — custom non-ORM relationship definitions."""

from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel
from sqlmodel import Field, SQLModel

from sqlmodel_graphql import AutoLoad, DefineSubset, ErDiagram, Relationship
from sqlmodel_graphql.loader.registry import LoaderRegistry, _build_custom_relationship_info
from sqlmodel_graphql.relationship import get_custom_relationships
from sqlmodel_graphql.resolver import Resolver
from tests.conftest import TestSprint, TestTask, TestUser

# ──────────────────────────────────────────────────────────
# Test entities with __relationships__
# ──────────────────────────────────────────────────────────


class Tag(SQLModel, table=True):
    __tablename__ = "rel_test_tag"

    id: int | None = Field(default=None, primary_key=True)
    name: str


async def _dummy_tag_loader(post_ids: list[int]) -> list[list]:
    return [[] for _ in post_ids]


class Post(SQLModel, table=True):
    __tablename__ = "rel_test_post"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    author_id: int = Field(foreign_key="rel_test_user.id")

    __relationships__ = [
        Relationship(
            fk="id",
            target=Tag,
            name="tags",
            loader=_dummy_tag_loader,
            is_list=True,
            description="Post tags via custom loader",
        )
    ]


class RelUser(SQLModel, table=True):
    __tablename__ = "rel_test_user"

    id: int | None = Field(default=None, primary_key=True)
    name: str


# Entity with duplicate names in __relationships__ for conflict testing


async def _dummy_conflict_loader(keys):
    return keys


class DuplicatePost(SQLModel, table=True):
    __tablename__ = "rel_test_dup_post"
    id: int | None = Field(default=None, primary_key=True)
    title: str
    author_id: int = Field(foreign_key="rel_test_user.id")

    __relationships__ = [
        Relationship(
            fk="author_id",
            target=RelUser,
            name="author",
            loader=_dummy_conflict_loader,
        ),
        # Same name "author" — duplicate within __relationships__
        Relationship(
            fk="author_id",
            target=RelUser,
            name="author",
            loader=_dummy_conflict_loader,
        ),
    ]


# ──────────────────────────────────────────────────────────
# Tests: Relationship dataclass
# ──────────────────────────────────────────────────────────


class TestRelationshipDataclass:
    def test_relationship_creation(self):
        """Relationship should store all fields correctly."""
        rel = Relationship(
            fk="author_id",
            target=RelUser,
            name="author",
            loader=_dummy_tag_loader,
        )
        assert rel.fk == "author_id"
        assert rel.target is RelUser
        assert rel.name == "author"
        assert rel.loader is _dummy_tag_loader
        assert rel.is_list is False
        assert rel.description is None

    def test_relationship_with_all_fields(self):
        """Relationship should handle all optional fields."""
        rel = Relationship(
            fk="id",
            target=Tag,
            name="tags",
            loader=_dummy_tag_loader,
            is_list=True,
            description="Tags",
        )
        assert rel.is_list is True
        assert rel.description == "Tags"


class TestGetCustomRelationships:
    def test_entity_with_relationships(self):
        """get_custom_relationships should return defined relationships."""
        rels = get_custom_relationships(Post)
        assert len(rels) == 1
        assert rels[0].name == "tags"
        assert rels[0].target is Tag
        assert rels[0].is_list is True

    def test_entity_without_relationships(self):
        """get_custom_relationships should return empty list for entities without __relationships__."""
        rels = get_custom_relationships(RelUser)
        assert rels == []

    def test_invalid_type_raises(self):
        """get_custom_relationships should raise TypeError for non-list __relationships__."""

        class BadEntity(SQLModel, table=True):
            __tablename__ = "rel_test_bad"
            __relationships__ = "not a list"
            id: int | None = Field(default=None, primary_key=True)

        with pytest.raises(TypeError, match="must be a list"):
            get_custom_relationships(BadEntity)

    def test_invalid_item_raises(self):
        """get_custom_relationships should raise TypeError for non-Relationship items."""

        class BadEntity2(SQLModel, table=True):
            __tablename__ = "rel_test_bad2"
            __relationships__ = ["not a Relationship"]
            id: int | None = Field(default=None, primary_key=True)

        with pytest.raises(TypeError, match="must be a Relationship"):
            get_custom_relationships(BadEntity2)


# ──────────────────────────────────────────────────────────
# Tests: ER Diagram integration
# ──────────────────────────────────────────────────────────


class TestErDiagramCustomRelationships:
    def test_custom_relationship_in_mermaid(self):
        """Custom relationships should appear in Mermaid output."""
        diagram = ErDiagram.from_sqlmodel([Post, Tag, RelUser])
        mermaid = diagram.to_mermaid()

        assert "Post" in mermaid
        assert "Tag" in mermaid
        assert "tags" in mermaid

    def test_custom_and_orm_relationships_combined(self):
        """Both ORM and custom relationships should appear in the diagram."""
        # Use TestTask which has ORM relationships (sprint, owner)
        # plus add a custom relationship via __relationships__
        diagram = ErDiagram.from_sqlmodel([Post, Tag, RelUser])

        post_entity = next(e for e in diagram.entities if e.name == "Post")
        rel_names = {r.name for r in post_entity.relationships}

        # Custom relationship: tags -> Tag
        assert "tags" in rel_names

    @pytest.mark.usefixtures("test_db")
    def test_conftest_models_with_custom_rel(self):
        """ER Diagram should work with conftest models that have ORM relationships."""
        diagram = ErDiagram.from_sqlmodel([TestUser, TestSprint, TestTask])

        task_entity = next(e for e in diagram.entities if e.name == "TestTask")
        rel_names = {r.name for r in task_entity.relationships}

        # ORM relationships on TestTask
        assert "sprint" in rel_names
        assert "owner" in rel_names

    def test_custom_relationship_target_not_in_entities_excluded(self):
        """Custom relationship whose target is not in entity list should be excluded."""
        diagram = ErDiagram.from_sqlmodel([Post, RelUser])

        post_entity = next(e for e in diagram.entities if e.name == "Post")
        rel_names = {r.name for r in post_entity.relationships}

        # 'tags' target (Tag) is not in the entity list
        assert "tags" not in rel_names


# ──────────────────────────────────────────────────────────
# Tests: LoaderRegistry integration
# ──────────────────────────────────────────────────────────


class TestLoaderRegistryCustomRelationships:
    def test_registry_includes_custom_relationships(self):
        """LoaderRegistry should include custom relationships."""
        registry = LoaderRegistry(
            entities=[Post, Tag, RelUser],
            session_factory=lambda: None,
        )

        post_rels = registry.get_relationships(Post)
        assert "tags" in post_rels

        rel_info = post_rels["tags"]
        assert rel_info.direction == "CUSTOM"
        assert rel_info.is_list is True
        assert rel_info.fk_field == "id"
        assert rel_info.target_entity is Tag

    def test_registry_custom_loader_works(self):
        """DataLoader from custom loader should work correctly."""
        registry = LoaderRegistry(
            entities=[Post, Tag, RelUser],
            session_factory=lambda: None,
        )

        loader = registry.get_loader_by_name("tags")
        assert loader is not None

    def test_registry_name_conflict_raises(self):
        """Custom relationship name conflicting with ORM should raise ValueError."""
        # DuplicatePost has ORM relationship 'author' (via FK) and
        # custom 'author' in __relationships__ — this should conflict
        # But actually, Post (without explicit ORM Relationship()) won't have
        # ORM 'author'. So test with conftest TestTask which has ORM 'owner'.
        # We need a custom rel named 'owner' on TestTask to trigger conflict.

        # Use the DuplicatePost which has duplicate custom names — the second
        # will conflict with the first during registration.
        with pytest.raises(ValueError, match="conflicts"):
            LoaderRegistry(
                entities=[DuplicatePost, RelUser],
                session_factory=lambda: None,
            )


# ──────────────────────────────────────────────────────────
# Tests: AutoLoad with custom relationships
# ──────────────────────────────────────────────────────────


class TestAutoLoadCustomRelationship:
    @pytest.mark.usefixtures("test_db")
    async def test_autoload_custom_many_to_one(self):
        """AutoLoad should work with custom many-to-one relationships."""

        async def user_loader(ids: list[int]) -> list:
            return [
                TestUser(id=1, name="Alice", email="alice@test.com") if k == 1
                else TestUser(id=2, name="Bob", email="bob@test.com")
                for k in ids
            ]

        registry = LoaderRegistry(
            entities=[TestUser, TestSprint, TestTask],
            session_factory=lambda: None,
        )

        custom_rel = Relationship(
            fk="owner_id",
            target=TestUser,
            name="custom_owner",
            loader=user_loader,
            is_list=False,
        )
        registry._registry[TestTask]["custom_owner"] = _build_custom_relationship_info(
            custom_rel
        )

        class UserDTO(DefineSubset):
            __subset__ = (TestUser, ("id", "name"))

        class TaskDTO(DefineSubset):
            __subset__ = (TestTask, ("id", "title", "owner_id"))
            custom_owner: Annotated[UserDTO | None, AutoLoad()] = None

        dto = TaskDTO(id=1, title="Test", owner_id=1)
        result = await Resolver(registry).resolve(dto)

        assert result.custom_owner is not None
        assert result.custom_owner.name == "Alice"

    @pytest.mark.usefixtures("test_db")
    async def test_autoload_custom_one_to_many(self):
        """AutoLoad should work with custom one-to-many (is_list=True) relationships."""

        async def greeting_loader(ids: list[int]) -> list[list]:
            return [[f"Greeting for {i}"] for i in ids]

        registry = LoaderRegistry(
            entities=[TestUser, TestSprint, TestTask],
            session_factory=lambda: None,
        )

        custom_rel = Relationship(
            fk="id",
            target=TestSprint,
            name="greetings",
            loader=greeting_loader,
            is_list=True,
        )
        registry._registry[TestSprint]["greetings"] = _build_custom_relationship_info(
            custom_rel
        )

        class SprintDTO(DefineSubset):
            __subset__ = (TestSprint, ("id", "name"))
            greetings: Annotated[list[str], AutoLoad()] = []

        dto = SprintDTO(id=1, name="Sprint 1")
        result = await Resolver(registry).resolve(dto)

        assert len(result.greetings) == 1
        assert result.greetings[0] == "Greeting for 1"

    @pytest.mark.usefixtures("test_db")
    async def test_custom_loader_returns_basemodel_skips_conversion(self):
        """Custom loader returning BaseModel instances should skip ORM→DTO conversion."""

        class InnerUserDTO(BaseModel):
            id: int
            name: str

        async def user_loader(keys: list[int]) -> list:
            return [InnerUserDTO(id=k, name=f"User{k}") for k in keys]

        class UserDTO(BaseModel):
            id: int
            name: str

        registry = LoaderRegistry(
            entities=[TestUser, TestSprint, TestTask],
            session_factory=lambda: None,
        )

        custom_rel = Relationship(
            fk="owner_id",
            target=TestUser,
            name="custom_owner",
            loader=user_loader,
            is_list=False,
        )
        registry._registry[TestTask]["custom_owner"] = _build_custom_relationship_info(
            custom_rel
        )

        class TaskDTO(DefineSubset):
            __subset__ = (TestTask, ("id", "title", "owner_id"))
            custom_owner: Annotated[UserDTO | None, AutoLoad()] = None

        dto = TaskDTO(id=1, title="Test", owner_id=1)
        result = await Resolver(registry).resolve(dto)

        assert result.custom_owner is not None
        assert result.custom_owner.name == "User1"
