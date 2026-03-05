"""GraphQL SDL generator for SQLModel classes."""

from __future__ import annotations

import inspect
from enum import Enum
from typing import TYPE_CHECKING, Any, Union, get_args, get_origin, get_type_hints

from sqlmodel import SQLModel

if TYPE_CHECKING:
    pass


def _to_camel_case(name: str) -> str:
    """Convert snake_case to camelCase."""
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def _is_optional(type_hint: Any) -> bool:
    """Check if a type hint is Optional (Union with None)."""
    origin = get_origin(type_hint)
    if origin is Union:
        args = get_args(type_hint)
        return type(None) in args
    return False


def _unwrap_optional(type_hint: Any) -> Any:
    """Unwrap Optional to get the inner type."""
    origin = get_origin(type_hint)
    if origin is Union:
        args = get_args(type_hint)
        non_none_args = [a for a in args if a is not type(None)]
        return non_none_args[0] if non_none_args else type_hint
    return type_hint


def _python_type_to_graphql(python_type: Any, entities: list[type[SQLModel]]) -> str:
    """Convert Python type to GraphQL type string."""
    origin = get_origin(python_type)

    # Handle list types
    if origin is list:
        args = get_args(python_type)
        if args:
            inner_type = _python_type_to_graphql_inner(args[0], entities)
            return f"[{inner_type}!]!"
        return "[String!]!"

    # Handle Optional
    if _is_optional(python_type):
        inner = _unwrap_optional(python_type)
        return _python_type_to_graphql_inner(inner, entities)

    # Non-nullable type
    return _python_type_to_graphql_inner(python_type, entities, nullable=False)


def _python_type_to_graphql_inner(
    python_type: Any, entities: list[type[SQLModel]], nullable: bool = True
) -> str:
    """Convert Python type to GraphQL type string (inner, without list wrapper)."""
    # Handle enum types
    if isinstance(python_type, type) and issubclass(python_type, Enum):
        return python_type.__name__

    # Check if it's an entity type
    for entity in entities:
        if python_type is entity or (
            isinstance(python_type, type) and issubclass(python_type, entity)
        ):
            return f"{python_type.__name__}{'!' if not nullable else ''}"

    # Handle basic Python types
    type_map: dict[Any, str] = {
        int: "Int",
        str: "String",
        bool: "Boolean",
        float: "Float",
    }

    base_type = type_map.get(python_type, "String")
    return f"{base_type}{'!' if not nullable else ''}"


