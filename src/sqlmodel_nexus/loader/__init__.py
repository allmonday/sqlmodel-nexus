"""Loader module - DataLoader factories and entity-relationship management."""

from sqlmodel_nexus.loader.pagination import (
    PageArgs,
    PageLoadCommand,
    Pagination,
    create_result_type,
)
from sqlmodel_nexus.loader.registry import ErManager, LoaderRegistry, RelationshipInfo

__all__ = [
    "ErManager",
    "LoaderRegistry",  # backward-compatible alias
    "RelationshipInfo",
    "PageArgs",
    "PageLoadCommand",
    "Pagination",
    "create_result_type",
]
