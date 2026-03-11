"""Argument building for GraphQL field arguments."""

from __future__ import annotations

import inspect
from typing import Any


class ArgumentBuilder:
    """Builds method arguments from GraphQL field arguments."""

    def build_arguments(
        self,
        selection: Any,
        variables: dict[str, Any] | None,
        method: Any,
        entity: type,
    ) -> dict[str, Any]:
        """Build method arguments from GraphQL field arguments.

        Args:
            selection: GraphQL FieldNode with argument info.
            variables: GraphQL variables dict.
            method: The method to call.
            entity: The SQLModel entity class.

        Returns:
            Dictionary of argument name to value.
        """
        args: dict[str, Any] = {}
        variables = variables or {}

        if not selection.arguments:
            return args

        # Get method signature for type info
        func = method.__func__ if hasattr(method, "__func__") else method
        sig = inspect.signature(func)

        for arg in selection.arguments:
            arg_name = arg.name.value

            # Get the value (from literal, list, or variable)
            if hasattr(arg.value, "values"):
                # List value - extract each element
                value = [v.value for v in arg.value.values]
            elif hasattr(arg.value, "value"):
                # Literal value
                value = arg.value.value
            elif hasattr(arg.value, "name"):
                # Variable reference
                var_name = arg.value.name.value
                value = variables.get(var_name)
            else:
                value = arg.value

            # Use argument name directly
            param_name = arg_name

            # Check if this param exists in the method signature
            if param_name in sig.parameters:
                args[param_name] = value
            elif arg_name in sig.parameters:
                args[arg_name] = value

        return args
