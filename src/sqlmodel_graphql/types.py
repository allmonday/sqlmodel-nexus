"""Type definitions for sqlmodel-graphql."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlmodel import SQLModel

from sqlalchemy.orm import class_mapper, load_only, selectinload


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

    def get_field_names(self) -> list[str]:
        """Get list of field names without aliases."""
        return [f.name for f in self.fields]


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

    def to_options(self, entity: type[SQLModel]) -> list[Any]:
        """Convert QueryMeta to SQLAlchemy query options.

        Args:
            entity: The SQLModel entity class to generate options for.

        Returns:
            List of SQLAlchemy options (load_only, selectinload, etc.)

        Example:
            stmt = select(User).options(*query_meta.to_options(User))
        """
        options: list[Any] = []

        # Add load_only for field selection
        if self.fields:
            columns = []
            for f in self.fields:
                try:
                    columns.append(getattr(entity, f.name))
                except AttributeError:
                    # Field might not exist in this entity, skip it
                    pass
            # Always include primary key
            pk_columns = self._get_primary_key_columns(entity)
            for pk in pk_columns:
                if pk not in columns:
                    columns.insert(0, pk)
            options.append(load_only(*columns))

        # Add selectinload for relationships
        for rel_name, rel_selection in self.relationships.items():
            rel_option = self._build_relationship_option(entity, rel_name, rel_selection)
            if rel_option:
                options.append(rel_option)

        return options

    def _build_relationship_option(
        self,
        entity: type[SQLModel],
        rel_name: str,
        rel_selection: RelationshipSelection,
    ) -> Any | None:
        """Build a selectinload option for a relationship."""
        try:
            rel_attr = getattr(entity, rel_name)
        except AttributeError:
            return None

        try:
            target_entity = rel_attr.property.mapper.class_
        except AttributeError:
            return None

        nested_options: list[Any] = []

        if rel_selection.fields:
            columns = [getattr(target_entity, f.name) for f in rel_selection.fields]
            pk_columns = self._get_primary_key_columns(target_entity)
            for pk in pk_columns:
                if pk not in columns:
                    columns.insert(0, pk)
            nested_options.append(load_only(*columns))

        # Recursively handle nested relationships
        for nested_rel_name, nested_rel_selection in rel_selection.relationships.items():
            nested_option = self._build_relationship_option(
                target_entity, nested_rel_name, nested_rel_selection
            )
            if nested_option:
                nested_options.append(nested_option)

        loader = selectinload(rel_attr)
        if nested_options:
            loader = loader.options(*nested_options)

        return loader

    @staticmethod
    def _get_primary_key_columns(entity: type[SQLModel]) -> list[Any]:
        """Get primary key column(s) for an entity."""
        pk_columns: list[Any] = []
        try:
            mapper = class_mapper(entity)
            for pk_column in mapper.primary_key:
                pk_columns.append(getattr(entity, pk_column.key))
        except Exception:
            pass
        return pk_columns
