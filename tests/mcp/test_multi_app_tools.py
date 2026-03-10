"""Integration tests for multi-app MCP tools."""

import pytest
from sqlmodel import Field, SQLModel

from sqlmodel_graphql import mutation, query

# Skip all tests in this module if mcp is not installed
pytest.importorskip("mcp")

from sqlmodel_graphql.mcp import create_mcp_server  # noqa: E402


# Test models for App 1
class BlogBaseEntity(SQLModel):
    """Base entity for Blog app."""

    pass


class BlogUser(BlogBaseEntity, table=True):
    """Blog user entity."""

    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str

    @query
    @staticmethod
    async def get_blog_users(limit: int = 10) -> list["BlogUser"]:
        """Get blog users."""
        return []

    @mutation
    @staticmethod
    async def create_blog_user(name: str, email: str) -> "BlogUser":
        """Create a blog user."""
        return BlogUser(name=name, email=email)


# Test models for App 2
class ShopBaseEntity(SQLModel):
    """Base entity for Shop app."""

    pass


class ShopProduct(ShopBaseEntity, table=True):
    """Shop product entity."""

    id: int | None = Field(default=None, primary_key=True)
    name: str
    price: float

    @query
    @staticmethod
    async def get_shop_products(limit: int = 10) -> list["ShopProduct"]:
        """Get shop products."""
        return []

    @mutation
    @staticmethod
    async def create_shop_product(name: str, price: float) -> "ShopProduct":
        """Create a shop product."""
        return ShopProduct(name=name, price=price)


@pytest.fixture
def multi_app_mcp():
    """Create a multi-app MCP server for testing."""
    apps = [
        {
            "name": "blog",
            "base": BlogBaseEntity,
            "description": "Blog application",
            "query_description": "Query blog data",
            "mutation_description": "Mutate blog data",
        },
        {
            "name": "shop",
            "base": ShopBaseEntity,
            "description": "Shop application",
            "query_description": "Query shop data",
            "mutation_description": "Mutate shop data",
        },
    ]
    return create_mcp_server(apps=apps, name="Test Multi-App")


