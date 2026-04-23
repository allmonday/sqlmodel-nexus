"""Relationship registry - inspects ORM metadata and creates DataLoaders.

Adapted from pydantic-resolve's integration.sqlalchemy.inspector module.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aiodataloader import DataLoader
from sqlmodel import SQLModel

from sqlmodel_graphql.loader.factories import (
    create_many_to_many_loader,
    create_many_to_one_loader,
    create_one_to_many_loader,
    create_page_many_to_many_loader,
    create_page_one_to_many_loader,
)

logger = logging.getLogger(__name__)


@dataclass
class RelationshipInfo:
    """Metadata for a single ORM relationship, including its DataLoader."""

    name: str  # relationship field name on the entity
    direction: str  # MANYTOONE | ONETOMANY | MANYTOMANY
    fk_field: str  # FK field on the *source* entity used as loader key
    target_entity: type[SQLModel]  # target entity class
    is_list: bool  # True for one-to-many / many-to-many lists
    loader: type[DataLoader]  # regular DataLoader class
    page_loader: type[DataLoader] | None = None  # paginated loader (list only)
    sort_field: str | None = None  # sort column for pagination
    default_page_size: int = 20
    max_page_size: int = 100


def _expect_single_pair(pairs: Any, message: str) -> tuple[Any, Any]:
    pair_list = list(pairs)
    if len(pair_list) != 1:
        raise NotImplementedError(message)
    return pair_list[0]


def _extract_sort_field(order_by: Any) -> str:
    """Extract column name from a SQLAlchemy order_by clause."""
    if isinstance(order_by, (list, tuple)):
        if len(order_by) == 0:
            raise ValueError("order_by cannot be empty")
        if len(order_by) > 1:
            raise ValueError(
                f"Only single-column sorting is supported, got {len(order_by)} columns"
            )
        order_by = order_by[0]

    if hasattr(order_by, "key"):
        return order_by.key

    raise ValueError(
        f"Unable to extract sort field from order_by clause: {order_by}. "
        f"Please use a simple column reference like Post.id"
    )


def _inspect_relationships(
    entity_kls: type[SQLModel],
    all_entities: set[type[SQLModel]],
    session_factory: Callable,
) -> list[RelationshipInfo]:
    """Inspect a single entity's ORM relationships and create loaders."""
    from sqlalchemy import inspect
    from sqlalchemy.orm import MANYTOMANY, MANYTOONE, ONETOMANY

    try:
        mapper = inspect(entity_kls)
    except Exception:
        # Not a mapped entity (no table=True)
        return []

    # Only process entities with actual table mappings
    if not hasattr(mapper, "relationships"):
        return []

    results: list[RelationshipInfo] = []

    for rel in mapper.relationships:
        target_entity = rel.mapper.class_

        # Only process relationships to known entities
        if target_entity not in all_entities:
            logger.debug(
                "Skipping %s.%s: target %s not in entity list",
                entity_kls.__name__,
                rel.key,
                target_entity.__name__,
            )
            continue

        direction = rel.direction
        rel_name = rel.key

        if direction is MANYTOONE:
            local_col, remote_col = _expect_single_pair(
                rel.local_remote_pairs,
                f"Composite FK not supported for MANYTOONE: {entity_kls.__name__}.{rel_name}",
            )
            fk_field = local_col.key
            loader = create_many_to_one_loader(
                source_kls=entity_kls,
                rel_name=rel_name,
                target_kls=target_entity,
                target_remote_col_name=remote_col.key,
                session_factory=session_factory,
            )
            results.append(
                RelationshipInfo(
                    name=rel_name,
                    direction="MANYTOONE",
                    fk_field=fk_field,
                    target_entity=target_entity,
                    is_list=False,
                    loader=loader,
                )
            )

        elif direction is ONETOMANY:
            local_col, remote_col = _expect_single_pair(
                rel.local_remote_pairs,
                f"Composite FK not supported for ONETOMANY: {entity_kls.__name__}.{rel_name}",
            )
            fk_field = local_col.key

            if rel.uselist is False:
                # Reverse one-to-one (treated as scalar)
                from sqlmodel_graphql.loader.factories import (
                    create_many_to_one_loader as _m2o,
                )

                loader = _m2o(
                    source_kls=entity_kls,
                    rel_name=rel_name,
                    target_kls=target_entity,
                    target_remote_col_name=remote_col.key,
                    session_factory=session_factory,
                )
                results.append(
                    RelationshipInfo(
                        name=rel_name,
                        direction="ONETOMANY_SCALAR",
                        fk_field=fk_field,
                        target_entity=target_entity,
                        is_list=False,
                        loader=loader,
                    )
                )
            else:
                # List relationship — create regular + optional paginated loader
                sort_field = None
                page_loader = None

                order_by = rel.order_by
                if order_by and order_by is not False:
                    sort_field = _extract_sort_field(order_by)
                    target_mapper = inspect(target_entity)
                    pk_col_name = target_mapper.primary_key[0].name

                    page_loader = create_page_one_to_many_loader(
                        source_kls=entity_kls,
                        rel_name=rel_name,
                        target_kls=target_entity,
                        target_fk_col_name=remote_col.key,
                        sort_field=sort_field,
                        pk_col_name=pk_col_name,
                        session_factory=session_factory,
                    )

                loader = create_one_to_many_loader(
                    source_kls=entity_kls,
                    rel_name=rel_name,
                    target_kls=target_entity,
                    target_fk_col_name=remote_col.key,
                    session_factory=session_factory,
                )

                results.append(
                    RelationshipInfo(
                        name=rel_name,
                        direction="ONETOMANY",
                        fk_field=fk_field,
                        target_entity=target_entity,
                        is_list=True,
                        loader=loader,
                        page_loader=page_loader,
                        sort_field=sort_field,
                    )
                )

        elif direction is MANYTOMANY:
            secondary = rel.secondary
            if secondary is None:
                raise NotImplementedError(
                    f"MANYTOMANY without secondary table: {entity_kls.__name__}.{rel_name}"
                )

            source_col, secondary_local_col = _expect_single_pair(
                rel.synchronize_pairs,
                f"Composite source pair not supported: {entity_kls.__name__}.{rel_name}",
            )
            target_col, secondary_remote_col = _expect_single_pair(
                rel.secondary_synchronize_pairs,
                f"Composite target pair not supported: {entity_kls.__name__}.{rel_name}",
            )
            fk_field = source_col.key

            sort_field = None
            page_loader = None

            order_by = rel.order_by
            if order_by and order_by is not False:
                sort_field = _extract_sort_field(order_by)
                target_mapper = inspect(target_entity)
                pk_col_name = target_mapper.primary_key[0].name

                page_loader = create_page_many_to_many_loader(
                    source_kls=entity_kls,
                    rel_name=rel_name,
                    target_kls=target_entity,
                    secondary_table=secondary,
                    secondary_local_col_name=secondary_local_col.key,
                    secondary_remote_col_name=secondary_remote_col.key,
                    target_match_col_name=target_col.key,
                    sort_field=sort_field,
                    pk_col_name=pk_col_name,
                    session_factory=session_factory,
                )

            loader = create_many_to_many_loader(
                source_kls=entity_kls,
                rel_name=rel_name,
                target_kls=target_entity,
                secondary_table=secondary,
                secondary_local_col_name=secondary_local_col.key,
                secondary_remote_col_name=secondary_remote_col.key,
                target_match_col_name=target_col.key,
                session_factory=session_factory,
            )

            results.append(
                RelationshipInfo(
                    name=rel_name,
                    direction="MANYTOMANY",
                    fk_field=fk_field,
                    target_entity=target_entity,
                    is_list=True,
                    loader=loader,
                    page_loader=page_loader,
                    sort_field=sort_field,
                )
            )

    return results


