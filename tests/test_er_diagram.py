"""Tests for ER Diagram — visualization and relationship documentation."""

from typing import Optional

import pytest
from sqlmodel import Field, Relationship, SQLModel

from sqlmodel_nexus.er_diagram import ErDiagram, RelationType
from tests.conftest import FixtureSprint, FixtureTask, FixtureUser

# ──────────────────────────────────────────────────────────
# Simple test entities (no DB needed)
# ──────────────────────────────────────────────────────────

class SimpleBase(SQLModel):
    pass


class SimpleUser(SimpleBase, table=True):
    __tablename__ = "er_test_user"

    id: int | None = Field(default=None, primary_key=True)
    name: str


class SimplePost(SimpleBase, table=True):
    __tablename__ = "er_test_post"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    author_id: int = Field(foreign_key="er_test_user.id")

    author: Optional["SimpleUser"] = Relationship()


# ──────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────

class TestErDiagram:
    def test_from_sqlmodel_discovers_entities(self):
        """ErDiagram should discover all entities and their fields."""

        diagram = ErDiagram.from_sqlmodel([SimpleUser, SimplePost])

        entity_names = {e.name for e in diagram.entities}
        assert "SimpleUser" in entity_names
        assert "SimplePost" in entity_names

    def test_from_sqlmodel_discovers_relationships(self):
        """ErDiagram should discover relationships between entities."""

        diagram = ErDiagram.from_sqlmodel([SimpleUser, SimplePost])

        post_entity = next(e for e in diagram.entities if e.name == "SimplePost")
        assert len(post_entity.relationships) == 1
        rel = post_entity.relationships[0]
        assert rel.name == "author"
        assert rel.target == "SimpleUser"
        assert rel.relation_type == RelationType.MANYTOONE

    def test_from_sqlmodel_separates_fk_fields(self):
        """ErDiagram should identify FK fields separately."""

        diagram = ErDiagram.from_sqlmodel([SimpleUser, SimplePost])

        post_entity = next(e for e in diagram.entities if e.name == "SimplePost")
        assert "author_id" in post_entity.fk_fields

    def test_to_mermaid_generates_valid_syntax(self):
        """to_mermaid should generate valid Mermaid erDiagram syntax."""

        diagram = ErDiagram.from_sqlmodel([SimpleUser, SimplePost])
        mermaid = diagram.to_mermaid()

        assert mermaid.startswith("erDiagram")
        assert "SimpleUser" in mermaid
        assert "SimplePost" in mermaid

    @pytest.mark.usefixtures("test_db")
    def test_from_sqlmodel_with_three_entities(self):
        """ErDiagram should handle the full test model (User, Sprint, Task)."""

        diagram = ErDiagram.from_sqlmodel([FixtureUser, FixtureSprint, FixtureTask])

        entity_names = {e.name for e in diagram.entities}
        assert entity_names == {"FixtureUser", "FixtureSprint", "FixtureTask"}

        task_entity = next(e for e in diagram.entities if e.name == "FixtureTask")
        rel_names = {r.name for r in task_entity.relationships}
        assert "sprint" in rel_names
        assert "owner" in rel_names

    @pytest.mark.usefixtures("test_db")
    def test_to_mermaid_with_complex_model(self):
        """to_mermaid should handle complex multi-entity diagrams."""

        diagram = ErDiagram.from_sqlmodel([FixtureUser, FixtureSprint, FixtureTask])
        mermaid = diagram.to_mermaid()

        assert "erDiagram" in mermaid
        assert "FixtureUser" in mermaid
        assert "FixtureSprint" in mermaid
        assert "FixtureTask" in mermaid
        # Should have relationship lines
        assert "||--o{" in mermaid or "}o--o{" in mermaid

    def test_entity_without_relationships(self):
        """ErDiagram should handle entities with no relationships."""

        diagram = ErDiagram.from_sqlmodel([SimpleUser])

        assert len(diagram.entities) == 1
        assert len(diagram.entities[0].relationships) == 0

    def test_empty_entities(self):
        """ErDiagram should handle empty entity list."""

        diagram = ErDiagram.from_sqlmodel([])

        assert len(diagram.entities) == 0
        assert diagram.to_mermaid() == "erDiagram"
