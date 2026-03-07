"""GraphQL SDL generator for SQLModel classes."""

from __future__ import annotations

import inspect
from enum import Enum
from typing import TYPE_CHECKING, Any, get_args, get_origin, get_type_hints

from sqlmodel import SQLModel

from sqlmodel_graphql.type_converter import TypeConverter

if TYPE_CHECKING:
    pass


def _python_type_to_graphql(
    python_type: Any, converter: TypeConverter
) -> str:
    """Convert Python type to GraphQL type string."""
    origin = get_origin(python_type)

    # Handle list types
    if origin is list:
        args = get_args(python_type)
        if args:
            inner_type = _python_type_to_graphql_inner(args[0], converter)
            return f"[{inner_type}!]!"
        return "[String!]!"

    # Handle Optional
    if converter.is_optional(python_type):
        inner = converter.unwrap_optional(python_type)
        return _python_type_to_graphql_inner(inner, converter)

    # Non-nullable type
    return _python_type_to_graphql_inner(python_type, converter, nullable=False)


def _python_type_to_graphql_inner(
    python_type: Any, converter: TypeConverter, nullable: bool = True
) -> str:
    """Convert Python type to GraphQL type string (inner, without list wrapper)."""
    # Handle enum types
    if converter.is_enum_type(python_type):
        return python_type.__name__

    # Check if it's an entity type
    entity_name = converter.get_entity_name(python_type)
    if entity_name:
        return f"{entity_name}{'!' if not nullable else ''}"

    # Handle basic Python types
    base_type = converter.get_scalar_type_name(python_type) or "String"
    return f"{base_type}{'!' if not nullable else ''}"


class SDLGenerator:
    """Generates GraphQL SDL from SQLModel classes."""

    def __init__(
        self,
        entities: list[type[SQLModel]],
        query_description: str | None = None,
        mutation_description: str | None = None,
    ):
        """Initialize the SDL generator.

        Args:
            entities: List of SQLModel classes to generate schema for.
            query_description: Optional custom description for Query type.
            mutation_description: Optional custom description for Mutation type.
        """
        self.entities = entities
        self._entity_names = {e.__name__ for e in entities}
        self._converter = TypeConverter(self._entity_names)
        self._query_description = query_description
        self._mutation_description = mutation_description

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
            query_def = f"type Query {{\n{chr(10).join(query_fields)}\n}}"
            if self._query_description:
                query_def = f'"""{self._query_description}"""\n{query_def}'
            parts.append(query_def)

        # 4. Generate Mutation type
        mutation_fields = self._collect_mutation_fields()
        if mutation_fields:
            mutation_def = f"type Mutation {{\n{chr(10).join(mutation_fields)}\n}}"
            if self._mutation_description:
                mutation_def = f'"""{self._mutation_description}"""\n{mutation_def}'
            parts.append(mutation_def)

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
            # Add field description if available
            if field_info.description:
                fields.append(f'  """{field_info.description}"""')
            fields.append(f"  {field_name}: {gql_type}")

        # Get relationship fields from type hints
        hints = get_type_hints(entity)
        for field_name, hint in hints.items():
            if field_name in entity.model_fields:
                continue  # Already processed

            # Check if it's a relationship (references another entity)
            gql_type = self._type_hint_to_graphql(hint)
            if gql_type:
                fields.append(f"  {field_name}: {gql_type}")

        # Build type definition with optional description
        type_def = f"type {entity.__name__} {{\n{chr(10).join(fields)}\n}}"
        if entity.__doc__:
            type_def = f'"""{entity.__doc__}"""\n{type_def}'
        return type_def

    def _field_info_to_graphql(self, field_info: Any) -> str:
        """Convert Pydantic FieldInfo to GraphQL type."""
        annotation = field_info.annotation
        return _python_type_to_graphql(annotation, self._converter)

    def _type_hint_to_graphql(self, hint: Any) -> str | None:
        """Convert type hint to GraphQL type if it's an entity reference."""
        # Unwrap Mapped wrapper if present
        if self._converter.is_mapped_wrapper(hint):
            hint = self._converter.unwrap_mapped(hint)

        origin = get_origin(hint)

        # Handle list of entities
        if origin is list:
            inner = self._converter.get_list_inner_type(hint)
            entity_name = self._converter.get_entity_name(inner)
            if entity_name:
                return f"[{entity_name}!]!"
            return None

        # Handle Optional entity (e.g., Optional[User])
        if self._converter.is_optional(hint):
            inner = self._converter.unwrap_optional(hint)
            entity_name = self._converter.get_entity_name(inner)
            if entity_name:
                return entity_name  # Optional, no !
            return None

        # Handle single entity
        entity_name = self._converter.get_entity_name(hint)
        if entity_name:
            return f"{entity_name}!"

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
            gql_name = func.__name__

        # Get description
        description = getattr(func, "_graphql_query_description", None) or getattr(
            func, "_graphql_mutation_description", None
        )

        # Get type hints from the function's module context
        # Include entity in localns to resolve forward references
        try:
            globalns = getattr(func, "__globals__", {})
            localns = {entity.__name__: entity}
            # Add all known entities to localns for forward reference resolution
            for e in self.entities:
                localns[e.__name__] = e
            hints = get_type_hints(func, globalns=globalns, localns=localns)
        except Exception:
            hints = {}

        # Parse method signature
        sig = inspect.signature(func)
        params: list[str] = []

        for param_name, param in sig.parameters.items():
            if param_name in ("cls", "self", "query_meta"):
                continue

            if param_name in hints:
                gql_type = _python_type_to_graphql(hints[param_name], self._converter)
                # Parameters are nullable by default if they have defaults
                if param.default != inspect.Parameter.empty:
                    # Remove the ! for optional parameters
                    gql_type = gql_type.rstrip("!")
                params.append(f"{param_name}: {gql_type}")
            else:
                params.append(f"{param_name}: String!")

        # Get return type
        return_type = hints.get("return", inspect.Signature.empty)
        if return_type != inspect.Signature.empty:
            return_gql_type = _python_type_to_graphql(return_type, self._converter)
        else:
            return_gql_type = "String!"

        # Build field definition
        param_str = f"({', '.join(params)})" if params else ""
        field_def = f"{gql_name}{param_str}: {return_gql_type}"

        if description:
            field_def = f'"""{description}"""\n  {field_def}'

        return field_def
