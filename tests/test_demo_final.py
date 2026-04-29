"""Test standard queries in demo."""

from demo.database import async_session
from demo.models import BaseEntity
from sqlmodel_nexus import AutoQueryConfig, GraphQLHandler

config = AutoQueryConfig(
    session_factory=async_session,
    default_limit=20,
)

handler = GraphQLHandler(base=BaseEntity, session_factory=async_session, auto_query_config=config)

sdl = handler.get_sdl()

print("=== Demo with Standard Queries ===\n")
print(sdl)

# Check if standard queries exist
assert "userById" in sdl
assert "userByFilter" in sdl
assert "postById" in sdl
assert "postByFilter" in sdl
assert "commentById" in sdl
assert "commentByFilter" in sdl

print("\n✅ All standard queries added successfully!")
