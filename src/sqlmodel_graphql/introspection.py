"""GraphQL Introspection generator for SQLModel entities."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING, Any, get_args, get_origin, get_type_hints

from sqlmodel import SQLModel

from sqlmodel_graphql.type_converter import TypeConverter

if TYPE_CHECKING:
    pass


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
        query_description: str | None = None,
        mutation_description: str | None = None,
    ):
        """Initialize the introspection generator.

        Args:
            entities: List of SQLModel classes.
            query_methods: Mapping of field name to (entity, method) for queries.
            mutation_methods: Mapping of field name to (entity, method) for mutations.
            query_description: Optional custom description for Query type.
            mutation_description: Optional custom description for Mutation type.
        """
        self.entities = entities
        self._entity_names = {e.__name__ for e in entities}
        self._query_methods = query_methods
        self._mutation_methods = mutation_methods
        self._query_description = query_description
        self._mutation_description = mutation_description
        # Initialize converter before _collect_enum_types which uses it
        self._converter = TypeConverter(self._entity_names)
        self._enum_types = self._collect_enum_types()
        self._input_types = self._collect_input_types()

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

        # 3. Input types
        for input_type in self._input_types.values():
            types_list.append(self._build_input_type(input_type))

        # 4. Entity types
        for entity in self.entities:
            types_list.append(self._build_entity_type(entity))

        # 5. Query type
        if self._query_methods:
            types_list.append(self._build_query_type())

        # 6. Mutation type
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
        scalar_fields: list[dict] = []
        object_fields: list[dict] = []

        # Collect all fields preserving definition order
        all_fields: list[tuple[str, Any, str | None]] = []

        # Get fields from model_fields
        for field_name, field_info in entity.model_fields.items():
            description = field_info.description
            all_fields.append((field_name, field_info.annotation, description))

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
                all_fields.append((field_name, hint, None))

        # Group fields by type (scalar vs object)
        for field_name, type_hint, description in all_fields:
            field = self._build_field(field_name, type_hint, description)
            if self._is_scalar_field(type_hint):
                scalar_fields.append(field)
            else:
                object_fields.append(field)

        # Combine: scalar fields first, then object fields
        fields = scalar_fields + object_fields

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

    def _is_scalar_field(self, type_hint: Any) -> bool:
        """Check if a field is a scalar type (not an object/relationship)."""
        # Unwrap wrappers (Optional, list, Mapped)
        base_type = self._converter.unwrap_to_base_type(type_hint)

        # Check if it's a scalar or enum
        if self._converter.get_scalar_type_name(base_type):
            return True
        if self._converter.is_enum_type(base_type):
            return True

        return False

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
            "description": self._query_description,
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
            "description": self._mutation_description,
            "fields": fields,
            "inputFields": None,
            "interfaces": [],
            "enumValues": None,
            "possibleTypes": None,
        }

    def _build_method_field(self, field_name: str, method: Callable) -> dict:
        """Build introspection data for a query/mutation field."""
        func = method.__func__ if hasattr(method, "__func__") else method

        # Get description from docstring
        description = func.__doc__.strip() if func.__doc__ else None

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
            # 提取参数默认值
            default_value = None if required else repr(param.default)
            arg = self._build_input_value(
                param_name, type_hint, default_value=default_value, required=required
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

        # Input types
        if hasattr(python_type, "__name__") and python_type.__name__ in self._input_types:
            if required:
                return {
                    "kind": "NON_NULL",
                    "name": None,
                    "ofType": {"kind": "INPUT_OBJECT", "name": python_type.__name__, "ofType": None},
                }
            return {"kind": "INPUT_OBJECT", "name": python_type.__name__, "ofType": None}

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

    def _collect_input_types(self) -> dict[str, type]:
        """Collect all Input types from query and mutation parameters."""
        import types as types_module
        from typing import Union

        from pydantic import BaseModel

        input_types: dict[str, type] = {}
        visited: set[str] = set()

        def get_core_types(python_type: Any) -> list[type]:
            """Extract core types from a type hint."""
            origin = get_origin(python_type)
            if origin is Union or origin is types_module.UnionType:
                args = get_args(python_type)
                result = []
                for arg in args:
                    if arg is not type(None):
                        result.extend(get_core_types(arg))
                return result
            if origin is list:
                args = get_args(python_type)
                if args:
                    return get_core_types(args[0])
                return []
            if isinstance(python_type, type):
                return [python_type]
            return []

        def is_input_type(python_type: type) -> bool:
            """Check if a type should be treated as a GraphQL Input type."""
            if not isinstance(python_type, type):
                return False
            try:
                if issubclass(python_type, SQLModel) or issubclass(python_type, BaseModel):
                    return True
            except TypeError:
                pass
            return False

        def collect_from_type(param_type: Any) -> None:
            """Recursively collect Input types from a type hint."""
            core_types = get_core_types(param_type)
            for core_type in core_types:
                if is_input_type(core_type) and core_type.__name__ not in self._entity_names:
                    type_name = core_type.__name__
                    if type_name not in visited:
                        visited.add(type_name)
                        input_types[type_name] = core_type
                        # Recursively collect nested types
                        try:
                            type_hints = get_type_hints(core_type)
                            for field_type in type_hints.values():
                                collect_from_type(field_type)
                        except Exception:
                            pass

        # Scan all query and mutation methods
        for methods in [self._query_methods, self._mutation_methods]:
            for _, (_, method) in methods.items():
                func = method.__func__ if hasattr(method, "__func__") else method
                sig = inspect.signature(func)
                try:
                    hints = get_type_hints(func)
                except Exception:
                    hints = {}

                for param_name, param in sig.parameters.items():
                    if param_name in ("cls", "self", "query_meta", "return"):
                        continue
                    if param_name in hints:
                        collect_from_type(hints[param_name])

        return input_types

    def _build_input_type(self, input_type: type) -> dict:
        """Build introspection data for an Input type."""
        input_fields: list[dict] = []

        # Get model_fields if available (SQLModel/Pydantic)
        model_fields = getattr(input_type, "model_fields", {})

        for field_name, field_info in model_fields.items():
            if field_name.startswith("_") or field_name == "metadata":
                continue

            field_type = field_info.annotation
            type_ref = self._build_type_ref(field_type, is_input=True, required=True)

            input_fields.append({
                "name": field_name,
                "description": getattr(field_info, "description", None),
                "type": type_ref,
                "defaultValue": None,
            })

        return {
            "kind": "INPUT_OBJECT",
            "name": input_type.__name__,
            "description": input_type.__doc__,
            "fields": None,
            "inputFields": input_fields,
            "interfaces": None,
            "enumValues": None,
            "possibleTypes": None,
        }
