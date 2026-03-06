"""Tests for MCP integration."""

from __future__ import annotations

import pytest

from sqlmodel_graphql.mcp.builders.query_builder import GraphQLQueryBuilder
from sqlmodel_graphql.mcp.types.errors import (
    MCPError,
    MCPErrors,
    create_error_response,
    create_success_response,
)


class TestGraphQLQueryBuilder:
    """Tests for GraphQLQueryBuilder."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.builder = GraphQLQueryBuilder()

    def test_build_simple_query(self) -> None:
        """Test building a simple query with scalar fields."""
        query = self.builder.build_query(
            operation_name="users",
            arguments=None,
            fields=["id", "name", "email"],
        )
        assert query == "query { users { id name email } }"

    def test_build_query_with_arguments(self) -> None:
        """Test building a query with arguments."""
        query = self.builder.build_query(
            operation_name="user",
            arguments={"id": 1},
            fields=["id", "name"],
        )
        assert query == 'query { user(id: 1) { id name } }'

    def test_build_query_with_string_argument(self) -> None:
        """Test building a query with string arguments."""
        query = self.builder.build_query(
            operation_name="search",
            arguments={"name": "John"},
            fields=["id", "name"],
        )
        assert query == 'query { search(name: "John") { id name } }'

    def test_build_query_with_multiple_arguments(self) -> None:
        """Test building a query with multiple arguments."""
        query = self.builder.build_query(
            operation_name="users",
            arguments={"limit": 10, "offset": 5},
            fields=["id", "name"],
        )
        # Arguments order may vary
        assert "limit: 10" in query
        assert "offset: 5" in query

    def test_build_query_with_nested_fields(self) -> None:
        """Test building a query with nested relationship fields."""
        query = self.builder.build_query(
            operation_name="users",
            arguments=None,
            fields=["id", "posts.title", "posts.content"],
        )
        assert query == "query { users { id posts { title content } } }"

    def test_build_query_with_deeply_nested_fields(self) -> None:
        """Test building a query with deeply nested fields."""
        query = self.builder.build_query(
            operation_name="posts",
            arguments=None,
            fields=["title", "author.name", "author.email", "comments.content"],
        )
        assert "author { name email }" in query
        assert "comments { content }" in query

    def test_build_query_with_multiple_nested_relationships(self) -> None:
        """Test building a query with multiple nested relationships at different levels."""
        query = self.builder.build_query(
            operation_name="posts",
            arguments=None,
            fields=["title", "author.name", "comments.content", "comments.author.name"],
        )
        # comments should have both content and author nested
        assert "comments { content author { name } }" in query

    def test_build_mutation(self) -> None:
        """Test building a mutation."""
        query = self.builder.build_query(
            operation_name="create_user",
            arguments={"name": "John", "email": "john@example.com"},
            fields=["id", "name"],
            operation_type="mutation",
        )
        assert query.startswith("mutation { create_user(")
        assert "name: \"John\"" in query
        assert 'email: "john@example.com"' in query
        assert "{ id name }" in query

    def test_format_value_null(self) -> None:
        """Test formatting null values."""
        assert self.builder._format_value(None) == "null"

    def test_format_value_boolean(self) -> None:
        """Test formatting boolean values."""
        assert self.builder._format_value(True) == "true"
        assert self.builder._format_value(False) == "false"

    def test_format_value_number(self) -> None:
        """Test formatting numeric values."""
        assert self.builder._format_value(42) == "42"
        assert self.builder._format_value(3.14) == "3.14"

    def test_format_value_string(self) -> None:
        """Test formatting string values."""
        assert self.builder._format_value("hello") == '"hello"'
        assert self.builder._format_value('with "quotes"') == '"with \\"quotes\\""'

    def test_format_value_list(self) -> None:
        """Test formatting list values."""
        result = self.builder._format_value([1, 2, 3])
        assert result == "[1, 2, 3]"

    def test_format_value_dict(self) -> None:
        """Test formatting dict values (input objects)."""
        result = self.builder._format_value({"name": "John", "age": 30})
        # Order may vary
        assert "name: \"John\"" in result
        assert "age: 30" in result

    def test_empty_fields_raises_error(self) -> None:
        """Test that empty fields raises an error."""
        with pytest.raises(MCPError) as exc_info:
            self.builder.build_query(
                operation_name="users",
                arguments=None,
                fields=[],
            )
        assert exc_info.value.error_type == MCPErrors.MISSING_REQUIRED_FIELD

    def test_invalid_field_path_raises_error(self) -> None:
        """Test that invalid field paths raise errors."""
        with pytest.raises(MCPError) as exc_info:
            self.builder.build_query(
                operation_name="users",
                arguments=None,
                fields=[""],
            )
        assert exc_info.value.error_type == MCPErrors.INVALID_FIELD_PATH

    def test_field_path_with_empty_segment_raises_error(self) -> None:
        """Test that field paths with empty segments raise errors."""
        with pytest.raises(MCPError) as exc_info:
            self.builder.build_query(
                operation_name="users",
                arguments=None,
                fields=["posts..title"],
            )
        assert exc_info.value.error_type == MCPErrors.INVALID_FIELD_PATH


class TestMCPErrors:
    """Tests for MCP error handling."""

    def test_create_error_response_with_mcp_error(self) -> None:
        """Test creating error response from MCPError."""
        error = MCPError(MCPErrors.VALIDATION_ERROR, "Invalid input")
        response = create_error_response(error)
        assert response == {
            "success": False,
            "error": "Invalid input",
            "error_type": "validation_error",
        }

    def test_create_error_response_with_string(self) -> None:
        """Test creating error response from string."""
        response = create_error_response("Something went wrong")
        assert response == {
            "success": False,
            "error": "Something went wrong",
            "error_type": "internal_error",
        }

    def test_create_error_response_with_string_and_type(self) -> None:
        """Test creating error response with explicit type."""
        response = create_error_response(
            "Field not found",
            MCPErrors.TYPE_NOT_FOUND,
        )
        assert response == {
            "success": False,
            "error": "Field not found",
            "error_type": "type_not_found",
        }

    def test_create_success_response(self) -> None:
        """Test creating success response."""
        response = create_success_response({"id": 1, "name": "John"})
        assert response == {
            "success": True,
            "data": {"id": 1, "name": "John"},
        }


class TestSchemaFormatter:
    """Tests for SchemaFormatter with simple test entities."""

    def test_get_schema_info_structure(self) -> None:
        """Test that get_schema_info returns proper structure using test entities."""
        from typing import Optional

        from sqlmodel import Field, SQLModel

        from sqlmodel_graphql import query
        from sqlmodel_graphql.handler import GraphQLHandler
        from sqlmodel_graphql.mcp.builders.schema_formatter import SchemaFormatter

        # Define test entities inline to avoid import issues
        class TestUser(SQLModel, table=False):
            """Test user entity."""

            id: int = Field(primary_key=True)
            name: str

            @query(name="test_users")
            async def get_all(cls) -> list["TestUser"]:
                return []

        handler = GraphQLHandler(entities=[TestUser])
        formatter = SchemaFormatter(handler)
        info = formatter.get_schema_info()

        assert "queries" in info
        assert "mutations" in info
        assert "types" in info

        # Check queries
        assert len(info["queries"]) > 0
        query_names = [q["name"] for q in info["queries"]]
        assert "test_users" in query_names

        # Check types
        assert len(info["types"]) > 0
        type_names = [t["name"] for t in info["types"]]
        assert "TestUser" in type_names

    def test_type_has_scalar_fields(self) -> None:
        """Test that types have scalar fields."""
        from sqlmodel import Field, SQLModel

        from sqlmodel_graphql import query
        from sqlmodel_graphql.handler import GraphQLHandler
        from sqlmodel_graphql.mcp.builders.schema_formatter import SchemaFormatter

        class TestPost(SQLModel, table=False):
            id: int = Field(primary_key=True)
            title: str
            content: str

            @query(name="test_posts")
            async def get_all(cls) -> list["TestPost"]:
                return []

        handler = GraphQLHandler(entities=[TestPost])
        formatter = SchemaFormatter(handler)
        info = formatter.get_schema_info()

        # Find TestPost type
        post_type = next((t for t in info["types"] if t["name"] == "TestPost"), None)
        assert post_type is not None

        # Check scalar fields
        scalar_names = [f["name"] for f in post_type["scalar_fields"]]
        assert "id" in scalar_names
        assert "title" in scalar_names
        assert "content" in scalar_names

    def test_query_has_arguments(self) -> None:
        """Test that queries have properly formatted arguments."""
        from typing import Optional

        from sqlmodel import Field, SQLModel

        from sqlmodel_graphql import query
        from sqlmodel_graphql.handler import GraphQLHandler
        from sqlmodel_graphql.mcp.builders.schema_formatter import SchemaFormatter

        class TestItem(SQLModel, table=False):
            id: int = Field(primary_key=True)
            name: str

            @query(name="test_item")
            async def get_by_id(cls, item_id: int) -> Optional["TestItem"]:
                return None

        handler = GraphQLHandler(entities=[TestItem])
        formatter = SchemaFormatter(handler)
        info = formatter.get_schema_info()

        # Find test_item query
        item_query = next(
            (q for q in info["queries"] if q["name"] == "test_item"), None
        )
        assert item_query is not None

        # Check arguments
        arg_names = [a["name"] for a in item_query["arguments"]]
        assert "item_id" in arg_names

        # Check that the argument has a type
        id_arg = next((a for a in item_query["arguments"] if a["name"] == "item_id"), None)
        assert id_arg is not None
        assert "type" in id_arg


class TestMCPServerCreation:
    """Tests for MCP server creation."""

    def test_create_mcp_server_with_test_entities(self) -> None:
        """Test that MCP server can be created with test entities."""
        from sqlmodel import Field, SQLModel

        from sqlmodel_graphql import query
        from sqlmodel_graphql.mcp import create_mcp_server

        class TestEntity(SQLModel, table=False):
            id: int = Field(primary_key=True)
            name: str

            @query(name="test_entities")
            async def get_all(cls) -> list["TestEntity"]:
                return []

        mcp = create_mcp_server(
            entities=[TestEntity],
            name="Test API",
        )

        # Check that server was created
        assert mcp is not None
        assert mcp.name == "Test API"
