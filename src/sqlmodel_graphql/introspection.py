"""GraphQL Introspection generator for SQLModel entities."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING, Any, get_type_hints

from sqlmodel_graphql.type_converter import TypeConverter

if TYPE_CHECKING:
    from sqlmodel import SQLModel


class IntrospectionGenerator:
    """Generates GraphQL introspection data directly without using graphql-core.

    This class builds introspection response dictionaries that can be used
    to answer __schema and __type queries.
    """

    def __init__(
        self,
        entities: list[type[SQLModel]],
        query_methods: dict[str, tuple[type[SQLModel], Callable]],
        mutation_methods: dict[str, tuple[type[SQLModel], Callable]],
    ):
        """Initialize the introspection generator.

        Args:
            entities: List of SQLModel classes.
            query_methods: Mapping of field name to (entity, method) for queries.
            mutation_methods: Mapping of field name to (entity, method) for mutations.
        """
        self.entities = entities
        self._entity_names = {e.__name__ for e in entities}
        self._query_methods = query_methods
        self._mutation_methods = mutation_methods
        # Initialize converter before _collect_enum_types which uses it
        self._converter = TypeConverter(self._entity_names)
        self._enum_types = self._collect_enum_types()

    def generate(self) -> dict[str, Any]:
        """Generate complete __schema introspection data."""
        types_list = self._get_all_types()

        query_type = {"name": "Query", "kind": "OBJECT"} if self._query_methods else None
        mutation_type = (
            {"name": "Mutation", "kind": "OBJECT"} if self._mutation_methods else None
        )

        return {
            "queryType": query_type,
            "mutationType": mutation_type,
            "subscriptionType": None,
            "types": types_list,
            "directives": [],
        }

    def execute(self, query: str) -> dict[str, Any]:
        """Execute an introspection query and return the response.

        Args:
            query: GraphQL introspection query string.

        Returns:
            Dictionary with 'data' key containing introspection results.
        """
        # For simplicity, we always return the full schema
        # Real introspection queries can filter specific fields, but most
        # clients request the full schema anyway
        return {"data": {"__schema": self.generate()}}

    def is_introspection_query(self, query: str) -> bool:
        """Check if the query is an introspection query."""
        return "__schema" in query or "__type" in query

    def _get_all_types(self) -> list[dict]:
        """Get all types in the schema."""
        types_list: list[dict] = []

        # 1. Built-in scalar types
        types_list.extend(self._build_scalar_types())

        # 2. Enum types
        for enum_class in self._enum_types.values():
            types_list.append(self._build_enum_type(enum_class))

        # 3. Entity types
        for entity in self.entities:
            types_list.append(self._build_entity_type(entity))

        # 4. Query type
        if self._query_methods:
            types_list.append(self._build_query_type())

        # 5. Mutation type
        if self._mutation_methods:
            types_list.append(self._build_mutation_type())

        return types_list

    def _build_scalar_types(self) -> list[dict]:
        """Build introspection data for built-in scalar types."""
        scalars = ["Int", "Float", "String", "Boolean", "ID"]
        return [
            {
                "kind": "SCALAR",
                "name": name,
                "description": f"Built-in {name} scalar",
                "fields": None,
                "inputFields": None,
                "interfaces": [],
                "enumValues": None,
                "possibleTypes": None,
            }
            for name in scalars
        ]

    def _build_entity_type(self, entity: type[SQLModel]) -> dict:
        """Build introspection data for an entity type."""
        fields: list[dict] = []

        # Get scalar fields from model_fields
        for field_name, field_info in entity.model_fields.items():
            field = self._build_field(field_name, field_info.annotation)
            fields.append(field)

        # Get relationship fields from type hints (only entity references)
        try:
            hints = get_type_hints(entity)
        except Exception:
            hints = {}

        for field_name, hint in hints.items():
            if field_name in entity.model_fields:
                continue  # Already processed

            # Only include if it's a relationship to another entity
            if self._is_entity_relationship(hint):
                field = self._build_field(field_name, hint)
                fields.append(field)

        return {
            "kind": "OBJECT",
            "name": entity.__name__,
            "description": None,
            "fields": fields,
            "inputFields": None,
            "interfaces": [],
            "enumValues": None,
            "possibleTypes": None,
        }

    def _is_entity_relationship(self, hint: Any) -> bool:
        """Check if a type hint represents a relationship to another entity."""
        return self._converter.is_relationship(hint)

    def _build_enum_type(self, enum_class: type[Enum]) -> dict:
        """Build introspection data for an enum type."""
        enum_values = [
            {
                "name": v.value,
                "description": None,
                "isDeprecated": False,
                "deprecationReason": None,
            }
            for v in enum_class
        ]

        return {
            "kind": "ENUM",
            "name": enum_class.__name__,
            "description": None,
            "fields": None,
            "inputFields": None,
            "interfaces": None,
            "enumValues": enum_values,
            "possibleTypes": None,
        }

    def _build_query_type(self) -> dict:
        """Build introspection data for the Query type."""
        fields: list[dict] = []

        for field_name, (_entity, method) in self._query_methods.items():
            field = self._build_method_field(field_name, method)
            fields.append(field)

        return {
            "kind": "OBJECT",
            "name": "Query",
            "description": "The query root of this GraphQL API.",
            "fields": fields,
            "inputFields": None,
            "interfaces": [],
            "enumValues": None,
            "possibleTypes": None,
        }

    def _build_mutation_type(self) -> dict:
        """Build introspection data for the Mutation type."""
        fields: list[dict] = []

        for field_name, (_entity, method) in self._mutation_methods.items():
            field = self._build_method_field(field_name, method)
            fields.append(field)

        return {
            "kind": "OBJECT",
            "name": "Mutation",
            "description": "The mutation root of this GraphQL API.",
            "fields": fields,
            "inputFields": None,
            "interfaces": [],
            "enumValues": None,
            "possibleTypes": None,
        }

    def _build_method_field(self, field_name: str, method: Callable) -> dict:
        """Build introspection data for a query/mutation field."""
        func = method.__func__ if hasattr(method, "__func__") else method

        # Get description from decorator
        description = getattr(func, "_graphql_query_description", None) or getattr(
            func, "_graphql_mutation_description", None
        )

        # Get type hints
        try:
            hints = get_type_hints(func)
        except Exception:
            hints = {}

        # Build return type
        return_type = hints.get("return")
        type_ref = self._build_type_ref(return_type, is_input=False, required=True)

        # Build arguments
        args: list[dict] = []
        sig = inspect.signature(func)

        for param_name, param in sig.parameters.items():
            if param_name in ("cls", "self", "query_meta", "return"):
                continue

            type_hint = hints.get(param_name)
            required = param.default == inspect.Parameter.empty
            arg = self._build_input_value(
                param_name, type_hint, default_value=None, required=required
            )
            args.append(arg)

        return {
            "name": field_name,
            "description": description,
            "args": args,
            "type": type_ref,
            "isDeprecated": False,
            "deprecationReason": None,
        }

    def _build_type_ref(
        self, python_type: Any, is_input: bool = False, required: bool = True
    ) -> dict:
        """Build a type reference, handling LIST and NON_NULL wrappers."""
        if python_type is None:
            return {"kind": "SCALAR", "name": "String", "ofType": None}

        # Unwrap Mapped wrapper if present
        if self._converter.is_mapped_wrapper(python_type):
            python_type = self._converter.unwrap_mapped(python_type)

        # Optional[T] -> required=False
        if self._converter.is_optional(python_type):
            inner = self._converter.unwrap_optional(python_type)
            return self._build_type_ref(inner, is_input, required=False)

        # list[T] -> LIST wrapper
        if self._converter.is_list_type(python_type):
            inner = self._converter.get_list_inner_type(python_type)
            inner_ref = self._build_type_ref(inner, is_input, required=True)

            list_ref = {"kind": "LIST", "name": None, "ofType": inner_ref}
            if required:
                return {"kind": "NON_NULL", "name": None, "ofType": list_ref}
            return list_ref

        # Scalar types
        scalar_name = self._converter.get_scalar_type_name(python_type)
        if scalar_name:
            if required:
                return {
                    "kind": "NON_NULL",
                    "name": None,
                    "ofType": {"kind": "SCALAR", "name": scalar_name, "ofType": None},
                }
            return {"kind": "SCALAR", "name": scalar_name, "ofType": None}

        # Enum types
        if self._converter.is_enum_type(python_type):
            if required:
                return {
                    "kind": "NON_NULL",
                    "name": None,
                    "ofType": {"kind": "ENUM", "name": python_type.__name__, "ofType": None},
                }
            return {"kind": "ENUM", "name": python_type.__name__, "ofType": None}

        # Entity types
        entity_name = self._converter.get_entity_name(python_type)
        if entity_name:
            if required:
                return {
                    "kind": "NON_NULL",
                    "name": None,
                    "ofType": {"kind": "OBJECT", "name": entity_name, "ofType": None},
                }
            return {"kind": "OBJECT", "name": entity_name, "ofType": None}

        # Default to String
        if required:
            return {
                "kind": "NON_NULL",
                "name": None,
                "ofType": {"kind": "SCALAR", "name": "String", "ofType": None},
            }
        return {"kind": "SCALAR", "name": "String", "ofType": None}

    def _build_field(
        self, name: str, python_type: Any, description: str | None = None
    ) -> dict:
        """Build introspection data for a field."""
        # Check if the type is optional (should not be NON_NULL)
        required = not self._converter.is_optional(python_type)
        type_ref = self._build_type_ref(python_type, is_input=False, required=required)

        return {
            "name": name,
            "description": description,
            "args": [],
            "type": type_ref,
            "isDeprecated": False,
            "deprecationReason": None,
        }

    def _build_input_value(
        self,
        name: str,
        python_type: Any,
        default_value: Any = None,
        required: bool = True,
    ) -> dict:
        """Build introspection data for an input value (argument)."""
        type_ref = self._build_type_ref(python_type, is_input=True, required=required)

        return {
            "name": name,
            "description": None,
            "type": type_ref,
            "defaultValue": default_value,
        }

    def _collect_enum_types(self) -> dict[str, type[Enum]]:
        """Collect all enum types used in entities."""
        enums: dict[str, type[Enum]] = {}

        for entity in self.entities:
            try:
                hints = get_type_hints(entity)
            except Exception:
                continue

            for field_type in hints.values():
                # Unwrap to base type (handles Optional, list, Mapped)
                base_type = self._converter.unwrap_to_base_type(field_type)

                # Check if it's an enum
                if self._converter.is_enum_type(base_type):
                    enums[base_type.__name__] = base_type

        # Also collect enums from query/mutation method signatures
        for methods in [self._query_methods, self._mutation_methods]:
            for _, (_, method) in methods.items():
                func = method.__func__ if hasattr(method, "__func__") else method
                try:
                    hints = get_type_hints(func)
                except Exception:
                    continue

                for hint in hints.values():
                    if self._converter.is_enum_type(hint):
                        enums[hint.__name__] = hint

        return enums