class TestMultiAppTools:
    """Integration tests for multi-app MCP tools."""

    def test_server_creation(self, multi_app_mcp):
        """Test that multi-app MCP server is created successfully."""
        assert multi_app_mcp is not None
        assert multi_app_mcp.name == "Test Multi-App"

    @pytest.mark.asyncio
    async def test_list_apps_tool(self, multi_app_mcp):
        """Test list_apps tool returns all configured apps."""
        # Get the tool
        tools = multi_app_mcp._tool_manager._tools
        list_apps_tool = tools.get("list_apps")

        assert list_apps_tool is not None

        # Execute the tool
        result = await list_apps_tool.fn()

        assert result["success"] is True
        assert len(result["data"]) == 2

        # Check app names
        app_names = [app["name"] for app in result["data"]]
        assert "blog" in app_names
        assert "shop" in app_names

        # Check that each app has required fields
        for app in result["data"]:
            assert "name" in app
            assert "description" in app
            assert "queries_count" in app
            assert "mutations_count" in app

    @pytest.mark.asyncio
    async def test_list_queries_with_valid_app(self, multi_app_mcp):
        """Test list_queries tool with a valid app_name."""
        tools = multi_app_mcp._tool_manager._tools
        list_queries_tool = tools.get("list_queries")

        result = await list_queries_tool.fn(app_name="blog")

        assert result["success"] is True
        assert isinstance(result["data"], list)
        assert len(result["data"]) > 0

        # Check that query has required fields
        query = result["data"][0]
        assert "name" in query
        assert "description" in query

    @pytest.mark.asyncio
    async def test_list_queries_with_invalid_app(self, multi_app_mcp):
        """Test list_queries tool with an invalid app_name."""
        tools = multi_app_mcp._tool_manager._tools
        list_queries_tool = tools.get("list_queries")

        result = await list_queries_tool.fn(app_name="nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"]
        assert "error_type" in result

    @pytest.mark.asyncio
    async def test_list_mutations_with_valid_app(self, multi_app_mcp):
        """Test list_mutations tool with a valid app_name."""
        tools = multi_app_mcp._tool_manager._tools
        list_mutations_tool = tools.get("list_mutations")

        result = await list_mutations_tool.fn(app_name="shop")

        assert result["success"] is True
        assert isinstance(result["data"], list)
        assert len(result["data"]) > 0

        # Check that mutation has required fields
        mutation = result["data"][0]
        assert "name" in mutation
        assert "description" in mutation

    @pytest.mark.asyncio
    async def test_list_mutations_with_invalid_app(self, multi_app_mcp):
        """Test list_mutations tool with an invalid app_name."""
        tools = multi_app_mcp._tool_manager._tools
        list_mutations_tool = tools.get("list_mutations")

        result = await list_mutations_tool.fn(app_name="nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_get_query_schema_sdl_format(self, multi_app_mcp):
        """Test get_query_schema tool with SDL format."""
        tools = multi_app_mcp._tool_manager._tools
        get_query_schema_tool = tools.get("get_query_schema")

        # First get the list of queries to find a valid query name
        list_queries_tool = tools.get("list_queries")
        queries_result = await list_queries_tool.fn(app_name="blog")
        query_name = queries_result["data"][0]["name"]

        result = await get_query_schema_tool.fn(
            name=query_name, app_name="blog", response_type="sdl"
        )

        assert result["success"] is True
        assert "sdl" in result["data"]
        assert query_name in result["data"]["sdl"]

    @pytest.mark.asyncio
    async def test_get_query_schema_introspection_format(self, multi_app_mcp):
        """Test get_query_schema tool with introspection format."""
        tools = multi_app_mcp._tool_manager._tools
        get_query_schema_tool = tools.get("get_query_schema")

        # First get the list of queries to find a valid query name
        list_queries_tool = tools.get("list_queries")
        queries_result = await list_queries_tool.fn(app_name="blog")
        query_name = queries_result["data"][0]["name"]

        result = await get_query_schema_tool.fn(
            name=query_name, app_name="blog", response_type="introspection"
        )

        assert result["success"] is True
        assert "operation" in result["data"]
        assert "types" in result["data"]

    @pytest.mark.asyncio
    async def test_get_query_schema_invalid_query(self, multi_app_mcp):
        """Test get_query_schema tool with an invalid query name."""
        tools = multi_app_mcp._tool_manager._tools
        get_query_schema_tool = tools.get("get_query_schema")

        result = await get_query_schema_tool.fn(
            name="nonexistent_query", app_name="blog", response_type="sdl"
        )

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_get_mutation_schema_sdl_format(self, multi_app_mcp):
        """Test get_mutation_schema tool with SDL format."""
        tools = multi_app_mcp._tool_manager._tools
        get_mutation_schema_tool = tools.get("get_mutation_schema")

        # First get the list of mutations to find a valid mutation name
        list_mutations_tool = tools.get("list_mutations")
        mutations_result = await list_mutations_tool.fn(app_name="shop")
        mutation_name = mutations_result["data"][0]["name"]

        result = await get_mutation_schema_tool.fn(
            name=mutation_name, app_name="shop", response_type="sdl"
        )

        assert result["success"] is True
        assert "sdl" in result["data"]
        assert mutation_name in result["data"]["sdl"]

    @pytest.mark.asyncio
    async def test_graphql_query_with_valid_app(self, multi_app_mcp):
        """Test graphql_query tool with a valid app_name."""
        tools = multi_app_mcp._tool_manager._tools
        graphql_query_tool = tools.get("graphql_query")

        result = await graphql_query_tool.fn(
            query="{ __typename }", app_name="blog"
        )

        assert result["success"] is True
        assert result["data"]["__typename"] == "Query"

    @pytest.mark.asyncio
    async def test_graphql_query_with_invalid_app(self, multi_app_mcp):
        """Test graphql_query tool with an invalid app_name."""
        tools = multi_app_mcp._tool_manager._tools
        graphql_query_tool = tools.get("graphql_query")

        result = await graphql_query_tool.fn(
            query="{ __typename }", app_name="nonexistent"
        )

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_graphql_query_empty_query(self, multi_app_mcp):
        """Test graphql_query tool with an empty query."""
        tools = multi_app_mcp._tool_manager._tools
        graphql_query_tool = tools.get("graphql_query")

        result = await graphql_query_tool.fn(query="", app_name="blog")

        assert result["success"] is False
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_graphql_mutation_with_valid_app(self, multi_app_mcp):
        """Test graphql_mutation tool with a valid app_name."""
        tools = multi_app_mcp._tool_manager._tools
        graphql_mutation_tool = tools.get("graphql_mutation")

        result = await graphql_mutation_tool.fn(
            query="{ __typename }", app_name="shop"
        )

        assert result["success"] is True
        assert result["data"]["__typename"] == "Mutation"

    @pytest.mark.asyncio
    async def test_graphql_mutation_with_invalid_app(self, multi_app_mcp):
        """Test graphql_mutation tool with an invalid app_name."""
        tools = multi_app_mcp._tool_manager._tools
        graphql_mutation_tool = tools.get("graphql_mutation")

        result = await graphql_mutation_tool.fn(
            query="{ __typename }", app_name="nonexistent"
        )

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_graphql_mutation_empty_mutation(self, multi_app_mcp):
        """Test graphql_mutation tool with an empty mutation."""
        tools = multi_app_mcp._tool_manager._tools
        graphql_mutation_tool = tools.get("graphql_mutation")

        result = await graphql_mutation_tool.fn(query="", app_name="shop")

        assert result["success"] is False
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_apps_are_isolated(self, multi_app_mcp):
        """Test that queries to different apps return different schemas."""
        tools = multi_app_mcp._tool_manager._tools

        # Get queries from blog app
        list_queries_tool = tools.get("list_queries")
        blog_queries = await list_queries_tool.fn(app_name="blog")

        # Get queries from shop app
        shop_queries = await list_queries_tool.fn(app_name="shop")

        # They should have different queries
        blog_query_names = [q["name"] for q in blog_queries["data"]]
        shop_query_names = [q["name"] for q in shop_queries["data"]]

        # Blog should have blog-related queries
        assert any("blog" in name.lower() for name in blog_query_names)

        # Shop should have shop-related queries
        assert any("shop" in name.lower() for name in shop_query_names)

        # They should not share the same queries
        assert blog_query_names != shop_query_names
