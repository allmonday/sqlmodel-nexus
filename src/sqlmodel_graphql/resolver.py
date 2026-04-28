"""Resolver — model-driven traversal for Core API use case response building.

Traverses Pydantic/DefineSubset model trees, executing resolve_* methods
to load related data and post_* methods to compute derived fields.
Supports cross-layer data flow via ExposeAs, SendTo, and Collector.

Uses the same LoaderRegistry as GraphQL mode for DataLoader access.

Usage:
    from sqlmodel_graphql import Resolver, DefineSubset, LoaderRegistry

    class PostSummary(DefineSubset):
        __subset__ = (Post, ('id', 'title', 'author_id'))
        author: UserSummary | None = None

        def resolve_author(self, loader=Loader('author')):
            return loader.load(self.author_id)

    registry = LoaderRegistry(entities=[User, Post], session_factory=session_factory)
    result = await Resolver(registry).resolve([
        PostSummary.model_validate(p) for p in posts
    ])
"""

from __future__ import annotations

import asyncio
import contextvars
import inspect
import typing
from collections.abc import Callable
from typing import Any, TypeVar, get_args, get_origin

from aiodataloader import DataLoader
from pydantic import BaseModel

from sqlmodel_graphql.context import (
    Collector,
    ICollector,
    scan_expose_fields,
    scan_send_to_fields,
)

T = TypeVar("T")


# ──────────────────────────────────────────────────────────
# Loader / Depends — declares DataLoader dependency in resolve_*
# ──────────────────────────────────────────────────────────

class Depends:
    """Internal wrapper for Loader dependency declarations."""

    def __init__(self, dependency=None):
        self.dependency = dependency


def Loader(dependency=None):
    """Declare a DataLoader dependency for resolve_* method parameters.

    Args:
        dependency: One of:
            - str: relationship name in LoaderRegistry
            - DataLoader subclass: instantiated and cached per Resolver
            - async callable: wrapped in DataLoader(batch_load_fn=...)

    Usage::

        # By name (LoaderRegistry lookup)
        def resolve_owner(self, loader=Loader('owner')):
            return loader.load(self.owner_id)

        # By DataLoader class
        def resolve_owner(self, loader=Loader(UserLoader)):
            return loader.load(self.owner_id)

        # By async batch function
        async def load_users(keys):
            ...
        def resolve_owner(self, loader=Loader(load_users)):
            return loader.load(self.owner_id)
    """
    return Depends(dependency=dependency)


# ──────────────────────────────────────────────────────────
# Resolver implementation
# ──────────────────────────────────────────────────────────

