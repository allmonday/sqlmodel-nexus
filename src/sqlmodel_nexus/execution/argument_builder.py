"""Argument building for GraphQL field arguments."""

from __future__ import annotations

import inspect
from typing import Any, get_type_hints


class ArgumentBuilder:
    """Builds method arguments from GraphQL field arguments."""

    def _extract_value(self, node: Any) -> Any:
        """Extract Python value from a GraphQL AST value node.

        Args:
            node: A GraphQL ValueNode (StringValueNode, IntValueNode,
                  ListValueNode, ObjectValueNode, etc.)

        Returns:
            The corresponding Python value.
        """
        # Handle list values (ListValueNode)
        if hasattr(node, "values") and node.__class__.__name__ == "ListValueNode":
            return [self._extract_value(v) for v in node.values]

        # Handle object values (ObjectValueNode)
        if hasattr(node, "fields") and node.__class__.__name__ == "ObjectValueNode":
            return {field.name.value: self._extract_value(field.value) for field in node.fields}

        # Handle variable references (VariableNode)
        if hasattr(node, "name") and node.__class__.__name__ == "VariableNode":
            # Variable reference - caller should resolve using variables dict
            return node  # Return the node itself, will be resolved later

        # Handle null value (NullValueNode)
        if node.__class__.__name__ == "NullValueNode":
            return None

        # Handle enum value (EnumValueNode)
        if hasattr(node, "value") and node.__class__.__name__ == "EnumValueNode":
            return node.value

        # Handle simple scalar values (String, Int, Float, Boolean)
        if hasattr(node, "value"):
            return node.value

        # Fallback - return the node itself
        return node

    def _is_input_type(self, python_type: type, entity_names: set[str]) -> bool:
        """Check if a type should be treated as a GraphQL Input type."""
        if not isinstance(python_type, type):
            return False
        # Skip if it's an entity type
        if python_type.__name__ in entity_names:
            return False
        try:
            from pydantic import BaseModel
            from sqlmodel import SQLModel
            if issubclass(python_type, SQLModel) or issubclass(python_type, BaseModel):
                return True
        except TypeError:
            pass
        return False

    def _convert_to_input_model(
        self, value: Any, target_type: type, entity_names: set[str]
    ) -> Any:
        """Convert a dict value to an Input model instance if needed."""
        if not isinstance(value, dict):
            return value
        if not self._is_input_type(target_type, entity_names):
            return value

        # Recursively convert nested dict values
        model_fields = getattr(target_type, "model_fields", {})
        converted = {}
        for key, val in value.items():
            if key in model_fields:
                field_info = model_fields[key]
                field_type = field_info.annotation
                converted[key] = self._convert_to_input_model(val, field_type, entity_names)
            else:
                converted[key] = val

        return target_type(**converted)

    def build_arguments(
        self,
        selection: Any,
        variables: dict[str, Any] | None,
        method: Any,
        entity: type,
        entity_names: set[str] | None = None,
    ) -> dict[str, Any]:
        """Build method arguments from GraphQL field arguments.

        Args:
            selection: GraphQL FieldNode with argument info.
            variables: GraphQL variables dict.
            method: The method to call.
            entity: The SQLModel entity class.
            entity_names: Set of known entity class names.

        Returns:
            Dictionary of argument name to value.
        """
        args: dict[str, Any] = {}
        variables = variables or {}
        entity_names = entity_names or set()

        if not selection.arguments:
            return args

        # Get method signature and type hints
        func = method.__func__ if hasattr(method, "__func__") else method
        sig = inspect.signature(func)

        try:
            hints = get_type_hints(func)
        except Exception:
            hints = {}

        for arg in selection.arguments:
            arg_name = arg.name.value

            # Extract the value using helper method
            value = self._extract_value(arg.value)

            # Handle variable references
            if value.__class__.__name__ == "VariableNode":
                var_name = value.name.value
                value = variables.get(var_name)

            # Use argument name directly
            param_name = arg_name

            # Determine the actual parameter name
            actual_param_name = None
            if param_name in sig.parameters:
                actual_param_name = param_name
            elif arg_name in sig.parameters:
                actual_param_name = arg_name

            if actual_param_name:
                # Convert to Input model if the parameter type is an Input type
                if actual_param_name in hints:
                    param_type = hints[actual_param_name]
                    value = self._convert_to_input_model(value, param_type, entity_names)
                args[actual_param_name] = value

        return args
