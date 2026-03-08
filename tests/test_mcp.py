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

# Check if mcp module is available
try:
    import mcp  # noqa: F401

    HAS_MCP = True
except ImportError:
    HAS_MCP = False


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

        from sqlmodel import Field, SQLModel

        from sqlmodel_graphql import query
        from sqlmodel_graphql.handler import GraphQLHandler
        from sqlmodel_graphql.mcp.builders.schema_formatter import SchemaFormatter

        # Define test base and entity
        class TestBase(SQLModel):
            pass

        class TestUser(TestBase, table=False):
            """Test user entity."""

            id: int = Field(primary_key=True)
            name: str

            @query(name="test_users")
            async def get_all(cls) -> list[TestUser]:
                return []

        handler = GraphQLHandler(base=TestBase)
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

        class TestBase(SQLModel):
            pass

        class TestPost(TestBase, table=False):
            id: int = Field(primary_key=True)
            title: str
            content: str

            @query(name="test_posts")
            async def get_all(cls) -> list[TestPost]:
                return []

        handler = GraphQLHandler(base=TestBase)
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

        from sqlmodel import Field, SQLModel

        from sqlmodel_graphql import query
        from sqlmodel_graphql.handler import GraphQLHandler
        from sqlmodel_graphql.mcp.builders.schema_formatter import SchemaFormatter

        class TestBase(SQLModel):
            pass

        class TestItem(TestBase, table=False):
            id: int = Field(primary_key=True)
            name: str

            @query(name="test_item")
            async def get_by_id(cls, item_id: int) -> TestItem | None:
                return None

        handler = GraphQLHandler(base=TestBase)
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


@pytest.mark.skipif(not HAS_MCP, reason="mcp package not installed")
class TestMCPServerCreation:
    """Tests for MCP server creation."""

    def test_create_mcp_server_with_test_entities(self) -> None:
        """Test that MCP server can be created with test entities."""
        from sqlmodel import Field, SQLModel

        from sqlmodel_graphql import query
        from sqlmodel_graphql.mcp import create_mcp_server

        class TestBase(SQLModel):
            pass

        class TestEntity(TestBase, table=False):
            id: int = Field(primary_key=True)
            name: str

            @query(name="test_entities")
            async def get_all(cls) -> list[TestEntity]:
                return []

        mcp = create_mcp_server(
            base=TestBase,
            name="Test API",
        )

        # Check that server was created
        assert mcp is not None
        assert mcp.name == "Test API"


class TestListOperations:
    """Tests for list_queries and list_mutations tools."""

    def test_list_queries_returns_names_and_descriptions(self) -> None:
        """Test that list_queries returns names and descriptions."""
        from sqlmodel import Field, SQLModel

        from sqlmodel_graphql import query
        from sqlmodel_graphql.handler import GraphQLHandler
        from sqlmodel_graphql.mcp.builders.type_tracer import TypeTracer

        class TestBase(SQLModel):
            pass

        class TestUser(TestBase, table=False):
            id: int = Field(primary_key=True)
            name: str

            @query(name="test_users")
            async def get_all(cls) -> list[TestUser]:
                """Get all test users."""
                return []

        handler = GraphQLHandler(base=TestBase)
        introspection = handler._introspection_generator.generate()
        entity_names = {e.__name__ for e in handler.entities}
        tracer = TypeTracer(introspection, entity_names)

        queries = tracer.list_operation_fields("Query")

        assert len(queries) == 1
        assert queries[0]["name"] == "test_users"
        assert queries[0]["description"] == "Get all test users."

    def test_list_queries_empty_when_no_queries(self) -> None:
        """Test that list_queries returns empty list when no queries."""
        from sqlmodel import SQLModel

        from sqlmodel_graphql.handler import GraphQLHandler
        from sqlmodel_graphql.mcp.builders.type_tracer import TypeTracer

        class TestBase(SQLModel):
            pass

        handler = GraphQLHandler(base=TestBase)
        introspection = handler._introspection_generator.generate()
        entity_names = {e.__name__ for e in handler.entities}
        tracer = TypeTracer(introspection, entity_names)

        queries = tracer.list_operation_fields("Query")

        assert queries == []

    def test_list_mutations_returns_names_and_descriptions(self) -> None:
        """Test that list_mutations returns names and descriptions."""
        from sqlmodel import Field, SQLModel

        from sqlmodel_graphql import mutation
        from sqlmodel_graphql.handler import GraphQLHandler
        from sqlmodel_graphql.mcp.builders.type_tracer import TypeTracer

        class TestBase(SQLModel):
            pass

        class TestUser(TestBase, table=False):
            id: int = Field(primary_key=True)
            name: str

            @mutation(name="create_test_user")
            async def create(cls, name: str) -> TestUser:
                """Create a test user."""
                return TestUser(id=1, name=name)

        handler = GraphQLHandler(base=TestBase)
        introspection = handler._introspection_generator.generate()
        entity_names = {e.__name__ for e in handler.entities}
        tracer = TypeTracer(introspection, entity_names)

        mutations = tracer.list_operation_fields("Mutation")

        assert len(mutations) == 1
        assert mutations[0]["name"] == "create_test_user"


