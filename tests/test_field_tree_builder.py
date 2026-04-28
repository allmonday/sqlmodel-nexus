"""Tests for FieldTreeBuilder — building field selection trees from GraphQL AST nodes."""

from __future__ import annotations

from graphql import parse

from sqlmodel_graphql.execution.field_tree_builder import FieldTreeBuilder


def _get_field_node(query: str, field_name: str):
    """Helper: parse a query and return the first FieldNode matching field_name."""
    doc = parse(query)
    for definition in doc.definitions:
        if hasattr(definition, "selection_set"):
            for selection in definition.selection_set.selections:
                if hasattr(selection, "name") and selection.name.value == field_name:
                    return selection
    return None


class TestFieldTreeBuilder:
    def test_build_simple_tree(self):
        """Scalar fields should map to None values."""
        builder = FieldTreeBuilder()
        node = _get_field_node("{ users { id name email } }", "users")
        tree = builder.build_field_tree(node)

        assert tree is not None
        assert tree == {"id": None, "name": None, "email": None}

    def test_build_nested_tree(self):
        """Relationship fields should map to nested dicts."""
        builder = FieldTreeBuilder()
        node = _get_field_node("{ users { id posts { title } } }", "users")
        tree = builder.build_field_tree(node)

        assert tree is not None
        assert "id" in tree
        assert tree["id"] is None
        assert "posts" in tree
        assert tree["posts"] == {"title": None}

    def test_build_deeply_nested_tree(self):
        """Deep nesting should produce nested dicts at each level."""
        builder = FieldTreeBuilder()
        node = _get_field_node(
            "{ users { id posts { title comments { text } } } }", "users"
        )
        tree = builder.build_field_tree(node)

        assert tree is not None
        assert tree["posts"]["comments"] == {"text": None}

    def test_build_with_no_selection_set(self):
        """FieldNode without selection_set should return None."""
        builder = FieldTreeBuilder()
        # A scalar field at root level has no selection_set
        node = _get_field_node("{ ping }", "ping")
        # ping has no selection_set, but _get_field_node still returns the node
        # However, build_field_tree checks selection_set
        if node and not node.selection_set:
            tree = builder.build_field_tree(node)
            assert tree is None

    def test_build_mixed_scalar_and_nested(self):
        """Mix of scalar and nested fields."""
        builder = FieldTreeBuilder()
        node = _get_field_node(
            "{ users { id name posts { id title } } }", "users"
        )
        tree = builder.build_field_tree(node)

        assert tree is not None
        assert tree["id"] is None
        assert tree["name"] is None
        assert tree["posts"] == {"id": None, "title": None}
