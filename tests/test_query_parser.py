"""Tests for QueryParser — GraphQL query parsing and field selection extraction."""

from __future__ import annotations

import pytest

from sqlmodel_graphql.query_parser import FieldSelection, QueryParser


class TestQueryParserBasic:
    def test_parse_simple_query(self):
        """Parser should extract simple scalar field selections."""
        parser = QueryParser()
        result = parser.parse("{ users { id name } }")

        assert "users" in result
        assert "id" in result["users"].sub_fields
        assert "name" in result["users"].sub_fields

    def test_parse_nested_fields(self):
        """Parser should extract nested relationship field selections."""
        parser = QueryParser()
        result = parser.parse("{ users { id posts { title content } } }")

        assert "users" in result
        users = result["users"]
        assert "posts" in users.sub_fields
        posts = users.sub_fields["posts"]
        assert "title" in posts.sub_fields
        assert "content" in posts.sub_fields

    def test_parse_with_nested_arguments(self):
        """Arguments on nested fields should be extracted."""
        parser = QueryParser()
        result = parser.parse("{ users { id posts(limit: 10) { title } } }")

        users = result["users"]
        posts = users.sub_fields["posts"]
        assert posts.arguments == {"limit": 10}

    def test_parse_mutation(self):
        """Parser should parse mutation operations."""
        parser = QueryParser()
        result = parser.parse('mutation { createUser(name: "Alice") { id name } }')

        assert "createUser" in result
        user = result["createUser"]
        assert "id" in user.sub_fields
        assert "name" in user.sub_fields

    def test_parse_multiple_operations(self):
        """Parser should parse multiple field selections in one operation."""
        parser = QueryParser()
        result = parser.parse("{ users { id } posts { title } }")

        assert "users" in result
        assert "posts" in result

    def test_parse_empty_selection(self):
        """Parser should handle operations with no sub-selections on a field."""
        parser = QueryParser()
        # A field with no selection set (scalar root) won't appear in result
        # because parse() only processes fields with selection_set
        result = parser.parse("{ ping }")
        assert result == {}


class TestFieldValueTypes:
    """Test that _value_node_to_python converts all GraphQL value types correctly."""

    def test_int_value(self):
        parser = QueryParser()
        result = parser.parse('{ users { posts(limit: 42) { id } } }')
        assert result["users"].sub_fields["posts"].arguments["limit"] == 42

    def test_float_value(self):
        parser = QueryParser()
        result = parser.parse('{ users { posts(ratio: 3.14) { id } } }')
        assert result["users"].sub_fields["posts"].arguments["ratio"] == pytest.approx(3.14)

    def test_string_value(self):
        parser = QueryParser()
        result = parser.parse('{ users { posts(filter: "hello") { id } } }')
        assert result["users"].sub_fields["posts"].arguments["filter"] == "hello"

    def test_boolean_value(self):
        parser = QueryParser()
        result = parser.parse('{ users { posts(active: true) { id } } }')
        assert result["users"].sub_fields["posts"].arguments["active"] is True

    def test_null_value(self):
        parser = QueryParser()
        result = parser.parse('{ users { posts(ref: null) { id } } }')
        assert result["users"].sub_fields["posts"].arguments["ref"] is None

    def test_list_value(self):
        parser = QueryParser()
        result = parser.parse('{ users { posts(ids: [1, 2, 3]) { id } } }')
        assert result["users"].sub_fields["posts"].arguments["ids"] == [1, 2, 3]

    def test_object_value(self):
        parser = QueryParser()
        q = '{ users { posts(filter: {name: "Alice", age: 30}) { id } } }'
        result = parser.parse(q)
        expected = {"name": "Alice", "age": 30}
        assert result["users"].sub_fields["posts"].arguments["filter"] == expected

    def test_enum_value(self):
        parser = QueryParser()
        result = parser.parse('{ users { posts(sort: ASC) { id } } }')
        assert result["users"].sub_fields["posts"].arguments["sort"] == "ASC"


class TestFieldSelectionDataclass:
    def test_default_values(self):
        sel = FieldSelection()
        assert sel.name == ""
        assert sel.alias is None
        assert sel.arguments == {}
        assert sel.sub_fields == {}

    def test_with_values(self):
        sel = FieldSelection(
            name="users",
            alias="allUsers",
            arguments={"limit": 10},
        )
        assert sel.name == "users"
        assert sel.alias == "allUsers"
        assert sel.arguments == {"limit": 10}