class SDLGenerator:
    """Generates GraphQL SDL from SQLModel classes."""

    def __init__(self, entities: list[type[SQLModel]]):
        """Initialize the SDL generator.

        Args:
            entities: List of SQLModel classes to generate schema for.
        """
        self.entities = entities
        self._entity_names = {e.__name__ for e in entities}

    def generate(self) -> str:
        """Generate complete GraphQL SDL string."""
        parts = []

        # 1. Generate enum types
        enum_defs = self._generate_enums()
        parts.extend(enum_defs)

        # 2. Generate entity types
        for entity in self.entities:
            parts.append(self._generate_type(entity))

        # 3. Generate Query type
        query_fields = self._collect_query_fields()
        if query_fields:
            parts.append(f"type Query {{\n{chr(10).join(query_fields)}\n}}")

        # 4. Generate Mutation type
        mutation_fields = self._collect_mutation_fields()
        if mutation_fields:
            parts.append(f"type Mutation {{\n{chr(10).join(mutation_fields)}\n}}")

        return "\n\n".join(parts)

    def _generate_enums(self) -> list[str]:
        """Generate GraphQL enum types from Python enums used in entities."""
        enums: dict[str, type[Enum]] = {}

        for entity in self.entities:
            hints = get_type_hints(entity)
            for field_type in hints.values():
                if isinstance(field_type, type) and issubclass(field_type, Enum):
                    enums[field_type.__name__] = field_type

        result = []
        for enum_name, enum_class in enums.items():
            values = "\n".join(f"  {v.value}" for v in enum_class)
            result.append(f"enum {enum_name} {{\n{values}\n}}")

        return result

    def _generate_type(self, entity: type[SQLModel]) -> str:
        """Generate GraphQL type definition from SQLModel class."""
        fields: list[str] = []

        # Get scalar fields from model_fields
        for field_name, field_info in entity.model_fields.items():
            gql_type = self._field_info_to_graphql(field_info)
            camel_name = _to_camel_case(field_name)
            fields.append(f"  {camel_name}: {gql_type}")

        # Get relationship fields from type hints
        hints = get_type_hints(entity)
        for field_name, hint in hints.items():
            if field_name in entity.model_fields:
                continue  # Already processed

            # Check if it's a relationship (references another entity)
            gql_type = self._type_hint_to_graphql(hint)
            if gql_type:
                camel_name = _to_camel_case(field_name)
                fields.append(f"  {camel_name}: {gql_type}")

        return f"type {entity.__name__} {{\n{chr(10).join(fields)}\n}}"

    def _field_info_to_graphql(self, field_info: Any) -> str:
        """Convert Pydantic FieldInfo to GraphQL type."""
        annotation = field_info.annotation
        return _python_type_to_graphql(annotation, self.entities)

    def _type_hint_to_graphql(self, hint: Any) -> str | None:
        """Convert type hint to GraphQL type if it's an entity reference."""
        origin = get_origin(hint)

        # Handle list of entities
        if origin is list:
            args = get_args(hint)
            if args:
                inner = args[0]
                if isinstance(inner, str):
                    # Forward reference
                    return f"[{inner}!]!"
                if inner.__name__ in self._entity_names:
                    return f"[{inner.__name__}!]!"
            return None

        # Handle single entity
        if isinstance(hint, type) and hint.__name__ in self._entity_names:
            return f"{hint.__name__}!"

        return None

    def _collect_query_fields(self) -> list[str]:
        """Collect @query methods from all entities."""
        fields: list[str] = []

        for entity in self.entities:
            for name in dir(entity):
                try:
                    attr = getattr(entity, name)
                    if callable(attr) and hasattr(attr, "_graphql_query"):
                        field_def = self._method_to_graphql_field(attr, entity)
                        fields.append(f"  {field_def}")
                except Exception:
                    continue

        return fields

    def _collect_mutation_fields(self) -> list[str]:
        """Collect @mutation methods from all entities."""
        fields: list[str] = []

        for entity in self.entities:
            for name in dir(entity):
                try:
                    attr = getattr(entity, name)
                    if callable(attr) and hasattr(attr, "_graphql_mutation"):
                        field_def = self._method_to_graphql_field(attr, entity)
                        fields.append(f"  {field_def}")
                except Exception:
                    continue

        return fields

    def _method_to_graphql_field(self, method: Any, entity: type[SQLModel]) -> str:
        """Convert a method to GraphQL field definition."""
        # Get the underlying function from classmethod
        func = method.__func__ if hasattr(method, "__func__") else method

        # Get GraphQL name
        gql_name = getattr(func, "_graphql_query_name", None) or getattr(
            func, "_graphql_mutation_name", None
        )
        if gql_name is None:
            gql_name = _to_camel_case(func.__name__)

        # Get description
        description = getattr(func, "_graphql_query_description", None) or getattr(
            func, "_graphql_mutation_description", None
        )

        # Get type hints from the function's module context
        try:
            hints = get_type_hints(func)
        except Exception:
            hints = {}

        # Parse method signature
        sig = inspect.signature(func)
        params: list[str] = []

        for param_name, param in sig.parameters.items():
            if param_name in ("cls", "self", "query_meta"):
                continue

            if param_name in hints:
                gql_type = _python_type_to_graphql(hints[param_name], self.entities)
                # Parameters are nullable by default if they have defaults
                if param.default != inspect.Parameter.empty:
                    # Remove the ! for optional parameters
                    gql_type = gql_type.rstrip("!")
                params.append(f"{_to_camel_case(param_name)}: {gql_type}")
            else:
                params.append(f"{_to_camel_case(param_name)}: String!")

        # Get return type
        return_type = hints.get("return", inspect.Signature.empty)
        if return_type != inspect.Signature.empty:
            return_gql_type = _python_type_to_graphql(return_type, self.entities)
        else:
            return_gql_type = "String!"

        # Build field definition
        param_str = f"({', '.join(params)})" if params else ""
        field_def = f"{gql_name}{param_str}: {return_gql_type}"

        if description:
            field_def = f'"""{description}"""\n  {field_def}'

        return field_def