class Resolver:
    """Model-driven resolver for building use case responses.

    Traverses a tree of Pydantic models (typically DefineSubset DTOs),
    executing resolve_* methods to load related data via DataLoaders
    and post_* methods to compute derived fields.

    Supports cross-layer data flow:
    - ExposeAs: parent fields exposed to descendants via ancestor_context
    - SendTo + Collector: descendant fields aggregated to ancestors
    - AutoLoad: automatic relationship loading with ORM->DTO conversion

    Args:
        loader_registry: LoaderRegistry providing DataLoader instances.
            If None, resolve_* methods must use their own loaders.
        context: Optional context dict accessible via `context` parameter.
    """

    def __init__(
        self,
        loader_registry: Any = None,
        context: dict[str, Any] | None = None,
    ):
        self._registry = loader_registry
        self._context = context or {}
        self._parent_var: contextvars.ContextVar[Any] = contextvars.ContextVar(
            "parent", default=None
        )
        # Ancestor context: dict of {alias: value} from ExposeAs fields
        self._ancestor_var: contextvars.ContextVar[dict[str, Any]] = (
            contextvars.ContextVar("ancestors", default={})
        )
        # Collectors: dict of {alias: Collector} active in current scope
        self._collector_var: contextvars.ContextVar[dict[str, ICollector]] = (
            contextvars.ContextVar("collectors", default={})
        )
        # Per-node collector instances (for Collector parameter injection)
        self._node_collectors: dict[int, dict[str, ICollector]] = {}
        # Loader instance cache for Depends-based loaders
        self._loader_cache: dict[Any, DataLoader] = {}

    def _get_loader(self, node: Any, loader_name: str) -> DataLoader | None:
        """Get a DataLoader by name from the registry.

        DefineSubset DTOs resolve loaders within their source entity first,
        avoiding collisions when multiple entities share the same relationship
        name.
        """
        if self._registry is None:
            return None

        from sqlmodel_graphql.subset import get_subset_source

        source_entity = None
        if isinstance(node, BaseModel):
            source_entity = get_subset_source(type(node))
        if source_entity is not None:
            loader = self._registry.get_loader_for_entity(source_entity, loader_name)
            if loader is not None:
                return loader
        return self._registry.get_loader_by_name(loader_name)

    def _resolve_dep(self, node: Any, dep: Depends) -> DataLoader | None:
        """Resolve a Depends wrapper to a DataLoader instance."""
        dep_val = dep.dependency
        if dep_val is None:
            return None
        if isinstance(dep_val, str):
            return self._get_loader(node, dep_val)
        if isinstance(dep_val, type) and issubclass(dep_val, DataLoader):
            return self._get_or_create_loader(dep_val)
        if callable(dep_val):
            return self._get_or_create_fn_loader(dep_val)
        return None

    def _get_or_create_loader(self, loader_cls: type[DataLoader]) -> DataLoader:
        """Get or create a cached DataLoader instance by class."""
        if loader_cls not in self._loader_cache:
            self._loader_cache[loader_cls] = loader_cls()
        return self._loader_cache[loader_cls]

    def _get_or_create_fn_loader(self, fn: Callable) -> DataLoader:
        """Get or create a cached DataLoader wrapping an async batch function."""
        if fn not in self._loader_cache:
            self._loader_cache[fn] = DataLoader(batch_load_fn=fn)
        return self._loader_cache[fn]

    def _scan_resolve_methods(self, node: Any) -> list[tuple[str, str, Callable]]:
        """Scan a node for resolve_* methods."""
        results = []
        for attr_name in dir(type(node)):
            if attr_name.startswith("resolve_"):
                field_name = attr_name[len("resolve_"):]
                method = getattr(node, attr_name)
                if callable(method):
                    results.append((field_name, field_name, method))
        return results

    def _scan_post_methods(self, node: Any) -> list[tuple[str, str, Callable]]:
        """Scan a node for post_* methods."""
        results = []
        for attr_name in dir(type(node)):
            if attr_name.startswith("post_"):
                field_name = attr_name[len("post_"):]
                method = getattr(node, attr_name)
                if callable(method):
                    results.append((field_name, field_name, method))
        return results

    def _get_object_fields(self, node: Any) -> list[tuple[str, Any]]:
        """Get non-None fields that are BaseModel instances (for recursive traversal)."""
        results = []
        if not isinstance(node, BaseModel):
            return results
        for field_name in type(node).model_fields:
            value = getattr(node, field_name, None)
            if value is None:
                continue
            if isinstance(value, BaseModel):
                results.append((field_name, value))
            elif isinstance(value, list):
                if value and isinstance(value[0], BaseModel):
                    results.append((field_name, value))
        return results

    # ──────────────────────────────────────────────────────
    # AutoLoad — automatic relationship loading
    # ──────────────────────────────────────────────────────

    def _scan_auto_load_fields(self, node: Any) -> list[tuple[str, str, Any, Any]]:
        """Scan fields that should be auto-loaded from relationships.

        Detects fields by:
        1. Explicit: AutoLoad() annotation in field metadata
        2. Implicit: field name matches a relationship on the source entity
           and field type is a BaseModel subclass (DTO)

        Returns list of (field_name, rel_name, rel_info, field_info).
        """
        if not isinstance(node, BaseModel) or self._registry is None:
            return []

        from sqlmodel_graphql.context import AutoLoadInfo
        from sqlmodel_graphql.subset import get_subset_source

        source_entity = get_subset_source(type(node))
        if source_entity is None:
            return []

        # Get relationship names from source entity for implicit matching
        entity_rels = self._registry.get_relationships(source_entity)

        # Get subset field names so we can skip them (only extra fields are candidates)
        subset_field_names = set(getattr(type(node), "__subset_fields__", []))

        results = []
        for field_name, field_info in type(node).model_fields.items():
            # Skip fields that already have a manual resolve_* method
            if hasattr(type(node), f"resolve_{field_name}"):
                continue

            # Skip fields that are part of the subset definition
            if field_name in subset_field_names:
                continue

            # 1. Check for explicit AutoLoad() annotation
            has_autoload = False
            for meta in field_info.metadata:
                if isinstance(meta, AutoLoadInfo):
                    rel_name = meta.origin or field_name
                    rel_info = self._registry.get_relationship(
                        source_entity, rel_name
                    )
                    if rel_info is not None:
                        results.append((field_name, rel_name, rel_info, field_info))
                    has_autoload = True
                    break

            # 2. Implicit: field name matches a relationship + type is BaseModel
            if not has_autoload and field_name in entity_rels:
                dto_cls = self._extract_dto_cls(field_info)
                if dto_cls is not None:
                    rel_info = entity_rels[field_name]
                    results.append((field_name, field_name, rel_info, field_info))

        return results

    def _extract_dto_cls(self, field_info: Any) -> type[BaseModel] | None:
        """Extract the DTO class from a field annotation.

        Handles Optional, list, Annotated wrappers.
        """
        anno = field_info.annotation
        # Resolve string annotations from __future__ import annotations
        if isinstance(anno, str):
            return None

        # Unwrap Annotated
        origin = get_origin(anno)
        if origin is typing.Annotated:
            anno = get_args(anno)[0]
            origin = get_origin(anno)

        # Unwrap Optional (Union[X, None])
        if origin is type(None):
            return None
        args = get_args(anno)
        if args:
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1 and len(args) > 1:
                anno = non_none[0]
                origin = get_origin(anno)

        # Unwrap list
        if origin is list:
            args = get_args(anno)
            if args:
                anno = args[0]

        # Check if it's a BaseModel subclass
        if isinstance(anno, type) and issubclass(anno, BaseModel):
            return anno
        return None

    @staticmethod
    def _orm_to_dto(orm_instance: Any, dto_cls: type[BaseModel]) -> BaseModel:
        """Convert a SQLModel ORM instance to a DefineSubset DTO."""
        subset_fields = getattr(dto_cls, "__subset_fields__", None)
        if subset_fields is None:
            return dto_cls.model_validate(orm_instance)
        kwargs = {}
        for fname in subset_fields:
            val = getattr(orm_instance, fname, None)
            if val is not None:
                kwargs[fname] = val
        try:
            return dto_cls(**kwargs)
        except Exception:
            # Handle forward references from __future__ import annotations.
            # Build a namespace with all known DefineSubset DTOs so
            # model_rebuild can resolve type names like 'UserDTO'.
            import sys

            from sqlmodel_graphql.subset import _subset_registry

            module = sys.modules.get(dto_cls.__module__, None)
            ns = dict(vars(module)) if module else {}
            # Add all known DefineSubset DTOs to the namespace
            for dto_class in _subset_registry:
                ns[dto_class.__name__] = dto_class
            dto_cls.model_rebuild(_types_namespace=ns)
            return dto_cls(**kwargs)

    async def _auto_resolve_and_set(
        self,
        node: Any,
        field_name: str,
        rel_name: str,
        rel_info: Any,
        field_info: Any,
    ) -> None:
        """Execute auto-resolve for an AutoLoad field and set on node."""
        loader = self._get_loader(node, rel_name)
        if loader is None:
            return

        dto_cls = self._extract_dto_cls(field_info)
        is_custom = getattr(rel_info, "direction", "") == "CUSTOM"

        if rel_info.is_list:
            # One-to-many / many-to-many: load by PK
            pk_value = getattr(node, "id", None)
            if pk_value is None:
                return
            results = await loader.load(pk_value)
            if dto_cls and results:
                results = [
                    r if (is_custom and isinstance(r, BaseModel))
                    else self._orm_to_dto(r, dto_cls)
                    for r in results
                ]
            results = await self._traverse(results, node)
            setattr(node, field_name, results)
        else:
            # Many-to-one: load by FK
            fk_value = getattr(node, rel_info.fk_field, None)
            if fk_value is None:
                return
            result = await loader.load(fk_value)
            if result is None:
                return
            if dto_cls:
                if not (is_custom and isinstance(result, BaseModel)):
                    result = self._orm_to_dto(result, dto_cls)
            result = await self._traverse(result, node)
            setattr(node, field_name, result)

    # ──────────────────────────────────────────────────────
    # ExposeAs / Collector preparation
    # ──────────────────────────────────────────────────────

    def _prepare_expose_fields(self, node: Any) -> Callable[[], None]:
        """Push ExposeAs field values into ancestor context.

        Returns a cleanup function that restores the previous context.
        """
        if not isinstance(node, BaseModel):
            return lambda: None

        expose_map = scan_expose_fields(type(node))
        if not expose_map:
            return lambda: None

        current = self._ancestor_var.get()
        new_context = dict(current)
        for field_name, alias in expose_map.items():
            new_context[alias] = getattr(node, field_name, None)

        token = self._ancestor_var.set(new_context)
        return lambda: self._safe_reset(self._ancestor_var, token)

    def _prepare_collectors(self, node: Any) -> Callable[[], None]:
        """Create Collector instances for this node's post_* methods.

        Scans post_* method signatures for Collector parameters and
        creates fresh Collector instances. Also propagates any existing
        ancestor collectors downward.

        Returns a cleanup function.
        """
        if not isinstance(node, BaseModel):
            return lambda: None

        # Scan post methods for Collector parameters
        new_collectors: dict[str, ICollector] = {}
        for attr_name in dir(type(node)):
            if not attr_name.startswith("post_"):
                continue
            method = getattr(node, attr_name)
            if not callable(method):
                continue
            sig = inspect.signature(method)
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue
                if (
                    param.default is not inspect.Parameter.empty
                    and isinstance(param.default, Collector)
                ):
                    alias = param.default.alias
                    if alias not in new_collectors:
                        new_collectors[alias] = Collector(
                            alias=alias, flat=param.default.flat
                        )

        if not new_collectors:
            return lambda: None

        # Store per-node collectors for parameter injection
        self._node_collectors[id(node)] = new_collectors

        # Merge with existing ancestor collectors (propagate downward)
        current = self._collector_var.get()
        merged = dict(current)
        merged.update(new_collectors)

        token = self._collector_var.set(merged)
        return lambda: self._safe_reset(self._collector_var, token)

    def _add_values_into_collectors(self, node: Any) -> None:
        """Send SendTo-annotated field values to active collectors."""
        if not isinstance(node, BaseModel):
            return

        send_to_map = scan_send_to_fields(type(node))
        if not send_to_map:
            return

        collectors = self._collector_var.get()
        for field_name, collector_names in send_to_map.items():
            value = getattr(node, field_name, None)
            if value is None:
                continue

            # Normalize to tuple
            if isinstance(collector_names, str):
                collector_names = (collector_names,)

            for name in collector_names:
                collector = collectors.get(name)
                if collector is not None:
                    collector.add(value)

    @staticmethod
    def _safe_reset(var: contextvars.ContextVar, token: Any) -> None:
        """Safely reset a contextvar, ignoring errors."""
        try:
            var.reset(token)
        except (ValueError, LookupError):
            pass

    # ──────────────────────────────────────────────────────
    # Method execution with parameter injection
    # ──────────────────────────────────────────────────────

    async def _execute_resolve_method(
        self,
        node: Any,
        method: Callable,
    ) -> Any:
        """Execute a resolve_* method with parameter injection."""
        sig = inspect.signature(method)
        params = {}

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            if param_name == "context":
                params["context"] = self._context
                continue
            if param_name == "parent":
                params["parent"] = self._parent_var.get()
                continue
            if param_name == "ancestor_context":
                params["ancestor_context"] = self._ancestor_var.get()
                continue

            # Check for Depends (Loader) default
            if param.default is not inspect.Parameter.empty and isinstance(
                param.default, Depends
            ):
                loader = self._resolve_dep(node, param.default)
                if loader is not None:
                    params[param_name] = loader
                continue

        result = method(**params)
        while inspect.isawaitable(result):
            result = await result
        return result

    async def _execute_post_method(
        self,
        node: Any,
        method: Callable,
    ) -> Any:
        """Execute a post_* method with parameter injection."""
        sig = inspect.signature(method)
        params = {}

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            if param_name == "context":
                params["context"] = self._context
                continue
            if param_name == "parent":
                params["parent"] = self._parent_var.get()
                continue
            if param_name == "ancestor_context":
                params["ancestor_context"] = self._ancestor_var.get()
                continue

            # Check for Collector default
            if param.default is not inspect.Parameter.empty and isinstance(
                param.default, Collector
            ):
                node_cols = self._node_collectors.get(id(node), {})
                collector = node_cols.get(param.default.alias)
                if collector is not None:
                    params[param_name] = collector
                continue

        result = method(**params)
        while inspect.isawaitable(result):
            result = await result
        return result

    # ──────────────────────────────────────────────────────
    # Core traversal
    # ──────────────────────────────────────────────────────

    async def _traverse(self, node: T, parent: Any) -> T:
        """Core traversal: prepare → resolve → traverse children → post → collect → cleanup."""
        if isinstance(node, (list, tuple)):
            await asyncio.gather(*[self._traverse(t, parent) for t in node])
            return node

        if not isinstance(node, BaseModel):
            return node

        # Prepare phase: set up context for this node
        parent_token = self._parent_var.set(parent)
        expose_reset = self._prepare_expose_fields(node)
        collector_reset = self._prepare_collectors(node)

        try:
            # Phase 1: Execute resolve_* methods
            resolve_methods = self._scan_resolve_methods(node)
            auto_load_entries = self._scan_auto_load_fields(node)

            resolve_tasks = []
            for field_name, trim_field, method in resolve_methods:
                resolve_tasks.append(
                    self._resolve_and_set(node, trim_field, method)
                )

            # AutoLoad: auto-resolve fields without manual resolve_* methods
            for field_name, rel_name, rel_info, field_info in auto_load_entries:
                resolve_tasks.append(
                    self._auto_resolve_and_set(
                        node, field_name, rel_name, rel_info, field_info
                    )
                )

            # Phase 1b: Traverse existing object fields (non-resolve)
            object_fields = self._get_object_fields(node)
            for field_name, child in object_fields:
                resolve_tasks.append(self._traverse(child, node))

            await asyncio.gather(*resolve_tasks)

            # Phase 2: Execute post_* methods (after all resolves complete)
            post_methods = self._scan_post_methods(node)
            post_tasks = []
            for field_name, trim_field, method in post_methods:
                post_tasks.append(
                    self._post_and_set(node, trim_field, method)
                )
            await asyncio.gather(*post_tasks)

            # Phase 3: Collect — send SendTo values to ancestor collectors
            self._add_values_into_collectors(node)

        finally:
            # Cleanup: reset all contextvars
            collector_reset()
            expose_reset()
            self._parent_var.reset(parent_token)

        return node

    async def _resolve_and_set(
        self, node: Any, trim_field: str, method: Callable
    ) -> None:
        """Execute resolve method, traverse result, and set on node."""
        result = await self._execute_resolve_method(node, method)
        result = await self._traverse(result, node)
        setattr(node, trim_field, result)

    async def _post_and_set(
        self, node: Any, trim_field: str, method: Callable
    ) -> None:
        """Execute post method and set result on node."""
        result = await self._execute_post_method(node, method)
        setattr(node, trim_field, result)

    async def resolve(self, node: T) -> T:
        """Resolve a model tree: execute resolve_* and post_* methods.

        Args:
            node: A BaseModel instance, or list of BaseModel instances.

        Returns:
            The same node with all resolve_* and post_* fields populated.
        """
        if self._registry is not None and hasattr(self._registry, "clear_cache"):
            self._registry.clear_cache()
        self._node_collectors.clear()
        self._loader_cache.clear()
        await self._traverse(node, None)
        return node
