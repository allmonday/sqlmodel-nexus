"""GraphQL query builder for MCP tools.

Converts field paths like ["id", "name", "posts.title"] into proper GraphQL query strings.
"""

from __future__ import annotations

from typing import Any

from sqlmodel_graphql.mcp.types.errors import MCPError, MCPErrors


class GraphQLQueryBuilder:
    """Builds GraphQL query strings from field paths.

    This class converts a list of field paths (using dot notation for nested fields)
    into a properly formatted GraphQL query string.

    Example:
        builder = GraphQLQueryBuilder()
        query = builder.build_query(
            operation_name="users",
            arguments={"limit": 10},
            fields=["id", "name", "posts.title", "posts.author.name"]
        )
        # Result: query { users(limit: 10) { id name posts { title author { name } } } }
    """

    def build_query(
        self,
        operation_name: str,
        arguments: dict[str, Any] | None,
        fields: list[str],
        operation_type: str = "query",
    ) -> str:
        """Build a GraphQL query or mutation string.

        Args:
            operation_name: The name of the GraphQL operation (e.g., "users", "create_user").
            arguments: Optional dictionary of arguments.
            fields: List of field paths using dot notation for nested fields.
            operation_type: "query" or "mutation".

        Returns:
            A formatted GraphQL query string.

        Raises:
            MCPError: If field paths are invalid.
        """
        if not fields:
            raise MCPError(
                MCPErrors.MISSING_REQUIRED_FIELD,
                "At least one field must be specified",
            )

        # Parse field paths into nested structure
        field_tree = self._parse_field_paths(fields)

        # Build the selection set
        selection_set = self._build_selection_set(field_tree)

        # Build arguments string
        args_str = ""
        if arguments:
            args_str = "(" + self._format_arguments(arguments) + ")"

        # Build the full query
        return f"{operation_type} {{ {operation_name}{args_str} {selection_set} }}"

    def _parse_field_paths(self, fields: list[str]) -> dict[str, Any]:
        """Parse field paths into a nested dictionary structure.

        Args:
            fields: List of field paths (e.g., ["id", "posts.title", "posts.author.name"]).

        Returns:
            Nested dictionary where keys are field names and values are nested dicts
            for relationship fields or None for scalar fields.

        Example:
            ["id", "posts.title", "posts.author.name"]
            -> {"id": None, "posts": {"title": None, "author": {"name": None}}}
        """
        result: dict[str, Any] = {}

        for field_path in fields:
            if not field_path or not isinstance(field_path, str):
                raise MCPError(
                    MCPErrors.INVALID_FIELD_PATH,
                    f"Invalid field path: {field_path}",
                )

            # Split by dot to get nested path
            parts = field_path.strip().split(".")
            current = result

            for i, part in enumerate(parts):
                if not part:
                    raise MCPError(
                        MCPErrors.INVALID_FIELD_PATH,
                        f"Invalid field path: {field_path} (empty segment)",
                    )

                if i == len(parts) - 1:
                    # Last part - scalar field
                    current[part] = None
                else:
                    # Not last part - relationship field
                    if part not in current:
                        current[part] = {}
                    elif current[part] is None:
                        # Was marked as scalar, but now has nested fields
                        current[part] = {}
                    current = current[part]

        return result

    def _build_selection_set(self, field_tree: dict[str, Any]) -> str:
        """Build a GraphQL selection set from a field tree.

        Args:
            field_tree: Nested dictionary of fields.

        Returns:
            GraphQL selection set string (e.g., "{ id posts { title } }").
        """
        if not field_tree:
            return ""

        parts: list[str] = []
        for field_name, nested in field_tree.items():
            if nested is None:
                # Scalar field
                parts.append(field_name)
            else:
                # Relationship field with nested selection
                nested_set = self._build_selection_set(nested)
                parts.append(f"{field_name} {nested_set}")

        return "{ " + " ".join(parts) + " }"

    def _format_arguments(self, arguments: dict[str, Any]) -> str:
        """Format arguments dictionary as GraphQL arguments string.

        Args:
            arguments: Dictionary of argument name to value.

        Returns:
            GraphQL arguments string (e.g., "limit: 10, name: \"test\"").
        """
        parts: list[str] = []
        for name, value in arguments.items():
            formatted_value = self._format_value(value)
            parts.append(f"{name}: {formatted_value}")

        return ", ".join(parts)

    def _format_value(self, value: Any) -> str:
        """Format a Python value as a GraphQL literal.

        Args:
            value: The Python value to format.

        Returns:
            GraphQL literal string.
        """
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int | float):
            return str(value)
        if isinstance(value, str):
            # Escape quotes and backslashes in strings
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        if isinstance(value, list):
            items = ", ".join(self._format_value(item) for item in value)
            return f"[{items}]"
        if isinstance(value, dict):
            # GraphQL input object
            items = ", ".join(
                f"{k}: {self._format_value(v)}" for k, v in value.items()
            )
            return "{" + items + "}"

        # Fallback - convert to string
        return str(value)
