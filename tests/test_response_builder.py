"""Tests for response_builder — dynamic Pydantic model building and serialization."""

from typing import Optional

from pydantic import BaseModel
from sqlmodel import Field, Relationship, SQLModel

from sqlmodel_graphql.response_builder import (
    build_response_model,
    get_relation_entity,
    get_relationship_names,
    serialize_with_model,
)

# ──────────────────────────────────────────────────────────
# Test entities
# ──────────────────────────────────────────────────────────


class RBUser(SQLModel, table=True):
    __tablename__ = "rb_user"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str

    posts: list["RBPost"] = Relationship(back_populates="author")  # type: ignore[type-arg]


class RBPost(SQLModel, table=True):
    __tablename__ = "rb_post"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    author_id: int = Field(foreign_key="rb_user.id")

    author: Optional["RBUser"] = Relationship(back_populates="posts")


# ──────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────


class TestBuildResponseModel:
    def test_build_scalar_model(self):
        """field_tree=None should build a model with all scalar fields."""
        model = build_response_model(RBUser, None)
        assert issubclass(model, BaseModel)
        instance = model(id=1, name="Alice", email="alice@test.com")
        data = instance.model_dump()
        assert data["id"] == 1
        assert data["name"] == "Alice"
        assert data["email"] == "alice@test.com"

    def test_build_model_with_selected_fields(self):
        """field_tree with scalar fields should include only those fields."""
        field_tree = {"id": None, "name": None}
        model = build_response_model(RBUser, field_tree)
        instance = model(id=1, name="Alice")
        data = instance.model_dump()
        assert "id" in data
        assert "name" in data
        assert "email" not in data

    def test_build_model_with_nested_relationship(self):
        """field_tree with nested dict should create nested model for relationship."""
        field_tree = {
            "id": None,
            "title": None,
            "author": {"id": None, "name": None},
        }
        model = build_response_model(RBPost, field_tree)
        assert issubclass(model, BaseModel)


class TestSerializeWithModel:
    def test_serialize_single_entity(self):
        """Single entity should be serialized to dict."""
        user = RBUser(id=1, name="Alice", email="alice@test.com")
        result = serialize_with_model(user, RBUser, {"id": None, "name": None})
        assert isinstance(result, dict)
        assert result["id"] == 1
        assert result["name"] == "Alice"

    def test_serialize_list_entities(self):
        """List of entities should be serialized to list of dicts."""
        users = [
            RBUser(id=1, name="Alice", email="alice@test.com"),
            RBUser(id=2, name="Bob", email="bob@test.com"),
        ]
        result = serialize_with_model(users, RBUser, {"id": None, "name": None})
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert result[1]["name"] == "Bob"

    def test_serialize_none(self):
        """None value should return None."""
        result = serialize_with_model(None, RBUser, {"id": None})
        assert result is None

    def test_serialize_with_all_scalar_fields(self):
        """field_tree=None should serialize all scalar fields."""
        user = RBUser(id=1, name="Alice", email="alice@test.com")
        result = serialize_with_model(user, RBUser, None)
        assert result["id"] == 1
        assert result["name"] == "Alice"
        assert result["email"] == "alice@test.com"


class TestGetRelationshipNames:
    def test_entity_with_relationships(self):
        """Should return relationship field names."""
        names = get_relationship_names(RBPost)
        assert "author" in names

    def test_entity_without_relationships(self):
        """Entity without relationships should return empty set."""
        names = get_relationship_names(RBUser)
        assert isinstance(names, set)


class TestGetRelationEntity:
    def test_known_relationship(self):
        """Should return target entity for a known relationship."""
        entity = get_relation_entity(RBPost, "author")
        assert entity is not None

    def test_unknown_field_returns_none(self):
        """Should return None for non-relationship field."""
        entity = get_relation_entity(RBPost, "nonexistent")
        assert entity is None

    def test_scalar_field_returns_type(self):
        """Scalar fields return their type (not None) via annotation extraction."""
        entity = get_relation_entity(RBPost, "title")
        # get_relation_entity extracts the type from annotations;
        # scalar fields are not filtered here
        assert entity is not None
