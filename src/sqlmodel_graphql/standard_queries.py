"""Standard query generators for SQLModel entities.

This module provides automatic generation of standard queries (by_id, by_filter)
for SQLModel entities.
"""

from __future__ import annotations

import inspect
import types
from typing import Any, Union, get_args, get_origin

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


async def _create_session_context(session_factory: Any) -> Any:
    """Create a session context, supporting sync and async factories."""
    session_context = session_factory()
    if inspect.isawaitable(session_context):
        session_context = await session_context
    return session_context


def _unwrap_optional_type(annotation: Any) -> Any:
    """Unwrap Optional[T] to T."""
    origin = get_origin(annotation)
    if origin in (types.UnionType, Union):
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _get_primary_key_fields(entity: type[SQLModel]) -> list[tuple[str, Any]]:
    """Get primary key fields from an entity."""
    primary_keys: list[tuple[str, Any]] = []

    for field_name, field_info in entity.model_fields.items():
        # First check: is it 'id'?
        if field_name == 'id':
            primary_keys.append((field_name, _unwrap_optional_type(field_info.annotation)))
            continue

        # Second check: see if it has primary_key=True
        has_primary_key = False
        has_foreign_key = False

        # Try various ways to detect primary key
        if hasattr(field_info, 'primary_key'):
            if field_info.primary_key is True:
                has_primary_key = True

        # Also check metadata (FieldInfoMetadata)
        if not has_primary_key and hasattr(field_info, 'metadata'):
            for meta in field_info.metadata:
                if hasattr(meta, 'primary_key') and meta.primary_key is True:
                    has_primary_key = True
                    break

        # Check for foreign key - only actual string values count
        if hasattr(field_info, 'foreign_key') and isinstance(field_info.foreign_key, str):
            has_foreign_key = True

        # Also check metadata for foreign key
        if not has_foreign_key and hasattr(field_info, 'metadata'):
            for meta in field_info.metadata:
                if hasattr(meta, 'foreign_key') and isinstance(meta.foreign_key, str):
                    has_foreign_key = True
                    break

        if has_primary_key and not has_foreign_key:
            primary_keys.append((field_name, _unwrap_optional_type(field_info.annotation)))

    return primary_keys


def _create_filter_input_type(entity: type[SQLModel]) -> type:
    """Create a filter input type from entity fields."""
    field_definitions: dict[str, tuple[type, Any]] = {}

    for field_name, field_info in entity.model_fields.items():
        if field_name.startswith("_") or field_name == "metadata":
            continue

        original_type = field_info.annotation
        field_type = original_type | None
        field_definitions[field_name] = (field_type, Field(default=None))

    return create_model(f"{entity.__name__}FilterInput", **field_definitions)


def _create_by_id_query(entity: type[SQLModel], session_factory) -> Any:
    """Create by_id query method."""

    primary_keys = _get_primary_key_fields(entity)
    if len(primary_keys) != 1:
        return None

    primary_key_name, primary_key_type = primary_keys[0]

    @query
    async def by_id(
        cls,
        query_meta: QueryMeta | None = None,
        **kwargs: Any,
    ) -> Any:
        """Get entity by ID."""
        if primary_key_name not in kwargs:
            msg = f"Missing required primary key argument: {primary_key_name}"
            raise TypeError(msg)

        session_context = await _create_session_context(session_factory)
        async with session_context as session:
            stmt = select(cls).where(
                getattr(cls, primary_key_name) == kwargs[primary_key_name]
            )
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

    func = by_id.__func__ if hasattr(by_id, "__func__") else by_id
    func.__annotations__[primary_key_name] = primary_key_type
    by_id.__annotations__["return"] = entity | None
    func.__signature__ = inspect.Signature(
        parameters=[
            inspect.Parameter(
                "cls",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ),
            inspect.Parameter(
                primary_key_name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=primary_key_type,
            ),
            inspect.Parameter(
                "query_meta",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=None,
                annotation=QueryMeta | None,
            ),
        ],
        return_annotation=entity | None,
    )

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
        session_context = await _create_session_context(session_factory)
        async with session_context as session:
            stmt = select(cls)
            if filter is not None:
                if hasattr(filter, "model_dump"):
                    filter_values = filter.model_dump(exclude_none=True)
                elif isinstance(filter, dict):
                    filter_values = {
                        field_name: value
                        for field_name, value in filter.items()
                        if value is not None
                    }
                else:
                    filter_values = {
                        field_name: getattr(filter, field_name, None)
                        for field_name in filter_input_type.model_fields
                        if getattr(filter, field_name, None) is not None
                    }

                for field_name, value in filter_values.items():
                    if value is not None:
                        stmt = stmt.where(getattr(cls, field_name) == value)
            stmt = stmt.limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    func = by_filter.__func__ if hasattr(by_filter, "__func__") else by_filter
    func.__annotations__["filter"] = filter_input_type
    by_filter.__annotations__["return"] = list[entity]
    func._filter_input_type = filter_input_type

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
        # Add by_id query if not exists
        if config.generate_by_id and not hasattr(entity, "by_id"):
            by_id_method = _create_by_id_query(entity, config.session_factory)
            if by_id_method is not None:
                entity.by_id = by_id_method

        # Add by_filter query if not exists
        if config.generate_by_filter and not hasattr(entity, "by_filter"):
            filter_input_type = _create_filter_input_type(entity)
            by_filter_method = _create_by_filter_query(
                entity,
                config.session_factory,
                config.default_limit,
                filter_input_type,
            )
            entity.by_filter = by_filter_method
