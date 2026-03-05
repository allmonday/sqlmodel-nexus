"""Query builder for converting QueryMeta to SQLAlchemy query options."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import class_mapper, load_only, selectinload
from sqlmodel import select

if TYPE_CHECKING:
    from sqlmodel import SQLModel

    from sqlmodel_graphql.types import QueryMeta, RelationshipSelection


class QueryBuilder:
    """Builds optimized SQLAlchemy queries from QueryMeta."""

    def __init__(self, entity: type[SQLModel]):
        """Initialize the query builder.

        Args:
            entity: The SQLModel entity class to build queries for.
        """
        self.entity = entity

    def build(self, query_meta: QueryMeta | None = None) -> Any:
        """Build a SQLAlchemy select statement with optimized options.

        Args:
            query_meta: Query metadata containing field and relationship selections.
                       If None, returns a basic select without optimization.

        Returns:
            SQLAlchemy Select statement with appropriate options.
        """
        stmt = select(self.entity)

        if query_meta is None:
            return stmt

        options = self._build_options(query_meta)
        if options:
            stmt = stmt.options(*options)

        return stmt

    def _build_options(self, query_meta: QueryMeta) -> list[Any]:
        """Build SQLAlchemy options from QueryMeta."""
        options: list[Any] = []

        # Add field selection (load_only)
        if query_meta.fields:
            columns = [getattr(self.entity, f.name) for f in query_meta.fields]
            # Always include primary key
            pk_columns = self._get_primary_key_columns()
            for pk in pk_columns:
                if pk not in columns:
                    columns.insert(0, pk)
            options.append(load_only(*columns))

        # Add relationship loading
        for rel_name, rel_selection in query_meta.relationships.items():
            rel_option = self._build_relationship_option(rel_name, rel_selection)
            if rel_option:
                options.append(rel_option)

        return options

    def _build_relationship_option(
        self, rel_name: str, rel_selection: RelationshipSelection
    ) -> Any | None:
        """Build a selectinload option for a relationship."""
        try:
            rel_attr = getattr(self.entity, rel_name)
        except AttributeError:
            return None

        # Get the target entity class
        try:
            target_entity = rel_attr.property.mapper.class_
        except AttributeError:
            # Not a relationship attribute
            return None

        # Build nested options
        nested_options: list[Any] = []

        # Add field selection for the relationship
        if rel_selection.fields:
            columns = [getattr(target_entity, f.name) for f in rel_selection.fields]
            # Include primary key of target entity
            pk_columns = self._get_primary_key_columns(target_entity)
            for pk in pk_columns:
                if pk not in columns:
                    columns.insert(0, pk)
            nested_options.append(load_only(*columns))

        # Recursively handle nested relationships
        for nested_rel_name, nested_rel_selection in rel_selection.relationships.items():
            nested_option = self._build_nested_relationship_option(
                target_entity, nested_rel_name, nested_rel_selection
            )
            if nested_option:
                nested_options.append(nested_option)

        # Build the selectinload option
        loader = selectinload(rel_attr)
        if nested_options:
            loader = loader.options(*nested_options)

        return loader

    def _build_nested_relationship_option(
        self,
        parent_entity: type[SQLModel],
        rel_name: str,
        rel_selection: RelationshipSelection,
    ) -> Any | None:
        """Build a nested relationship option for multi-level relationships."""
        try:
            rel_attr = getattr(parent_entity, rel_name)
        except AttributeError:
            return None

        try:
            target_entity = rel_attr.property.mapper.class_
        except AttributeError:
            return None

        # Build nested options
        nested_options: list[Any] = []

        if rel_selection.fields:
            columns = [getattr(target_entity, f.name) for f in rel_selection.fields]
            pk_columns = self._get_primary_key_columns(target_entity)
            for pk in pk_columns:
                if pk not in columns:
                    columns.insert(0, pk)
            nested_options.append(load_only(*columns))

        # Handle deeper nesting
        for nested_rel_name, nested_rel_selection in rel_selection.relationships.items():
            deeper_option = self._build_nested_relationship_option(
                target_entity, nested_rel_name, nested_rel_selection
            )
            if deeper_option:
                nested_options.append(deeper_option)

        loader = selectinload(rel_attr)
        if nested_options:
            loader = loader.options(*nested_options)

        return loader

    def _get_primary_key_columns(
        self, entity: type[SQLModel] | None = None
    ) -> list[Any]:
        """Get primary key column(s) for an entity."""
        target = entity or self.entity
        pk_columns: list[Any] = []

        # Use SQLAlchemy mapper to get primary key columns
        try:
            mapper = class_mapper(target)
            for pk_column in mapper.primary_key:
                # Get the column name and find the corresponding model attribute
                pk_columns.append(getattr(target, pk_column.key))
        except Exception:
            # Fallback: try to find primary key from model_fields metadata
            for field_name, field_info in target.model_fields.items():
                # Check if this field has primary_key in json_schema_extra or other metadata
                json_schema_extra = field_info.json_schema_extra
                if json_schema_extra and isinstance(json_schema_extra, dict):
                    if json_schema_extra.get("primary_key"):
                        pk_columns.append(getattr(target, field_name))

        return pk_columns
