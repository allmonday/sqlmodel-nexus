"""Type compatibility checking for implicit auto-loading.

Validates that a DTO field type is compatible with a relationship's
target entity before auto-loading. Adapted from pydantic-resolve's
``class_util.is_compatible_type``.
"""

from __future__ import annotations

import types
from typing import Union, get_args, get_origin

from sqlmodel_graphql.subset import SUBSET_REFERENCE


def _is_optional(tp: type) -> bool:
    """Check if a type is Optional[X] (Union[X, None])."""
    origin = get_origin(tp)
    if origin is Union or origin is types.UnionType:
        args = get_args(tp)
        return type(None) in args
    return False


def _is_list(tp: type) -> bool:
    """Check if a type is list[X]."""
    return get_origin(tp) is list


def _safe_issubclass(kls: type, classinfo: type) -> bool:
    try:
        return issubclass(kls, classinfo)
    except TypeError:
        return False


def is_compatible_type(src_type: type, target_type: type) -> bool:
    """Check if src_type is compatible with target_type for auto-loading.

    Compatible means one of:
    1. Same type (after unwrapping Optional from src)
    2. src is a DefineSubset of target (follows __sqlmodel_graphql_subset_source__ chain)
    3. src is a subclass of target
    4. list[src_element] is compatible with list[target] (recursive check)

    Args:
        src_type: The DTO field annotation type (e.g. UserDTO, list[UserDTO]).
        target_type: The relationship's target entity class (e.g. User).

    Returns:
        True if src_type can receive data loaded from target_type.
    """

    def unwrap_optional(tp):
        if _is_optional(tp):
            args = [a for a in get_args(tp) if a is not type(None)]
            if len(args) == 1:
                return args[0]
        return tp

    def is_union(tp):
        origin = get_origin(tp)
        return origin is Union or origin is types.UnionType

    def is_subset_of(src, tgt) -> bool:
        """Walk the subset source chain to check if src derives from tgt."""
        current = src
        while current is not None:
            if current is tgt:
                return True
            current = getattr(current, SUBSET_REFERENCE, None)
        return False

    def is_list_compatible(src, tgt) -> bool:
        if _is_list(src) and _is_list(tgt):
            src_args, tgt_args = get_args(src), get_args(tgt)
            if not src_args or not tgt_args:
                return False
            return is_compatible_type(src_args[0], tgt_args[0])
        return False

    # Unwrap Optional in src
    src = unwrap_optional(src_type)
    tgt = target_type

    # Non-optional unions are incompatible
    if is_union(src) or is_union(tgt):
        return False

    # list[SrcDTO] vs list[Target]
    if is_list_compatible(src, tgt):
        return True

    # Direct equality
    if src is tgt:
        return True

    # Subset chain: SrcDTO → __subset_source__ → ... → Target
    try:
        if is_subset_of(src, tgt):
            return True
    except Exception:
        pass

    # Subclass check
    try:
        if _safe_issubclass(src, tgt):
            return True
    except Exception:
        pass

    return False
