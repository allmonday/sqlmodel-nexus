"""Tests for TypeTracer class."""

from __future__ import annotations

import pytest

from sqlmodel_graphql.mcp.builders.type_tracer import TypeTracer


class TestTypeTracer:
    """Tests for TypeTracer class."""

    @pytest.fixture
    def simple_introspection(self) -> dict:
        """Create a simple introspection data with User type only."""
        return {
            "types": [
                {
                    "kind": "OBJECT",
                    "name": "Query",
                    "fields": [
                        {
                            "name": "users",
                            "description": "Get all users",
                            "args": [],
                            "type": {
                                "kind": "NON_NULL",
                                "ofType": {
                                    "kind": "LIST",
                                    "ofType": {
                                        "kind": "NON_NULL",
                                        "ofType": {"kind": "OBJECT", "name": "User"},
                                    },
                                },
                            },
                        }
                    ],
                },
                {
                    "kind": "OBJECT",
                    "name": "User",
                    "fields": [
                        {
                            "name": "id",
                            "type": {
                                "kind": "NON_NULL",
                                "ofType": {"kind": "SCALAR", "name": "Int"},
                            },
                        },
                        {
                            "name": "name",
                            "type": {
                                "kind": "NON_NULL",
                                "ofType": {"kind": "SCALAR", "name": "String"},
                            },
                        },
                    ],
                },
            ]
        }

    @pytest.fixture
    def related_types_introspection(self) -> dict:
        """Create introspection data with User and Post types."""
        return {
            "types": [
                {
                    "kind": "OBJECT",
                    "name": "Query",
                    "fields": [
                        {
                            "name": "users",
                            "description": "Get all users",
                            "args": [],
                            "type": {
                                "kind": "NON_NULL",
                                "ofType": {
                                    "kind": "LIST",
                                    "ofType": {
                                        "kind": "NON_NULL",
                                        "ofType": {"kind": "OBJECT", "name": "User"},
                                    },
                                },
                            },
                        }
                    ],
                },
                {
                    "kind": "OBJECT",
                    "name": "User",
                    "fields": [
                        {
                            "name": "id",
                            "type": {
                                "kind": "NON_NULL",
                                "ofType": {"kind": "SCALAR", "name": "Int"},
                            },
                        },
                        {
                            "name": "name",
                            "type": {
                                "kind": "NON_NULL",
                                "ofType": {"kind": "SCALAR", "name": "String"},
                            },
                        },
                        {
                            "name": "posts",
                            "type": {
                                "kind": "NON_NULL",
                                "ofType": {
                                    "kind": "LIST",
                                    "ofType": {
                                        "kind": "NON_NULL",
                                        "ofType": {"kind": "OBJECT", "name": "Post"},
                                    },
                                },
                            },
                        },
                    ],
                },
                {
                    "kind": "OBJECT",
                    "name": "Post",
                    "fields": [
                        {
                            "name": "id",
                            "type": {
                                "kind": "NON_NULL",
                                "ofType": {"kind": "SCALAR", "name": "Int"},
                            },
                        },
                        {
                            "name": "title",
                            "type": {
                                "kind": "NON_NULL",
                                "ofType": {"kind": "SCALAR", "name": "String"},
                            },
                        },
                        {
                            "name": "author",
                            "type": {
                                "kind": "NON_NULL",
                                "ofType": {"kind": "OBJECT", "name": "User"},
                            },
                        },
                    ],
                },
            ]
        }

    def test_collect_single_type(self, simple_introspection: dict) -> None:
        """Test collecting a single type."""
        tracer = TypeTracer(simple_introspection, {"User"})

        type_ref = {"kind": "OBJECT", "name": "User"}
        result = tracer.collect_related_types(type_ref)

        assert result == {"User"}

    def test_collect_nested_list_type(self, simple_introspection: dict) -> None:
        """Test collecting from a nested list type."""
        tracer = TypeTracer(simple_introspection, {"User"})

        # [User]! type reference
        type_ref = {
            "kind": "NON_NULL",
            "ofType": {
                "kind": "LIST",
                "ofType": {
                    "kind": "NON_NULL",
                    "ofType": {"kind": "OBJECT", "name": "User"},
                },
            },
        }
        result = tracer.collect_related_types(type_ref)

        assert result == {"User"}

    def test_collect_recursive_types(self, related_types_introspection: dict) -> None:
        """Test recursively collecting related types."""
        tracer = TypeTracer(related_types_introspection, {"User", "Post"})

        # Start from User type
        type_ref = {"kind": "OBJECT", "name": "User"}
        result = tracer.collect_related_types(type_ref)

        # Should include both User and Post (User -> posts -> Post)
        assert result == {"User", "Post"}

    def test_circular_reference(self, related_types_introspection: dict) -> None:
        """Test handling circular references (User -> Post -> User)."""
        tracer = TypeTracer(related_types_introspection, {"User", "Post"})

        # Start from User, which has posts, which has author back to User
        type_ref = {"kind": "OBJECT", "name": "User"}
        result = tracer.collect_related_types(type_ref)

        # Should not hang and should include both types
        assert result == {"User", "Post"}

    def test_deep_nesting(self) -> None:
        """Test handling deeply nested types."""
        introspection = {
            "types": [
                {
                    "kind": "OBJECT",
                    "name": "User",
                    "fields": [
                        {
                            "name": "posts",
                            "type": {
                                "kind": "NON_NULL",
                                "ofType": {
                                    "kind": "LIST",
                                    "ofType": {
                                        "kind": "NON_NULL",
                                        "ofType": {"kind": "OBJECT", "name": "Post"},
                                    },
                                },
                            },
                        }
                    ],
                },
                {
                    "kind": "OBJECT",
                    "name": "Post",
                    "fields": [
                        {
                            "name": "comments",
                            "type": {
                                "kind": "NON_NULL",
                                "ofType": {
                                    "kind": "LIST",
                                    "ofType": {
                                        "kind": "NON_NULL",
                                        "ofType": {"kind": "OBJECT", "name": "Comment"},
                                    },
                                },
                            },
                        }
                    ],
                },
                {
                    "kind": "OBJECT",
                    "name": "Comment",
                    "fields": [
                        {
                            "name": "author",
                            "type": {
                                "kind": "NON_NULL",
                                "ofType": {"kind": "OBJECT", "name": "User"},
                            },
                        }
                    ],
                },
            ]
        }

        tracer = TypeTracer(introspection, {"User", "Post", "Comment"})

        type_ref = {"kind": "OBJECT", "name": "User"}
        result = tracer.collect_related_types(type_ref)

        # Should collect all three types: User -> Post -> Comment -> User (cycle)
        assert result == {"User", "Post", "Comment"}

    def test_get_introspection_for_types(
        self, related_types_introspection: dict
    ) -> None:
        """Test getting introspection data for specific types."""
        tracer = TypeTracer(related_types_introspection, {"User", "Post"})

        result = tracer.get_introspection_for_types({"Post", "User"})

        # Should return two type info dictionaries
        assert len(result) == 2

        # Check that types are returned in sorted order
        names = [t["name"] for t in result]
        assert names == ["Post", "User"]

    def test_get_operation_field(self, related_types_introspection: dict) -> None:
        """Test getting a specific operation field."""
        tracer = TypeTracer(related_types_introspection, {"User", "Post"})

        field = tracer.get_operation_field("Query", "users")

        assert field is not None
        assert field["name"] == "users"
        assert field["description"] == "Get all users"

    def test_get_operation_field_not_found(
        self, related_types_introspection: dict
    ) -> None:
        """Test getting a non-existent operation field."""
        tracer = TypeTracer(related_types_introspection, {"User", "Post"})

        field = tracer.get_operation_field("Query", "nonexistent")

        assert field is None

    def test_list_operation_fields(self, related_types_introspection: dict) -> None:
        """Test listing all operation fields."""
        tracer = TypeTracer(related_types_introspection, {"User", "Post"})

        fields = tracer.list_operation_fields("Query")

        assert len(fields) == 1
        assert fields[0]["name"] == "users"
        assert fields[0]["description"] == "Get all users"

    def test_list_operation_fields_empty_for_nonexistent_type(
        self, related_types_introspection: dict
    ) -> None:
        """Test listing fields for a non-existent type returns empty list."""
        tracer = TypeTracer(related_types_introspection, {"User", "Post"})

        fields = tracer.list_operation_fields("NonExistent")

        assert fields == []

    def test_collect_types_excludes_non_entities(self) -> None:
        """Test that non-entity types are not collected."""
        introspection = {
            "types": [
                {
                    "kind": "OBJECT",
                    "name": "User",
                    "fields": [
                        {
                            "name": "settings",
                            "type": {"kind": "OBJECT", "name": "Settings"},
                        }
                    ],
                },
                {
                    "kind": "OBJECT",
                    "name": "Settings",
                    "fields": [
                        {"name": "theme", "type": {"kind": "SCALAR", "name": "String"}}
                    ],
                },
            ]
        }

        # Only User is an entity, Settings is not
        tracer = TypeTracer(introspection, {"User"})

        type_ref = {"kind": "OBJECT", "name": "User"}
        result = tracer.collect_related_types(type_ref)

        # Should only include User, not Settings
        assert result == {"User"}

    def test_none_type_ref(self, simple_introspection: dict) -> None:
        """Test handling None type reference."""
        tracer = TypeTracer(simple_introspection, {"User"})

        result = tracer.collect_related_types(None)

        assert result == set()