class LoaderRegistry:
    """Registry of DataLoader instances keyed by (entity, relationship_name).

    Inspects SQLModel ORM metadata to auto-discover relationships
    and create the appropriate DataLoaders.
    """

    def __init__(
        self,
        entities: list[type[SQLModel]],
        session_factory: Callable,
        enable_pagination: bool = False,
    ):
        self._session_factory = session_factory
        self._enable_pagination = enable_pagination
        # entity -> {rel_name -> RelationshipInfo}
        self._registry: dict[type[SQLModel], dict[str, RelationshipInfo]] = {}
        # Cache of instantiated loaders: loader_cls -> instance
        self._loader_instances: dict[type[DataLoader], DataLoader] = {}

        all_entities = set(entities)
        for entity in entities:
            rels = _inspect_relationships(entity, all_entities, session_factory)
            self._registry[entity] = {r.name: r for r in rels}

        if enable_pagination:
            self._validate_pagination()

    def _validate_pagination(self) -> None:
        """Validate all list relationships have page_loader (order_by configured)."""
        errors = []
        for entity_kls, rels in self._registry.items():
            for rel in rels.values():
                if rel.is_list and rel.page_loader is None:
                    errors.append(
                        f"  {entity_kls.__name__}.{rel.name} — no order_by configured"
                    )
        if errors:
            raise ValueError(
                "enable_pagination is True but the following list "
                "relationships lack order_by:\n"
                + "\n".join(errors)
                + "\n\nSet order_by on the SQLModel Relationship to enable pagination."
            )

    def get_relationships(self, entity: type[SQLModel]) -> dict[str, RelationshipInfo]:
        """Get all registered relationships for an entity."""
        return self._registry.get(entity, {})

    def get_relationship(
        self, entity: type[SQLModel], name: str
    ) -> RelationshipInfo | None:
        """Get a specific relationship by entity and name."""
        rels = self._registry.get(entity, {})
        return rels.get(name)

    def get_loader(self, loader_cls: type[DataLoader]) -> DataLoader:
        """Get or create a DataLoader instance (cached per request)."""
        if loader_cls not in self._loader_instances:
            self._loader_instances[loader_cls] = loader_cls()
        return self._loader_instances[loader_cls]

    def clear_cache(self) -> None:
        """Clear cached loader instances (call at start of each request)."""
        self._loader_instances.clear()