class TestGetOperationSchema:
    """Tests for get_query_schema and get_mutation_schema tools."""

    def test_get_query_schema_returns_operation_info(self) -> None:
        """Test that get_query_schema returns operation info."""
        from sqlmodel import Field, SQLModel

        from sqlmodel_graphql import query
        from sqlmodel_graphql.handler import GraphQLHandler
        from sqlmodel_graphql.mcp.builders.type_tracer import TypeTracer

        class TestBase(SQLModel):
            pass

        class TestUser(TestBase, table=False):
            id: int = Field(primary_key=True)
            name: str

            @query(name="test_user")
            async def get_by_id(cls, user_id: int) -> TestUser | None:
                """Get user by ID."""
                return None

        handler = GraphQLHandler(base=TestBase)
        introspection = handler._introspection_generator.generate()
        entity_names = {e.__name__ for e in handler.entities}
        tracer = TypeTracer(introspection, entity_names)

        operation = tracer.get_operation_field("Query", "test_user")

        assert operation is not None
        assert operation["name"] == "test_user"
        assert len(operation["args"]) == 1
        assert operation["args"][0]["name"] == "user_id"

    def test_get_query_schema_returns_related_types(self) -> None:
        """Test that get_query_schema can collect related types from introspection data."""
        # This test uses manually constructed introspection data to avoid
        # Python's forward reference issues when classes are defined inside methods.
        # See test_type_tracer.py for comprehensive tests of type tracing.
        from sqlmodel_graphql.mcp.builders.type_tracer import TypeTracer

        introspection = {
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

        tracer = TypeTracer(introspection, {"User", "Post"})

        # Get operation and collect related types
        operation = tracer.get_operation_field("Query", "users")
        assert operation is not None

        related_types = tracer.collect_related_types(operation["type"])

        # Should include both User and Post (User -> posts -> Post)
        assert "User" in related_types
        assert "Post" in related_types

    def test_get_query_schema_nonexistent_returns_none(self) -> None:
        """Test that get_query_schema returns None for nonexistent query."""
        from sqlmodel import SQLModel

        from sqlmodel_graphql.handler import GraphQLHandler
        from sqlmodel_graphql.mcp.builders.type_tracer import TypeTracer

        class TestBase(SQLModel):
            pass

        handler = GraphQLHandler(base=TestBase)
        introspection = handler._introspection_generator.generate()
        entity_names = {e.__name__ for e in handler.entities}
        tracer = TypeTracer(introspection, entity_names)

        operation = tracer.get_operation_field("Query", "nonexistent")

        assert operation is None

    def test_get_mutation_schema_returns_operation_info(self) -> None:
        """Test that get_mutation_schema returns operation info."""
        from sqlmodel import Field, SQLModel

        from sqlmodel_graphql import mutation
        from sqlmodel_graphql.handler import GraphQLHandler
        from sqlmodel_graphql.mcp.builders.type_tracer import TypeTracer

        class TestBase(SQLModel):
            pass

        class TestUser(TestBase, table=False):
            id: int = Field(primary_key=True)
            name: str

            @mutation(name="create_test_user")
            async def create(cls, name: str) -> TestUser:
                return TestUser(id=1, name=name)

        handler = GraphQLHandler(base=TestBase)
        introspection = handler._introspection_generator.generate()
        entity_names = {e.__name__ for e in handler.entities}
        tracer = TypeTracer(introspection, entity_names)

        operation = tracer.get_operation_field("Mutation", "create_test_user")

        assert operation is not None
        assert operation["name"] == "create_test_user"

    def test_operation_with_no_arguments(self) -> None:
        """Test operation with no arguments."""
        from sqlmodel import Field, SQLModel

        from sqlmodel_graphql import query
        from sqlmodel_graphql.handler import GraphQLHandler
        from sqlmodel_graphql.mcp.builders.type_tracer import TypeTracer

        class TestBase(SQLModel):
            pass

        class TestUser(TestBase, table=False):
            id: int = Field(primary_key=True)
            name: str

            @query(name="all_test_users")
            async def get_all(cls) -> list[TestUser]:
                return []

        handler = GraphQLHandler(base=TestBase)
        introspection = handler._introspection_generator.generate()
        entity_names = {e.__name__ for e in handler.entities}
        tracer = TypeTracer(introspection, entity_names)

        operation = tracer.get_operation_field("Query", "all_test_users")

        assert operation is not None
        assert operation["args"] == []


class TestThreeLayerProgressiveDisclosure:
    """Integration tests for three-layer progressive disclosure."""

    def test_full_workflow(self) -> None:
        """Test full workflow from list to schema."""
        from sqlmodel import Field, SQLModel

        from sqlmodel_graphql import query
        from sqlmodel_graphql.handler import GraphQLHandler
        from sqlmodel_graphql.mcp.builders.type_tracer import TypeTracer

        class TestBase(SQLModel):
            pass

        class TestUser(TestBase, table=False):
            id: int = Field(primary_key=True)
            name: str

            @query(name="test_users")
            async def get_all(cls, limit: int = 10) -> list["TestUser"]:
                """Get all test users."""
                return []

        handler = GraphQLHandler(base=TestBase)
        introspection = handler._introspection_generator.generate()
        entity_names = {e.__name__ for e in handler.entities}
        tracer = TypeTracer(introspection, entity_names)

        # Layer 1: List queries
        queries = tracer.list_operation_fields("Query")
        assert len(queries) == 1
        assert queries[0]["name"] == "test_users"

        # Layer 2: Get query schema
        operation = tracer.get_operation_field("Query", "test_users")
        assert operation is not None
        assert operation["name"] == "test_users"
        assert operation["description"] == "Get all test users."

        # Note: Due to Python's forward reference limitations when classes are
        # defined inside methods, the return type may not be correctly resolved.
        # The TypeTracer tests in test_type_tracer.py cover the full functionality
        # with properly defined classes.
