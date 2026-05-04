"""Voyager visualization for RPC services and ER diagrams.

Provides interactive visualization of RPC service structure
and entity-relationship diagrams, decoupled from FastAPI.
"""
from sqlmodel_nexus.voyager.create_voyager import create_rpc_voyager

__all__ = ["create_rpc_voyager"]
