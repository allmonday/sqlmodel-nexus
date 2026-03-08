"""Tests for IntrospectionToSDL class."""

from __future__ import annotations

import pytest

from sqlmodel_graphql.mcp.builders.introspection_to_sdl import IntrospectionToSDL


class TestIntrospectionToSDL:
    """Tests for IntrospectionToSDL class."""

    @pytest.fixture
    def converter(self) -> IntrospectionToSDL:
        """Create an IntrospectionToSDL instance."""
        return IntrospectionToSDL()

    # Tests for format_type_ref
    def test_format_scalar_type(self, converter: IntrospectionToSDL) -> None:
        """Test formatting a simple scalar type."""
        type_ref = {"kind": "SCALAR", "name": "String", "ofType": None}
        assert converter.format_type_ref(type_ref) == "String"

    def test_format_non_null_type(self, converter: IntrospectionToSDL) -> None:
        """Test formatting a non-null type."""
        type_ref = {
            "kind": "NON_NULL",
            "name": None,
            "ofType": {"kind": "SCALAR", "name": "Int", "ofType": None}
        }
        assert converter.format_type_ref(type_ref) == "Int!"

    def test_format_list_type(self, converter: IntrospectionToSDL) -> None:
        """Test formatting a list type."""
        type_ref = {
            "kind": "LIST",
            "name": None,
            "ofType": {"kind": "SCALAR", "name": "Int", "ofType": None}
        }
        assert converter.format_type_ref(type_ref) == "[Int]"

    def test_format_non_null_list_non_null(self, converter: IntrospectionToSDL) -> None:
        """Test formatting [User!]! type."""
        type_ref = {
            "kind": "NON_NULL",
            "name": None,
            "ofType": {
                "kind": "LIST",
                "name": None,
                "ofType": {
                    "kind": "NON_NULL",
                    "name": None,
                    "ofType": {"kind": "OBJECT", "name": "User", "ofType": None}
                }
            }
        }
        assert converter.format_type_ref(type_ref) == "[User!]!"

    def test_format_null_type_ref(self, converter: IntrospectionToSDL) -> None:
        """Test formatting None type reference."""
        assert converter.format_type_ref(None) == "Unknown"

    # Tests for format_args
    def test_format_empty_args(self, converter: IntrospectionToSDL) -> None:
        """Test formatting empty args list."""
        assert converter.format_args([]) == ""

    def test_format_single_arg(self, converter: IntrospectionToSDL) -> None:
        """Test formatting single argument."""
        args = [
            {"name": "id", "type": {"kind": "SCALAR", "name": "Int"}, "defaultValue": None}
        ]
        assert converter.format_args(args) == "(id: Int)"

    def test_format_multiple_args(self, converter: IntrospectionToSDL) -> None:
        """Test formatting multiple arguments."""
        args = [
            {"name": "limit", "type": {"kind": "SCALAR", "name": "Int"}, "defaultValue": None},
            {"name": "offset", "type": {"kind": "SCALAR", "name": "Int"}, "defaultValue": None}
        ]
        result = converter.format_args(args)
        assert "limit: Int" in result
        assert "offset: Int" in result

    def test_format_arg_with_default_value(self, converter: IntrospectionToSDL) -> None:
        """Test formatting argument with default value."""
        args = [
            {"name": "limit", "type": {"kind": "SCALAR", "name": "Int"}, "defaultValue": "10"}
        ]
        assert converter.format_args(args) == "(limit: Int = 10)"

    def test_format_non_null_arg(self, converter: IntrospectionToSDL) -> None:
        """Test formatting non-null argument."""
        args = [
            {
                "name": "id",
                "type": {
                    "kind": "NON_NULL",
                    "ofType": {"kind": "SCALAR", "name": "Int"}
                },
                "defaultValue": None
            }
        ]
        assert converter.format_args(args) == "(id: Int!)"

    # Tests for convert_field
    def test_convert_simple_field(self, converter: IntrospectionToSDL) -> None:
        """Test converting a simple field."""
        field = {
            "name": "id",
            "args": [],
            "type": {"kind": "SCALAR", "name": "Int"}
        }
        assert converter.convert_field(field) == "  id: Int"

    def test_convert_field_with_args(self, converter: IntrospectionToSDL) -> None:
        """Test converting a field with arguments."""
        field = {
            "name": "user",
            "args": [{"name": "id", "type": {"kind": "SCALAR", "name": "Int"}, "defaultValue": None}],
            "type": {"kind": "OBJECT", "name": "User"}
        }
        assert converter.convert_field(field) == "  user(id: Int): User"

    # Tests for convert_type
    def test_convert_simple_type(self, converter: IntrospectionToSDL) -> None:
        """Test converting a simple type."""
        type_info = {
            "kind": "OBJECT",
            "name": "User",
            "description": None,
            "fields": [
                {"name": "id", "args": [], "type": {"kind": "SCALAR", "name": "Int"}},
                {"name": "name", "args": [], "type": {"kind": "SCALAR", "name": "String"}}
            ]
        }
        result = converter.convert_type(type_info)
        assert "type User {" in result
        assert "  id: Int" in result
        assert "  name: String" in result
        assert "}" in result

    def test_convert_type_with_description(self, converter: IntrospectionToSDL) -> None:
        """Test converting a type with description."""
        type_info = {
            "kind": "OBJECT",
            "name": "User",
            "description": "A user in the system",
            "fields": [
                {"name": "id", "args": [], "type": {"kind": "SCALAR", "name": "Int"}}
            ]
        }
        result = converter.convert_type(type_info)
        assert '"""A user in the system"""' in result

    # Tests for convert_operation
    def test_convert_query_operation(self, converter: IntrospectionToSDL) -> None:
        """Test converting a query operation."""
        operation = {
            "name": "users",
            "description": "Get all users",
            "args": [],
            "type": {
                "kind": "NON_NULL",
                "ofType": {
                    "kind": "LIST",
                    "ofType": {"kind": "OBJECT", "name": "User"}
                }
            }
        }
        result = converter.convert_operation(operation, "Query")
        assert '"""Get all users"""' in result
        assert "users: [User]!" in result

    def test_convert_mutation_operation(self, converter: IntrospectionToSDL) -> None:
        """Test converting a mutation operation."""
        operation = {
            "name": "createUser",
            "description": "Create a new user",
            "args": [
                {"name": "name", "type": {"kind": "SCALAR", "name": "String"}, "defaultValue": None},
                {"name": "email", "type": {"kind": "SCALAR", "name": "String"}, "defaultValue": None}
            ],
            "type": {"kind": "OBJECT", "name": "User"}
        }
        result = converter.convert_operation(operation, "Mutation")
        assert '"""Create a new user"""' in result
        assert "createUser(" in result
        assert "name: String" in result
        assert "email: String" in result
        assert "): User" in result

    # Tests for convert_types
    def test_convert_multiple_types(self, converter: IntrospectionToSDL) -> None:
        """Test converting multiple types."""
        types = [
            {
                "kind": "OBJECT",
                "name": "User",
                "description": None,
                "fields": [{"name": "id", "args": [], "type": {"kind": "SCALAR", "name": "Int"}}]
            },
            {
                "kind": "OBJECT",
                "name": "Post",
                "description": None,
                "fields": [{"name": "title", "args": [], "type": {"kind": "SCALAR", "name": "String"}}]
            }
        ]
        result = converter.convert_types(types)
        assert "type User {" in result
        assert "type Post {" in result
        # Types should be separated by blank lines
        assert "\n\n" in result

    # Tests for convert_operation_with_types
    def test_convert_operation_with_types_full(
        self, converter: IntrospectionToSDL
    ) -> None:
        """Test converting operation with related types."""
        operation = {
            "name": "users",
            "description": "Get all users",
            "args": [{"name": "limit", "type": {"kind": "SCALAR", "name": "Int"}, "defaultValue": None}],
            "type": {"kind": "OBJECT", "name": "User"}
        }
        types = [
            {
                "kind": "OBJECT",
                "name": "User",
                "description": None,
                "fields": [
                    {"name": "id", "args": [], "type": {"kind": "SCALAR", "name": "Int"}},
                    {"name": "name", "args": [], "type": {"kind": "SCALAR", "name": "String"}}
                ]
            }
        ]
        result = converter.convert_operation_with_types(operation, types, "Query")

        # Should contain Query section
        assert "# Query" in result
        assert "users(limit: Int): User" in result

        # Should contain Related Types section
        assert "# Related Types" in result
        assert "type User {" in result
        assert "  id: Int" in result
        assert "  name: String" in result

    def test_convert_operation_without_types(
        self, converter: IntrospectionToSDL
    ) -> None:
        """Test converting operation without related types."""
        operation = {
            "name": "version",
            "description": "Get API version",
            "args": [],
            "type": {"kind": "SCALAR", "name": "String"}
        }
        result = converter.convert_operation_with_types(operation, [], "Query")

        assert "# Query" in result
        assert "version: String" in result
        # Should not have Related Types section when types is empty
        assert "# Related Types" not in result
