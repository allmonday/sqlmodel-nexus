"""DataLoader factory functions for SQLModel relationships.

Adapted from pydantic-resolve's integration.sqlalchemy.loader module.
Simplified for sqlmodel-graphql where SQLModel serves as both ORM and DTO.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from aiodataloader import DataLoader

if TYPE_CHECKING:
    from sqlmodel_graphql.loader.pagination import PageArgs


def _normalize_identifier(value: str) -> str:
    """Convert arbitrary names to valid class-name fragments."""
    normalized = re.sub(r"[^0-9a-zA-Z_]", "_", value)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "anonymous"


def _build_loader_identity(source_kls: type, rel_name: str, suffix: str) -> str:
    source_name = _normalize_identifier(getattr(source_kls, "__name__", "source"))
    rel_part = _normalize_identifier(rel_name)
    return f"{source_name}_{rel_part}_{suffix}"


def _finalize_loader_class(cls: type[DataLoader], identity: str) -> type[DataLoader]:
    class_name = f"SG_{identity}"
    cls.__name__ = class_name
    cls.__qualname__ = class_name
    cls.__module__ = __name__
    return cls


def _row_get(row: Any, key: str) -> Any:
    mapping = getattr(row, "_mapping", None)
    if mapping is not None and key in mapping:
        return mapping[key]
    return getattr(row, key)


def _apply_filters(stmt: Any, filters: list[Any] | None) -> Any:
    if filters:
        return stmt.where(*filters)
    return stmt


def _apply_load_only(stmt: Any, target_kls: type, fields: list[str]) -> Any:
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy.orm import load_only

    mapper = sa_inspect(target_kls)
    rel_keys = {rel.key for rel in mapper.relationships}
    attrs = [
        getattr(target_kls, field)
        for field in fields
        if hasattr(target_kls, field) and field not in rel_keys
    ]
    if attrs:
        return stmt.options(load_only(*attrs))
    return stmt


# ---------------------------------------------------------------------------
# Many-to-one loader
# ---------------------------------------------------------------------------


def create_many_to_one_loader(
    *,
    source_kls: type,
    rel_name: str,
    target_kls: type,
    target_remote_col_name: str,
    session_factory: Callable,
    filters: list[Any] | None = None,
) -> type[DataLoader]:
    """Create a DataLoader for many-to-one relationships.

    Batch-loads target entities by their primary key (remote column).
    """

    class _Loader(DataLoader):
        async def batch_load_fn(self, keys):
            from sqlalchemy import select

            async with self.session_factory() as session:
                stmt = select(self.target_kls).where(
                    getattr(self.target_kls, self.target_remote_col_name).in_(keys)
                )
                stmt = _apply_filters(stmt, self.filters)
                rows = (await session.scalars(stmt)).all()

            lookup = {getattr(row, self.target_remote_col_name): row for row in rows}
            return [lookup.get(k) for k in keys]

    _Loader.target_kls = target_kls
    _Loader.target_remote_col_name = target_remote_col_name
    _Loader.session_factory = staticmethod(session_factory)
    _Loader.filters = filters

    return _finalize_loader_class(
        _Loader,
        _build_loader_identity(source_kls, rel_name, "M2O"),
    )


# ---------------------------------------------------------------------------
# One-to-many loader
# ---------------------------------------------------------------------------


def create_one_to_many_loader(
    *,
    source_kls: type,
    rel_name: str,
    target_kls: type,
    target_fk_col_name: str,
    session_factory: Callable,
    filters: list[Any] | None = None,
) -> type[DataLoader]:
    """Create a DataLoader for one-to-many relationships.

    Batch-loads lists of target entities by the FK column on the target side.
    """

    class _Loader(DataLoader):
        async def batch_load_fn(self, keys):
            from sqlalchemy import select

            async with self.session_factory() as session:
                stmt = select(self.target_kls).where(
                    getattr(self.target_kls, self.target_fk_col_name).in_(keys)
                )
                stmt = _apply_filters(stmt, self.filters)
                rows = (await session.scalars(stmt)).all()

            grouped = defaultdict(list)
            for row in rows:
                grouped[getattr(row, self.target_fk_col_name)].append(row)

            return [grouped.get(k, []) for k in keys]

    _Loader.target_kls = target_kls
    _Loader.target_fk_col_name = target_fk_col_name
    _Loader.session_factory = staticmethod(session_factory)
    _Loader.filters = filters

    return _finalize_loader_class(
        _Loader,
        _build_loader_identity(source_kls, rel_name, "O2M"),
    )


# ---------------------------------------------------------------------------
# Many-to-many loader
# ---------------------------------------------------------------------------


def create_many_to_many_loader(
    *,
    source_kls: type,
    rel_name: str,
    target_kls: type,
    secondary_table: Any,
    secondary_local_col_name: str,
    secondary_remote_col_name: str,
    target_match_col_name: str,
    session_factory: Callable,
    filters: list[Any] | None = None,
) -> type[DataLoader]:
    """Create a DataLoader for many-to-many relationships through a secondary table."""

    class _Loader(DataLoader):
        async def batch_load_fn(self, keys):
            from sqlalchemy import select

            async with self.session_factory() as session:
                join_stmt = select(self.secondary_table).where(
                    getattr(self.secondary_table.c, self.secondary_local_col_name).in_(keys)
                )
                join_rows = (await session.execute(join_stmt)).all()

                target_keys = list(
                    {_row_get(row, self.secondary_remote_col_name) for row in join_rows}
                )
                if not target_keys:
                    return [[] for _ in keys]

                target_stmt = select(self.target_kls).where(
                    getattr(self.target_kls, self.target_match_col_name).in_(target_keys)
                )
                target_stmt = _apply_filters(target_stmt, self.filters)
                target_rows = (await session.scalars(target_stmt)).all()

            target_map = {
                getattr(row, self.target_match_col_name): row for row in target_rows
            }

            grouped = defaultdict(list)
            for join_row in join_rows:
                target_obj = target_map.get(_row_get(join_row, self.secondary_remote_col_name))
                if target_obj is not None:
                    grouped[_row_get(join_row, self.secondary_local_col_name)].append(target_obj)

            return [grouped.get(k, []) for k in keys]

    _Loader.target_kls = target_kls
    _Loader.secondary_table = secondary_table
    _Loader.secondary_local_col_name = secondary_local_col_name
    _Loader.secondary_remote_col_name = secondary_remote_col_name
    _Loader.target_match_col_name = target_match_col_name
    _Loader.session_factory = staticmethod(session_factory)
    _Loader.filters = filters

    return _finalize_loader_class(
        _Loader,
        _build_loader_identity(source_kls, rel_name, "M2M"),
    )


# ---------------------------------------------------------------------------
# Paginated one-to-many loader
# ---------------------------------------------------------------------------


def _build_page_result(
    rows: list,
    page_args: PageArgs,
    total_count: int | None,
    has_next_page: bool,
    entity_kls: type | None = None,
) -> dict:
    """Build a Page result dict from queried rows.

    If entity_kls is provided, RowMapping objects are converted to entity instances.
    """
    from sqlmodel_graphql.loader.pagination import Pagination

    effective_limit = page_args.effective_limit
    page_rows = rows[:effective_limit]

    # Convert RowMapping objects to entity instances if needed
    if entity_kls is not None:
        converted = []
        entity_fields = set(entity_kls.model_fields.keys())
        for row in page_rows:
            if hasattr(row, "_mapping"):
                # SQLAlchemy RowMapping - extract entity fields
                mapping = row._mapping
                data = {k: mapping[k] for k in entity_fields if k in mapping}
                converted.append(entity_kls(**data))
            elif isinstance(row, dict):
                data = {k: row[k] for k in entity_fields if k in row}
                converted.append(entity_kls(**data))
            else:
                converted.append(row)
        page_rows = converted

    pagination = Pagination(
        has_more=has_next_page,
        total_count=total_count,
    )

    return {
        "items": page_rows,
        "pagination": pagination,
    }


def create_page_one_to_many_loader(
    *,
    source_kls: type,
    rel_name: str,
    target_kls: type,
    target_fk_col_name: str,
    sort_field: str = "id",
    pk_col_name: str = "id",
    session_factory: Callable,
    filters: list[Any] | None = None,
) -> type[DataLoader]:
    """Create a loader that paginates per-parent using ROW_NUMBER().

    SQL strategy:
        SELECT * FROM (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY fk_col ORDER BY sort_field) AS __rn,
                   COUNT(*) OVER (PARTITION BY fk_col) AS __tc
            FROM target_table
            WHERE fk_col IN (:fk_values)
        ) sub WHERE __rn BETWEEN :start AND :end
    """

    class _Loader(DataLoader):
        async def batch_load_fn(self, keys):
            from sqlalchemy import func, select

            if not keys:
                return []

            first_cmd = keys[0]
            page_args: PageArgs = first_cmd.page_args
            fk_values = [cmd.fk_value for cmd in keys]

            effective_limit = page_args.effective_limit
            start = page_args.offset + 1
            end = start + effective_limit

            async with self.session_factory() as session:
                fk_col = getattr(self.target_kls, self.target_fk_col_name)
                sort_col = getattr(self.target_kls, self.sort_field)
                pk_col = getattr(self.target_kls, self.pk_col_name)

                rn_label = "_sg_rn"
                tc_label = "_sg_tc"

                row_num_col = func.row_number().over(
                    partition_by=fk_col,
                    order_by=[sort_col, pk_col],
                ).label(rn_label)

                total_count_col = func.count().over(
                    partition_by=fk_col,
                ).label(tc_label)

                inner = select(
                    self.target_kls,
                    row_num_col,
                    total_count_col,
                ).where(fk_col.in_(fk_values))
                inner = _apply_filters(inner, self.filters)
                subq = inner.subquery()

                rn_col = subq.c[rn_label]
                fk_col_sub = subq.c[self.target_fk_col_name]
                sort_col_sub = subq.c[self.sort_field]
                pk_col_sub = subq.c[self.pk_col_name]

                outer = select(subq).where(rn_col.between(start, end)).order_by(
                    fk_col_sub, sort_col_sub, pk_col_sub,
                )
                rows = (await session.execute(outer)).all()

                grouped = defaultdict(list)
                total_counts: dict[Any, int] = {}
                for row in rows:
                    row_dict = row._mapping
                    fk_val = row_dict[self.target_fk_col_name]
                    rn = row_dict[rn_label]
                    tc = row_dict[tc_label]
                    grouped[fk_val].append((row_dict, rn))
                    total_counts[fk_val] = tc

                # Fallback for parents with offset > total
                missing_fks = [cmd.fk_value for cmd in keys if cmd.fk_value not in total_counts]
                if missing_fks:
                    count_q = (
                        select(fk_col, func.count().label(tc_label))
                        .where(fk_col.in_(missing_fks))
                    )
                    count_q = _apply_filters(count_q, self.filters)
                    count_q = count_q.group_by(fk_col)
                    for row in (await session.execute(count_q)).all():
                        total_counts[row[0]] = row[1]

                return [
                    _build_page_result(
                        rows=[r for r, _ in grouped.get(cmd.fk_value, [])],
                        page_args=page_args,
                        total_count=total_counts.get(cmd.fk_value, 0),
                        has_next_page=total_counts.get(cmd.fk_value, 0) >= end
                        if cmd.fk_value in total_counts
                        else False,
                        entity_kls=self.target_kls,
                    )
                    for cmd in keys
                ]

    _Loader.target_kls = target_kls
    _Loader.target_fk_col_name = target_fk_col_name
    _Loader.sort_field = sort_field
    _Loader.pk_col_name = pk_col_name
    _Loader.session_factory = staticmethod(session_factory)
    _Loader.filters = filters

    return _finalize_loader_class(
        _Loader,
        _build_loader_identity(source_kls, rel_name, "PO2M"),
    )


# ---------------------------------------------------------------------------
# Paginated many-to-many loader
# ---------------------------------------------------------------------------


def create_page_many_to_many_loader(
    *,
    source_kls: type,
    rel_name: str,
    target_kls: type,
    secondary_table: Any,
    secondary_local_col_name: str,
    secondary_remote_col_name: str,
    target_match_col_name: str,
    sort_field: str = "id",
    pk_col_name: str = "id",
    session_factory: Callable,
    filters: list[Any] | None = None,
) -> type[DataLoader]:
    """Create a loader that paginates per-parent for M2M using ROW_NUMBER().

    Like create_page_one_to_many_loader but works through a secondary
    (association) table.
    """

    class _Loader(DataLoader):
        async def batch_load_fn(self, keys):
            from sqlalchemy import func, select

            if not keys:
                return []

            first_cmd = keys[0]
            page_args: PageArgs = first_cmd.page_args
            fk_values = [cmd.fk_value for cmd in keys]

            effective_limit = page_args.effective_limit
            start = page_args.offset + 1
            end = start + effective_limit

            async with self.session_factory() as session:
                sec_local_col = getattr(self.secondary_table.c, self.secondary_local_col_name)
                sec_remote_col = getattr(self.secondary_table.c, self.secondary_remote_col_name)
                target_match_col = getattr(self.target_kls, self.target_match_col_name)
                sort_col = getattr(self.target_kls, self.sort_field)
                pk_col = getattr(self.target_kls, self.pk_col_name)

                rn_label = "_sg_rn"
                tc_label = "_sg_tc"

                inner = select(
                    self.target_kls,
                    sec_local_col.label(self.secondary_local_col_name),
                    func.row_number().over(
                        partition_by=sec_local_col,
                        order_by=[sort_col, pk_col],
                    ).label(rn_label),
                    func.count().over(
                        partition_by=sec_local_col,
                    ).label(tc_label),
                ).join(
                    self.secondary_table,
                    target_match_col == sec_remote_col,
                ).where(
                    sec_local_col.in_(fk_values),
                )
                inner = _apply_filters(inner, self.filters)
                subq = inner.subquery()

                rn_col = subq.c[rn_label]
                sec_local_sub = subq.c[self.secondary_local_col_name]
                sort_col_sub = subq.c[self.sort_field]
                pk_col_sub = subq.c[self.pk_col_name]

                outer = select(subq).where(rn_col.between(start, end)).order_by(
                    sec_local_sub, sort_col_sub, pk_col_sub,
                )
                rows = (await session.execute(outer)).all()

                grouped = defaultdict(list)
                total_counts: dict[Any, int] = {}
                for row in rows:
                    row_dict = row._mapping
                    fk_val = row_dict[self.secondary_local_col_name]
                    rn = row_dict[rn_label]
                    tc = row_dict[tc_label]
                    grouped[fk_val].append((row_dict, rn))
                    total_counts[fk_val] = tc

                missing_fks = [cmd.fk_value for cmd in keys if cmd.fk_value not in total_counts]
                if missing_fks:
                    count_q = (
                        select(sec_local_col, func.count().label(tc_label))
                        .where(sec_local_col.in_(missing_fks))
                    )
                    count_q = _apply_filters(count_q, self.filters)
                    count_q = count_q.group_by(sec_local_col)
                    for row in (await session.execute(count_q)).all():
                        total_counts[row[0]] = row[1]

                return [
                    _build_page_result(
                        rows=[r for r, _ in grouped.get(cmd.fk_value, [])],
                        page_args=page_args,
                        total_count=total_counts.get(cmd.fk_value, 0),
                        has_next_page=total_counts.get(cmd.fk_value, 0) >= end
                        if cmd.fk_value in total_counts
                        else False,
                        entity_kls=self.target_kls,
                    )
                    for cmd in keys
                ]

    _Loader.target_kls = target_kls
    _Loader.secondary_table = secondary_table
    _Loader.secondary_local_col_name = secondary_local_col_name
    _Loader.secondary_remote_col_name = secondary_remote_col_name
    _Loader.target_match_col_name = target_match_col_name
    _Loader.sort_field = sort_field
    _Loader.pk_col_name = pk_col_name
    _Loader.session_factory = staticmethod(session_factory)
    _Loader.filters = filters

    return _finalize_loader_class(
        _Loader,
        _build_loader_identity(source_kls, rel_name, "PM2M"),
    )
