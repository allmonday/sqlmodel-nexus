"""Custom relationship definitions for SQLModel entities.

Define non-ORM relationships with manually provided async batch loaders.
Used alongside ORM relationships discovered by SQLAlchemy inspection.

Usage:
    from sqlmodel_graphql import Relationship

    async def tags_by_post_id_loader(post_ids: list[int]) -> list[list[Tag]]:
        ...

    class Post(SQLModel, table=True):
        __tablename__ = "post"
        __relationships__ = [
            Relationship(
                fk='id',
                target=Tag,
                name='tags',
                loader=tags_by_post_id_loader,
                is_list=True,
            )
        ]
        id: int | None = Field(default=None, primary_key=True)
        title: str
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlmodel import SQLModel


@dataclass
class Relationship:
    """Defines a custom (non-ORM) relationship for a SQLModel entity.

    Args:
        fk: FK field name on the source entity. For many-to-one, this is the
            actual FK column (e.g. 'owner_id'). For one-to-many (is_list=True),
            this is the source entity's PK field (typically 'id').
        target: Target SQLModel entity class. Used for type checking and
            ER diagram generation.
        name: Unique relationship name within this entity. Becomes the lookup
            key in LoaderRegistry and auto-loading.
        loader: Async batch loader function. Signature varies by is_list:
            - is_list=False: ``async def fn(keys: list[K]) -> list[V | None]``
            - is_list=True:  ``async def fn(keys: list[K]) -> list[list[V]]``
        is_list: True for one-to-many style relationships where one source
            entity maps to multiple target entities.
        description: Optional description for ER diagram documentation.
    """

    fk: str
    target: type[SQLModel]
    name: str
    loader: Callable
    is_list: bool = False
    description: str | None = None


def get_custom_relationships(entity: type[SQLModel]) -> list[Relationship]:
    """Read __relationships__ from a SQLModel entity class.

    Returns an empty list if __relationships__ is not defined.
    Validates each entry is a Relationship instance.
    """
    raw = getattr(entity, "__relationships__", None)
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise TypeError(
            f"{entity.__name__}.__relationships__ must be a list of Relationship, "
            f"got {type(raw).__name__}"
        )
    for i, item in enumerate(raw):
        if not isinstance(item, Relationship):
            raise TypeError(
                f"{entity.__name__}.__relationships__[{i}] must be a Relationship, "
                f"got {type(item).__name__}"
            )
    return list(raw)
