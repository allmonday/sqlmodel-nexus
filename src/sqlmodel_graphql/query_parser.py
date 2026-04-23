"""GraphQL query parser for extracting selection trees and arguments."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from graphql import FieldNode, OperationDefinitionNode, parse


@dataclass
class FieldSelection:
    """Represents a selected field with its nested selections and arguments.

    Attributes:
        name: The field name as defined in the SQLModel.
        alias: Optional GraphQL alias for the field.
        arguments: Dict of argument name -> value from GraphQL query.
        sub_fields: Dict of child field name -> FieldSelection for nested selections.
    """

    name: str = ""
    alias: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    sub_fields: dict[str, FieldSelection] = field(default_factory=dict)


class QueryParser:
    """Parses GraphQL queries to extract field selections and arguments."""

    def __init__(self, entity_field_names: set[str] | None = None):
        """Initialize the parser.

        Args:
            entity_field_names: Set of field names that represent entity types
                               (used to distinguish relationships from scalar fields).
        """
        self.entity_field_names = entity_field_names or set()

    def parse(self, query: str) -> dict[str, FieldSelection]:
        """Parse a GraphQL query and return FieldSelection for each operation.

        Args:
            query: GraphQL query string.

        Returns:
            Dictionary mapping operation name to FieldSelection.
        """
        document = parse(query)
        result: dict[str, FieldSelection] = {}

        for definition in document.definitions:
            if isinstance(definition, OperationDefinitionNode):
                for selection in definition.selection_set.selections:
                    if isinstance(selection, FieldNode):
                        operation_name = selection.name.value
                        if selection.selection_set:
                            meta = self._parse_selection_set(selection.selection_set)
                            result[operation_name] = meta

        return result

    def _parse_selection_set(self, selection_set: Any) -> FieldSelection:
        """Internal method to parse selection set into FieldSelection."""
        sub_fields: dict[str, FieldSelection] = {}

        for selection in selection_set.selections:
            if isinstance(selection, FieldNode):
                field_name = selection.name.value
                alias = selection.alias.value if selection.alias else None
                arguments = self._extract_arguments(selection)

                if selection.selection_set:
                    nested = self._parse_selection_set(selection.selection_set)
                    nested.name = field_name
                    nested.alias = alias
                    nested.arguments = arguments
                    sub_fields[field_name] = nested
                else:
                    sub_fields[field_name] = FieldSelection(
                        name=field_name,
                        alias=alias,
                        arguments=arguments,
                    )

        return FieldSelection(sub_fields=sub_fields)

    def _extract_arguments(self, field_node: FieldNode) -> dict[str, Any]:
        """Extract arguments from a FieldNode into a dict."""
        args: dict[str, Any] = {}
        if not field_node.arguments:
            return args

        for arg in field_node.arguments:
            args[arg.name.value] = self._value_node_to_python(arg.value)

        return args

    def _value_node_to_python(self, value_node: Any) -> Any:
        """Convert a GraphQL ValueNode to a Python value."""
        from graphql import (
            BooleanValueNode,
            EnumValueNode,
            FloatValueNode,
            IntValueNode,
            ListValueNode,
            NullValueNode,
            ObjectValueNode,
            StringValueNode,
        )

        if isinstance(value_node, IntValueNode):
            return int(value_node.value)
        elif isinstance(value_node, FloatValueNode):
            return float(value_node.value)
        elif isinstance(value_node, StringValueNode):
            return value_node.value
        elif isinstance(value_node, BooleanValueNode):
            return value_node.value
        elif isinstance(value_node, NullValueNode):
            return None
        elif isinstance(value_node, EnumValueNode):
            return value_node.value
        elif isinstance(value_node, ListValueNode):
            return [self._value_node_to_python(v) for v in value_node.values]
        elif isinstance(value_node, ObjectValueNode):
            return {
                f.name.value: self._value_node_to_python(f.value)
                for f in value_node.fields
            }
        return str(value_node.value) if hasattr(value_node, "value") else None
