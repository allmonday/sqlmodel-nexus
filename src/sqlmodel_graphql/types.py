"""Type definitions for sqlmodel-graphql."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FieldSelection:
    """Represents a selected field in a GraphQL query.

    Attributes:
        name: The field name as defined in the SQLModel.
        alias: Optional GraphQL alias for the field.
    """

    name: str
    alias: str | None = None


@dataclass
class RelationshipSelection:
    """Represents a selected relationship field in a GraphQL query.

    Attributes:
        name: The relationship attribute name on the SQLModel.
        fields: List of scalar fields to select from the related entity.
        relationships: Nested relationship selections.
    """

    name: str = ""
    fields: list[FieldSelection] = field(default_factory=list)
    relationships: dict[str, RelationshipSelection] = field(default_factory=dict)


@dataclass
class QueryMeta:
    """Metadata extracted from a GraphQL query selection set.

    This is used to optimize SQLAlchemy queries by:
    - Only loading requested fields (via load_only)
    - Eager loading requested relationships (via selectinload)

    Attributes:
        fields: List of scalar fields to select.
        relationships: Dictionary of relationship selections.
    """

    fields: list[FieldSelection] = field(default_factory=list)
    relationships: dict[str, RelationshipSelection] = field(default_factory=dict)

    def get_field_names(self) -> list[str]:
        """Get list of field names without aliases."""
        return [f.name for f in self.fields]
