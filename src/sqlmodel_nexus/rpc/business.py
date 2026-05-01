"""RpcService base class and BusinessMeta metaclass.

Provides the foundation for defining business service classes whose
async classmethods are automatically discovered and exposed via MCP.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any


def _to_snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


class BusinessMeta(type):
    """Metaclass that collects async classmethod info for introspection.

    Scans the class namespace for async classmethods and stores them
    in ``__rpc_methods__`` for use by ServiceIntrospector.
    """

    def __new__(mcs, name: str, bases: tuple, namespace: dict, **kwargs):
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)

        # Allow RpcService itself to be created without __rpc_methods__
        if name == "RpcService" and not any(
            isinstance(b, BusinessMeta) for b in bases
        ):
            cls.__rpc_methods__ = {}
            return cls

        # Collect async classmethods from this class and bases
        methods: dict[str, Any] = {}

        # First collect from bases
        for base in bases:
            if hasattr(base, "__rpc_methods__"):
                methods.update(base.__rpc_methods__)

        # Then collect from current class
        _EXCLUDED_METHODS = {"get_tag_name"}
        for attr_name, attr_value in namespace.items():
            # Skip private/protected and excluded methods
            if attr_name.startswith("_") or attr_name in _EXCLUDED_METHODS:
                continue

            # Check if it's a classmethod wrapping an async function
            func = _unwrap_classmethod(attr_value)
            if func is not None and asyncio.iscoroutinefunction(func):
                methods[attr_name] = attr_value

        cls.__rpc_methods__ = methods
        return cls


def _unwrap_classmethod(value: Any) -> Any | None:
    """Unwrap a classmethod to get the underlying function, if any."""
    if isinstance(value, classmethod):
        return value.__func__
    return None


class RpcService(metaclass=BusinessMeta):
    """Base class for business service definitions.

    Subclasses define async classmethods that represent RPC operations.
    The BusinessMeta metaclass automatically discovers these methods
    and makes them available for introspection.

    Example::

        class SprintService(RpcService):
            '''Sprint management service.'''

            @classmethod
            async def list_sprints(cls) -> list[SprintSummary]:
                '''Get all sprints.'''
                ...

            @classmethod
            async def get_sprint(cls, sprint_id: int) -> SprintSummary | None:
                '''Get a sprint by ID.'''
                ...
    """

    __rpc_methods__: dict[str, Any]

    @classmethod
    def get_tag_name(cls) -> str:
        """Return the OpenAPI tag name for this service.

        Default implementation strips ``Service``/``Rpc`` suffix and
        converts to snake_case. Override to customize.

        Returns:
            Tag name string (e.g. ``SprintService`` -> ``sprint``).
        """
        name = cls.__name__
        for suffix in ("Service", "Rpc"):
            if name.endswith(suffix) and len(name) > len(suffix):
                name = name[: -len(suffix)]
                break
        return _to_snake_case(name)
