"""Multi-app demo package."""

from .database import init_databases
from .models import BlogBaseEntity, ShopBaseEntity

__all__ = ["BlogBaseEntity", "ShopBaseEntity", "init_databases"]
