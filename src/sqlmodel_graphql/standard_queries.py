"""Standard query generators for SQLModel entities.

This module provides automatic generation of standard queries (by_id, by_filter)
for SQLModel entities.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import Field, create_model
from sqlmodel import SQLModel, select

from sqlmodel_graphql.decorator import query
from sqlmodel_graphql.types import QueryMeta


class AutoQueryConfig:
    """Configuration for auto-generated standard queries."""

    def __init__(
        self,
        session_factory,
        default_limit: int = 10,
        generate_by_id: bool = True,
        generate_by_filter: bool = True,
        enabled: bool = True,
    ):
        """Initialize the auto query configuration.

        Args:
            session_factory: Factory that creates async database session.
            default_limit: Default limit for by_filter queries.
            generate_by_id: Whether to generate by_id query.
            generate_by_filter: Whether to generate by_filter query.
            enabled: Whether standard queries are enabled.
        """
        self.session_factory = session_factory
        self.default_limit = default_limit
        self.generate_by_id = generate_by_id
        self.generate_by_filter = generate_by_filter
        self.enabled = enabled


def _create_by_id_query(entity: type[SQLModel], session_factory) -> Any:
    """Create by_id query method."""

    @query
    async def by_id(cls, id: int, query_meta: QueryMeta | None = None) -> Any:
        """Get entity by ID."""
        async with session_factory() as session:
            stmt = select(cls).where(cls.id == id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

    # Set return type annotation
    by_id.__annotations__["return"] = Optional[entity]

    return by_id


def _create_by_filter_query(
    entity: type[SQLModel],
    session_factory,
    default_limit: int,
    filter_input_type,
) -> Any:
    """Create by_filter query method."""

    @query
    async def by_filter(
        cls,
        filter: Any | None = None,
        limit: int = default_limit,
        query_meta: QueryMeta | None = None,
    ) -> Any:
        """Get entities by filter."""
        async with session_factory() as session:
            stmt = select(cls)
            if filter is not None:
                for field_name in filter_input_type.model_fields:
                    value = getattr(filter, field_name, None)
                    if value is not None:
                        stmt = stmt.where(getattr(cls, field_name) == value)
            stmt = stmt.limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    # Set return type annotation
    by_filter.__annotations__["return"] = list[entity]

    return by_filter


def add_standard_queries(entities: list[type[SQLModel]], config: AutoQueryConfig) -> None:
    """Add standard queries (by_id, by_filter) to entities.

    Args:
        entities: List of SQLModel entity classes.
        config: AutoQueryConfig.
    """
    if not config.enabled:
        return

    for entity in entities:
        # Create filter input type
        field_definitions: dict[str, tuple[type, Any]] = {}
        for field_name, field_info in entity.model_fields.items():
            if field_name.startswith("_") or field_name == "metadata":
                continue
            if field_name not in entity.__annotations__:
                continue
            original_type = field_info.annotation
            field_type = Optional[original_type]
            field_definitions[field_name] = (field_type, Field(default=None))

        # Create the filter input class
        class_name = f"{entity.__name__}FilterInput"
        filter_input_type = create_model(
            class_name,
            **{k: v for k, v in field_definitions.items()},
        )

        # Attach to entity for retrieval
        entity._filter_input_type = filter_input_type

        # Add by_id query if not exists
        if config.generate_by_id and not hasattr(entity, "by_id"):
            entity.by_id = _create_by_id_query(entity, config.session_factory)

        # Add by_filter query if not exists
        if config.generate_by_filter and not hasattr(entity, "by_filter"):
            by_filter_method = _create_by_filter_query(
                entity,
                config.session_factory,
                config.default_limit,
                filter_input_type,
            )
            # Attach to entity
            entity.by_filter = by_filter_method
            # Attach filter input type to the method for SDL generation
            entity.by_filter.__func__._filter_input_type = filter_input_type
