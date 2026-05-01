"""RPC configuration types."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from sqlmodel_nexus.rpc.business import RpcService


class RpcServiceConfig(TypedDict, total=False):
    """Configuration for a single RPC service.

    Attributes:
        name: Unique identifier for the service (corresponds to OpenAPI tag).
        service: RpcService subclass with business methods.
        description: Human-readable description of the service.
    """

    name: str
    service: type[RpcService]
    description: str | None
