"""Test standard queries with the demo models."""

from __future__ import annotations

from sqlmodel_graphql import GraphQLHandler, AutoQueryConfig, add_standard_queries

# Import demo models
from demo.models import BaseEntity, User, Post, Comment
from demo.database import async_session


def test_demo_with_standard_queries():
    """Test adding standard queries to demo models."""
    # Add standard queries to all demo entities
    config = AutoQueryConfig(
        session_factory=async_session,
        default_limit=20,
    )
    add_standard_queries([User, Post, Comment], config)

    # Verify methods exist
    assert hasattr(User, "by_id")
    assert hasattr(User, "by_filter")
    assert hasattr(Post, "by_id")
    assert hasattr(Post, "by_filter")
    assert hasattr(Comment, "by_id")
    assert hasattr(Comment, "by_filter")

    # Verify filter input types exist
    assert hasattr(User, "_filter_input_type")
    assert hasattr(Post, "_filter_input_type")
    assert hasattr(Comment, "_filter_input_type")

    # Generate SDL
    handler = GraphQLHandler(base=BaseEntity)
    sdl = handler.get_sdl()

    print("=== Generated SDL with Standard Queries ===\n")
    print(sdl)
    print("\n=== End of SDL ===\n")

    # Verify SDL contains expected queries
    assert "userById" in sdl
    assert "userByFilter" in sdl
    assert "postById" in sdl
    assert "postByFilter" in sdl
    assert "commentById" in sdl
    assert "commentByFilter" in sdl

    # Verify filter input types
    assert "input UserFilterInput" in sdl
    assert "input PostFilterInput" in sdl
    assert "input CommentFilterInput" in sdl

    print("✅ All standard queries are successfully added to demo models!")


def test_graphql_handler_with_auto_config():
    """Test using auto_query_config directly in GraphQLHandler."""
    config = AutoQueryConfig(
        session_factory=async_session,
        default_limit=20,
    )

    handler = GraphQLHandler(base=BaseEntity, auto_query_config=config)
    sdl = handler.get_sdl()

    # Verify SDL contains expected queries
    assert "userById" in sdl
    assert "userByFilter" in sdl

    print("✅ auto_query_config works with GraphQLHandler!")


if __name__ == "__main__":
    test_demo_with_standard_queries()
    print()
    test_graphql_handler_with_auto_config()
    print()
    print("🎉 All tests passed!")
