"""ER Diagram — visualize and document SQLModel entity relationships.

Generates Mermaid ER diagrams from SQLModel ORM metadata.
Uses the same relationship discovery logic as LoaderRegistry.

Usage:
    from sqlmodel_nexus import ErDiagram

    diagram = ErDiagram.from_sqlmodel(entities=[User, Post, Comment])
    print(diagram.to_mermaid())

    # Entity details
    for entity_info in diagram.entities:
        print(f"{entity_info.name}: {[r.name for r in entity_info.relationships]}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import RelationshipProperty
from sqlmodel import SQLModel


class RelationType(str, Enum):
    MANYTOONE = "MANYTOONE"
    ONETOMANY = "ONETOMANY"
    MANYTOMANY = "MANYTOMANY"


@dataclass
class RelationInfo:
    """A single relationship between two entities."""
    name: str  # relationship field name
    source: str  # source entity name
    target: str  # target entity name
    fk_field: str  # FK field name on source side
    relation_type: RelationType


@dataclass
class EntityInfo:
    """An entity with its fields and relationships."""
    name: str
    table_name: str
    fields: list[str]
    fk_fields: list[str]
    relationships: list[RelationInfo] = field(default_factory=list)


@dataclass
class ErDiagram:
    """ER Diagram constructed from SQLModel entity metadata.

    Create via ErDiagram.from_sqlmodel() and visualize via to_mermaid().
    """

    entities: list[EntityInfo]

    @classmethod
    def from_sqlmodel(cls, entities: list[type[SQLModel]]) -> ErDiagram:
        """Build an ER Diagram from SQLModel entity classes.

        Inspects SQLAlchemy ORM metadata to discover relationships,
        field names, and foreign keys.

        Args:
            entities: List of SQLModel entity classes (with table=True).

        Returns:
            ErDiagram with entity and relationship information.
        """
        entity_map: dict[type, EntityInfo] = {}
        entity_set = set(entities)

        # First pass: collect entity info
        for entity in entities:
            mapper = sa_inspect(entity)
            table_name = getattr(entity, "__tablename__", entity.__name__.lower())

            # Collect field names, separating FK fields
            all_fields = []
            fk_fields = []
            for fname, finfo in entity.model_fields.items():
                all_fields.append(fname)
                if _is_fk_field(finfo):
                    fk_fields.append(fname)

            # Remove relationship names from field list
            rel_names = set()
            if mapper and hasattr(mapper, "relationships"):
                rel_names = {r.key for r in mapper.relationships}

            scalar_fields = [f for f in all_fields if f not in rel_names]

            entity_info = EntityInfo(
                name=entity.__name__,
                table_name=table_name,
                fields=scalar_fields,
                fk_fields=fk_fields,
            )
            entity_map[entity] = entity_info

        # Second pass: discover relationships
        for entity in entities:
            mapper = sa_inspect(entity)
            if not mapper or not hasattr(mapper, "relationships"):
                continue

            for rel in mapper.relationships:
                # Only include relationships to entities in our set
                target_entity = rel.mapper.class_
                if target_entity not in entity_set:
                    continue

                direction = _get_relation_direction(rel)

                # Get FK field name
                fk_field = ""
                if rel.local_columns:
                    fk_field = list(rel.local_columns)[0].name

                entity_map[entity].relationships.append(
                    RelationInfo(
                        name=rel.key,
                        source=entity.__name__,
                        target=target_entity.__name__,
                        fk_field=fk_field,
                        relation_type=direction,
                    )
                )

        # Third pass: discover custom relationships from __relationships__
        from sqlmodel_nexus.relationship import get_custom_relationships

        for entity in entities:
            custom_rels = get_custom_relationships(entity)
            for crel in custom_rels:
                # Only include relationships to entities in our set
                if crel.target_entity not in entity_set:
                    continue

                direction = (
                    RelationType.ONETOMANY if crel.is_list else RelationType.MANYTOONE
                )

                entity_map[entity].relationships.append(
                    RelationInfo(
                        name=crel.name,
                        source=entity.__name__,
                        target=crel.target_entity.__name__,
                        fk_field=crel.fk,
                        relation_type=direction,
                    )
                )

        return cls(entities=list(entity_map.values()))

    def to_mermaid(self) -> str:
        """Generate a Mermaid ER diagram string.

        Returns:
            Mermaid erDiagram syntax string.
        """
        lines = ["erDiagram"]

        # Entity definitions
        for entity in self.entities:
            lines.append(f"    {entity.name} {{")
            for fname in entity.fields:
                lines.append(f"        {fname}")
            lines.append("    }")

        # Relationships
        seen_rels: set[tuple[str, str]] = set()
        for entity in self.entities:
            for rel in entity.relationships:
                # Avoid duplicate relationship lines
                pair = tuple(sorted([rel.source, rel.target]))
                rel_key = (pair, rel.name)
                if rel_key in seen_rels:
                    continue
                seen_rels.add(rel_key)

                if rel.relation_type == RelationType.ONETOMANY:
                    lines.append(
                        f"    {rel.source} ||--o{{ {rel.target} : {rel.name}"
                    )
                elif rel.relation_type == RelationType.MANYTOONE:
                    lines.append(
                        f"    {rel.target} ||--o{{ {rel.source} : {rel.name}"
                    )
                elif rel.relation_type == RelationType.MANYTOMANY:
                    lines.append(
                        f"    {rel.source} }}o--o{{ {rel.target} : {rel.name}"
                    )

        return "\n".join(lines)


def _is_fk_field(field_info: Any) -> bool:
    """Check if a FieldInfo represents a foreign key field."""
    if hasattr(field_info, "foreign_key") and isinstance(field_info.foreign_key, str):
        return True
    if hasattr(field_info, "metadata"):
        for meta in field_info.metadata:
            if hasattr(meta, "foreign_key") and isinstance(meta.foreign_key, str):
                return True
    return False


def _get_relation_direction(rel: RelationshipProperty) -> RelationType:
    """Determine the direction of a SQLAlchemy relationship."""
    if rel.direction.name == "MANYTOONE":
        return RelationType.MANYTOONE
    elif rel.direction.name == "ONETOMANY":
        return RelationType.ONETOMANY
    else:
        return RelationType.MANYTOMANY
