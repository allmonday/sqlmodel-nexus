"""Unit tests for MultiAppManager."""

import pytest
from sqlmodel import Field, SQLModel

from sqlmodel_graphql.mcp.managers import AppResources, MultiAppManager
from sqlmodel_graphql.mcp.types.app_config import AppConfig


# Mock models for testing (not test classes)
class MockBaseEntity1(SQLModel):
    """Base entity for mock app 1."""

    pass


class MockUser(MockBaseEntity1, table=True):
    """Mock user entity."""

    id: int | None = Field(default=None, primary_key=True)
    name: str


class MockBaseEntity2(SQLModel):
    """Base entity for mock app 2."""

    pass


class MockProduct(MockBaseEntity2, table=True):
    """Mock product entity."""

    id: int | None = Field(default=None, primary_key=True)
    name: str
    price: float


class TestMultiAppManager:
    """Test cases for MultiAppManager."""

    def test_init_with_single_app(self):
        """Test MultiAppManager initialization with a single app."""
        apps: list[AppConfig] = [
            {
                "name": "test_app",
                "base": MockBaseEntity1,
                "description": "Test application",
            }
        ]

        manager = MultiAppManager(apps)

        assert len(manager.apps) == 1
        assert "test_app" in manager.apps
        assert isinstance(manager.apps["test_app"], AppResources)

    def test_init_with_multiple_apps(self):
        """Test MultiAppManager initialization with multiple apps."""
        apps: list[AppConfig] = [
            {
                "name": "app1",
                "base": MockBaseEntity1,
                "description": "Application 1",
            },
            {
                "name": "app2",
                "base": MockBaseEntity2,
                "description": "Application 2",
            },
        ]

        manager = MultiAppManager(apps)

        assert len(manager.apps) == 2
        assert "app1" in manager.apps
        assert "app2" in manager.apps

    def test_get_app_success(self):
        """Test getting an existing app."""
        apps: list[AppConfig] = [
            {
                "name": "test_app",
                "base": MockBaseEntity1,
                "description": "Test application",
            }
        ]

        manager = MultiAppManager(apps)
        app = manager.get_app("test_app")

        assert app.name == "test_app"
        assert app.description == "Test application"
        assert isinstance(app, AppResources)

    def test_get_app_not_found(self):
        """Test getting a non-existent app raises ValueError."""
        apps: list[AppConfig] = [
            {
                "name": "test_app",
                "base": MockBaseEntity1,
                "description": "Test application",
            }
        ]

        manager = MultiAppManager(apps)

        with pytest.raises(ValueError) as exc_info:
            manager.get_app("nonexistent")

        assert "App 'nonexistent' not found" in str(exc_info.value)
        assert "Available apps: ['test_app']" in str(exc_info.value)

    def test_list_apps_single(self):
        """Test listing apps with a single app."""
        apps: list[AppConfig] = [
            {
                "name": "test_app",
                "base": MockBaseEntity1,
                "description": "Test application",
            }
        ]

        manager = MultiAppManager(apps)
        app_names = manager.list_apps()

        assert app_names == ["test_app"]

    def test_list_apps_multiple(self):
        """Test listing apps with multiple apps."""
        apps: list[AppConfig] = [
            {
                "name": "app1",
                "base": MockBaseEntity1,
                "description": "Application 1",
            },
            {
                "name": "app2",
                "base": MockBaseEntity2,
                "description": "Application 2",
            },
        ]

        manager = MultiAppManager(apps)
        app_names = manager.list_apps()

        assert len(app_names) == 2
        assert "app1" in app_names
        assert "app2" in app_names

    def test_app_resources_have_handler(self):
        """Test that AppResources has a handler."""
        apps: list[AppConfig] = [
            {
                "name": "test_app",
                "base": MockBaseEntity1,
                "description": "Test application",
            }
        ]

        manager = MultiAppManager(apps)
        app = manager.get_app("test_app")

        assert app.handler is not None
        assert hasattr(app.handler, "execute")

    def test_app_resources_have_tracer(self):
        """Test that AppResources has a tracer."""
        apps: list[AppConfig] = [
            {
                "name": "test_app",
                "base": MockBaseEntity1,
                "description": "Test application",
            }
        ]

        manager = MultiAppManager(apps)
        app = manager.get_app("test_app")

        assert app.tracer is not None
        assert hasattr(app.tracer, "list_operation_fields")

    def test_app_resources_have_sdl_generator(self):
        """Test that AppResources has an SDL generator."""
        apps: list[AppConfig] = [
            {
                "name": "test_app",
                "base": MockBaseEntity1,
                "description": "Test application",
            }
        ]

        manager = MultiAppManager(apps)
        app = manager.get_app("test_app")

        assert app.sdl_generator is not None
        assert hasattr(app.sdl_generator, "generate_operation_sdl")

    def test_app_resources_entity_names(self):
        """Test that AppResources returns entity names as a set."""
        apps: list[AppConfig] = [
            {
                "name": "test_app",
                "base": MockBaseEntity1,
                "description": "Test application",
            }
        ]

        manager = MultiAppManager(apps)
        app = manager.get_app("test_app")
        entity_names = app.entity_names

        # Verify that entity_names is a set
        assert isinstance(entity_names, set)
        # The set may be empty if there are no @query decorated entities
        # This is expected behavior

    def test_optional_description(self):
        """Test that description is optional."""
        apps: list[AppConfig] = [
            {
                "name": "test_app",
                "base": MockBaseEntity1,
            }
        ]

        manager = MultiAppManager(apps)
        app = manager.get_app("test_app")

        assert app.description == ""

    def test_custom_descriptions(self):
        """Test custom query and mutation descriptions are passed to handler."""
        apps: list[AppConfig] = [
            {
                "name": "test_app",
                "base": MockBaseEntity1,
                "description": "Test application",
                "query_description": "Custom query description",
                "mutation_description": "Custom mutation description",
            }
        ]

        manager = MultiAppManager(apps)
        app = manager.get_app("test_app")

        assert app.description == "Test application"
        # Verify that the handler was created successfully with custom descriptions
        # The descriptions are passed to the introspection generator and SDL generator
        assert app.handler is not None
