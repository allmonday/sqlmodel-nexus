"""Convert GraphQL introspection data to SDL format.

This module provides functionality to convert GraphQL introspection data
into Schema Definition Language (SDL) format for more compact representation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


class IntrospectionToSDL:
    """Convert GraphQL introspection data to SDL format.

    This class provides methods to convert introspection data for types,
    fields, and operations into SDL format strings.

    Example:
        >>> converter = IntrospectionToSDL()
        >>> sdl = converter.convert_type(type_introspection)
        >>> # Returns: "type User {\\n  id: Int!\\n  name: String!\\n}"
    """

    def format_type_ref(self, type_ref: dict[str, Any] | None) -> str:
        """Format a GraphQL type reference to SDL type notation.

        Args:
            type_ref: A GraphQL type reference from introspection data.

        Returns:
            SDL type notation string (e.g., "String!", "[User!]!", "Int").
        """
        if type_ref is None:
            return "Unknown"

        kind = type_ref.get("kind")
        name = type_ref.get("name")
        of_type = type_ref.get("ofType")

        if kind == "NON_NULL":
            inner = self.format_type_ref(of_type)
            return f"{inner}!"
        elif kind == "LIST":
            inner = self.format_type_ref(of_type)
            return f"[{inner}]"
        elif kind in ("SCALAR", "OBJECT", "INTERFACE", "UNION", "ENUM", "INPUT_OBJECT"):
            return name or "Unknown"
        else:
            return name or "Unknown"

    def format_args(self, args: list[dict[str, Any]]) -> str:
        """Format field arguments to SDL notation.

        Args:
            args: List of argument introspection data.

        Returns:
            SDL arguments string (e.g., "(limit: Int, id: Int!)").
        """
        if not args:
            return ""

        formatted_args = []
        for arg in args:
            arg_name = arg.get("name", "")
            arg_type = self.format_type_ref(arg.get("type"))
            default_value = arg.get("defaultValue")

            if default_value is not None:
                formatted_args.append(f"{arg_name}: {arg_type} = {default_value}")
            else:
                formatted_args.append(f"{arg_name}: {arg_type}")

        return f"({', '.join(formatted_args)})"

    def convert_field(self, field: dict[str, Any]) -> str:
        """Convert a single field to SDL format.

        Args:
            field: Field introspection data.

        Returns:
            SDL field definition string.
        """
        name = field.get("name", "")
        args = self.format_args(field.get("args", []))
        field_type = self.format_type_ref(field.get("type"))

        return f"  {name}{args}: {field_type}"

    def convert_type(self, type_info: dict[str, Any]) -> str:
        """Convert a type definition to SDL format.

        Args:
            type_info: Type introspection data (OBJECT type).

        Returns:
            SDL type definition string.
        """
        name = type_info.get("name", "Unknown")
        description = type_info.get("description")
        fields = type_info.get("fields", [])

        lines = []

        # Add description if present
        if description:
            lines.append(f'"""{description}"""')

        lines.append(f"type {name} {{")

        for field in fields:
            lines.append(self.convert_field(field))

        lines.append("}")

        return "\n".join(lines)

    def convert_operation(
        self,
        operation_info: dict[str, Any],
        operation_type: str = "Query"
    ) -> str:
        """Convert a Query/Mutation field to SDL format.

        Args:
            operation_info: Operation field introspection data.
            operation_type: Either "Query" or "Mutation".

        Returns:
            SDL operation definition string.
        """
        name = operation_info.get("name", "")
        description = operation_info.get("description")
        args = self.format_args(operation_info.get("args", []))
        return_type = self.format_type_ref(operation_info.get("type"))

        lines = []

        # Add description if present
        if description:
            lines.append(f'"""{description}"""')

        lines.append(f"{name}{args}: {return_type}")

        return "\n".join(lines)

    def convert_types(self, types: list[dict[str, Any]]) -> str:
        """Convert multiple type definitions to SDL format.

        Args:
            types: List of type introspection data.

        Returns:
            SDL type definitions string with types separated by blank lines.
        """
        sdl_parts = []
        for type_info in types:
            sdl_parts.append(self.convert_type(type_info))
        return "\n\n".join(sdl_parts)

    def convert_operation_with_types(
        self,
        operation_info: dict[str, Any],
        types: list[dict[str, Any]],
        operation_type: str = "Query"
    ) -> str:
        """Convert an operation with its related types to full SDL format.

        Args:
            operation_info: Operation field introspection data.
            types: List of related type introspection data.
            operation_type: Either "Query" or "Mutation".

        Returns:
            Complete SDL string with operation and all related types.
        """
        parts = []

        # Add operation definition
        operation_sdl = self.convert_operation(operation_info, operation_type)
        parts.append(f"# {operation_type}\n{operation_sdl}")

        # Add related types
        if types:
            types_sdl = self.convert_types(types)
            parts.append(f"# Related Types\n{types_sdl}")

        return "\n\n".join(parts)
