"""Loader module - DataLoader factories and relationship registry."""

from sqlmodel_graphql.loader.pagination import (
    PageArgs,
    PageLoadCommand,
    Pagination,
    create_result_type,
)
from sqlmodel_graphql.loader.registry import LoaderRegistry, RelationshipInfo

__all__ = [
    "LoaderRegistry",
    "RelationshipInfo",
    "PageArgs",
    "PageLoadCommand",
    "Pagination",
    "create_result_type",
]
