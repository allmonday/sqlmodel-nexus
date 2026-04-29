"""Field tree builder for GraphQL selection sets."""

from __future__ import annotations

from typing import Any


class FieldTreeBuilder:
    """Builds field selection trees from GraphQL FieldNodes."""

    def build_field_tree(self, selection: Any) -> dict[str, Any] | None:
        """Build a field selection tree from a GraphQL FieldNode.

        Args:
            selection: GraphQL FieldNode with selection set.

        Returns:
            Dictionary where keys are field names and values are:
            - None: Scalar field
            - {nested_field: ...}: Relationship field
            Returns None if no selection_set.
        """
        if not selection.selection_set:
            return None

        field_tree: dict[str, Any] = {}
        for field in selection.selection_set.selections:
            if hasattr(field, "name"):
                field_name = field.name.value
                if hasattr(field, "selection_set") and field.selection_set:
                    # It's a relationship field - recursively build nested tree
                    field_tree[field_name] = self.build_field_tree(field)
                else:
                    # It's a scalar field
                    field_tree[field_name] = None

        return field_tree
