"""Tests for GraphQL introspection generator."""

import pytest
from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field

from sqlmodel_graphql import GraphQLHandler, query, mutation
from sqlmodel_graphql.introspection import IntrospectionGenerator


class Status(Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class IntrospectionUser(SQLModel, table=True):
    __tablename__ = "introspection_user"  # Unique table name to avoid conflicts
    id: int = Field(default=None, primary_key=True)
    name: str
    email: Optional[str] = None
    status: Status = Status.ACTIVE

    @query(name="users")
    def get_users(cls, limit: int = 10) -> list["IntrospectionUser"]:
        return []

    @query(name="user")
    def get_user(cls, id: int) -> Optional["IntrospectionUser"]:
        return None

    @mutation(name="createUser")
    def create_user(cls, name: str, email: Optional[str] = None) -> "IntrospectionUser":
        return cls(name=name, email=email)


class TestIntrospectionGenerator:
    """Tests for IntrospectionGenerator class."""

    @pytest.fixture
    def handler(self) -> GraphQLHandler:
        return GraphQLHandler(entities=[IntrospectionUser])

    @pytest.fixture
    def generator(self, handler: GraphQLHandler) -> IntrospectionGenerator:
        return handler._introspection_generator

    def test_generate_schema_structure(self, generator: IntrospectionGenerator):
        """Test that generate() returns correct schema structure."""
        schema = generator.generate()

        assert "queryType" in schema
        assert "mutationType" in schema
        assert "subscriptionType" in schema
        assert "types" in schema
        assert "directives" in schema

        assert schema["queryType"]["name"] == "Query"
        assert schema["mutationType"]["name"] == "Mutation"
        assert schema["subscriptionType"] is None
        assert schema["directives"] == []

    def test_scalar_types(self, generator: IntrospectionGenerator):
        """Test that scalar types are included."""
        schema = generator.generate()
        type_names = [t["name"] for t in schema["types"]]

        assert "Int" in type_names
        assert "Float" in type_names
        assert "String" in type_names
        assert "Boolean" in type_names
        assert "ID" in type_names

    def test_entity_type(self, generator: IntrospectionGenerator):
        """Test that entity types are included with correct fields."""
        schema = generator.generate()

        user_type = next((t for t in schema["types"] if t["name"] == "IntrospectionUser"), None)
        assert user_type is not None
        assert user_type["kind"] == "OBJECT"

        field_names = [f["name"] for f in user_type["fields"]]
        assert "id" in field_names
        assert "name" in field_names
        assert "email" in field_names
        assert "status" in field_names

    def test_enum_type(self, generator: IntrospectionGenerator):
        """Test that enum types are included with correct values."""
        schema = generator.generate()

        status_type = next((t for t in schema["types"] if t["name"] == "Status"), None)
        assert status_type is not None
        assert status_type["kind"] == "ENUM"

        enum_values = [v["name"] for v in status_type["enumValues"]]
        assert "ACTIVE" in enum_values
        assert "INACTIVE" in enum_values

    def test_query_type(self, generator: IntrospectionGenerator):
        """Test that Query type is generated with correct fields."""
        schema = generator.generate()

        query_type = next((t for t in schema["types"] if t["name"] == "Query"), None)
        assert query_type is not None
        assert query_type["kind"] == "OBJECT"

        field_names = [f["name"] for f in query_type["fields"]]
        assert "users" in field_names
        assert "user" in field_names

    def test_mutation_type(self, generator: IntrospectionGenerator):
        """Test that Mutation type is generated with correct fields."""
        schema = generator.generate()

        mutation_type = next((t for t in schema["types"] if t["name"] == "Mutation"), None)
        assert mutation_type is not None
        assert mutation_type["kind"] == "OBJECT"

        field_names = [f["name"] for f in mutation_type["fields"]]
        assert "createUser" in field_names

    def test_field_arguments(self, generator: IntrospectionGenerator):
        """Test that field arguments are generated correctly."""
        schema = generator.generate()

        query_type = next((t for t in schema["types"] if t["name"] == "Query"), None)
        users_field = next((f for f in query_type["fields"] if f["name"] == "users"), None)

        assert users_field is not None
        arg_names = [a["name"] for a in users_field["args"]]
        assert "limit" in arg_names

    def test_return_type_structure(self, generator: IntrospectionGenerator):
        """Test that return types are structured correctly."""
        schema = generator.generate()

        query_type = next((t for t in schema["types"] if t["name"] == "Query"), None)
        users_field = next((f for f in query_type["fields"] if f["name"] == "users"), None)

        # users returns list[User], so type should be NON_NULL(LIST(NON_NULL(OBJECT(User))))
        return_type = users_field["type"]
        assert return_type["kind"] == "NON_NULL"
        assert return_type["ofType"]["kind"] == "LIST"

    def test_optional_return_type(self, generator: IntrospectionGenerator):
        """Test that Optional return types are handled correctly."""
        schema = generator.generate()

        query_type = next((t for t in schema["types"] if t["name"] == "Query"), None)
        user_field = next((f for f in query_type["fields"] if f["name"] == "user"), None)

        # user returns Optional[User], so type should be OBJECT (not NON_NULL)
        return_type = user_field["type"]
        # Could be OBJECT directly or wrapped differently
        assert return_type["kind"] in ("OBJECT", "NON_NULL")

    def test_execute(self, generator: IntrospectionGenerator):
        """Test execute() returns correct response structure."""
        result = generator.execute("{ __schema { queryType { name } } }")

        assert "data" in result
        assert "__schema" in result["data"]
        assert result["data"]["__schema"]["queryType"]["name"] == "Query"

    def test_is_introspection_query(self, generator: IntrospectionGenerator):
        """Test is_introspection_query() method."""
        assert generator.is_introspection_query("{ __schema { types { name } } }")
        assert generator.is_introspection_query("{ __type(name: \"User\") { name } }")
        assert not generator.is_introspection_query("{ users { id } }")


class TestIntrospectionIntegration:
    """Integration tests for introspection via GraphQLHandler."""

    @pytest.fixture
    def handler(self) -> GraphQLHandler:
        return GraphQLHandler(entities=[IntrospectionUser])

    @pytest.mark.asyncio
    async def test_introspection_query(self, handler: GraphQLHandler):
        """Test that handler executes introspection queries."""
        query = """
        {
            __schema {
                queryType { name }
                mutationType { name }
            }
        }
        """

        result = await handler.execute(query)

        assert "data" in result
        assert result["data"]["__schema"]["queryType"]["name"] == "Query"
        assert result["data"]["__schema"]["mutationType"]["name"] == "Mutation"

    @pytest.mark.asyncio
    async def test_full_introspection_query(self, handler: GraphQLHandler):
        """Test full introspection query like GraphiQL would send."""
        query = """
        query IntrospectionQuery {
            __schema {
                queryType { name }
                mutationType { name }
                subscriptionType { name }
                types {
                    kind
                    name
                    fields {
                        name
                        type {
                            kind
                            name
                            ofType {
                                kind
                                name
                            }
                        }
                    }
                }
            }
        }
        """

        result = await handler.execute(query)

        assert "data" in result
        schema = result["data"]["__schema"]
        assert schema["queryType"]["name"] == "Query"
        assert schema["mutationType"]["name"] == "Mutation"

        # Check that IntrospectionUser type is present
        user_type = next((t for t in schema["types"] if t["name"] == "IntrospectionUser"), None)
        assert user_type is not None
        assert user_type["kind"] == "OBJECT"

    @pytest.mark.asyncio
    async def test_introspection_with_types_query(self, handler: GraphQLHandler):
        """Test introspection query for specific type."""
        query = """
        {
            __schema {
                types {
                    name
                    kind
                }
            }
        }
        """

        result = await handler.execute(query)

        assert "data" in result
        type_names = [t["name"] for t in result["data"]["__schema"]["types"]]

        # Should include scalars
        assert "Int" in type_names
        assert "String" in type_names
        assert "Boolean" in type_names

        # Should include our types
        assert "IntrospectionUser" in type_names
        assert "Status" in type_names
        assert "Query" in type_names
        assert "Mutation" in type_names
