"""GraphQL query parser for extracting QueryMeta from selection sets."""


from __future__ import annotations

from typing import Any

from graphql import FieldNode, OperationDefinitionNode, parse

from sqlmodel_graphql.types import FieldSelection, QueryMeta, RelationshipSelection



class QueryParser:
    """Parses GraphQL queries to extract QueryMeta for query optimization."""

    def __init__(self, entity_field_names: set[str] | None = None):
        """Initialize the parser.

        Args:
            entity_field_names: Set of field names that represent entity types
                               (used to distinguish relationships from scalar fields).
        """
        self.entity_field_names = entity_field_names or set()

    def parse(self, query: str) -> dict[str, QueryMeta]:
        """Parse a GraphQL query and return QueryMeta for each operation.

        Args:
            query: GraphQL query string.

        Returns:
            Dictionary mapping operation name to QueryMeta.
        """
        document = parse(query)
        result: dict[str, QueryMeta] = {}

        for definition in document.definitions:
            if isinstance(definition, OperationDefinitionNode):
                for selection in definition.selection_set.selections:
                    if isinstance(selection, FieldNode):
                        operation_name = selection.name.value
                        if selection.selection_set:
                            meta = self._parse_selection_set(selection.selection_set)
                            result[operation_name] = meta

        return result

    def parse_selection_set(self, selection_set: Any) -> QueryMeta:
        """Parse a GraphQL selection set into QueryMeta.

        Args:
            selection_set: GraphQL selection set node.

        Returns:
            QueryMeta containing field and relationship selections.
        """
        return self._parse_selection_set(selection_set)

    def _parse_selection_set(self, selection_set: Any) -> QueryMeta:
        """Internal method to parse selection set."""
        fields: list[FieldSelection] = []
        relationships: dict[str, RelationshipSelection] = {}

        for selection in selection_set.selections:
            if isinstance(selection, FieldNode):
                field_name = selection.name.value
                alias = selection.alias.value if selection.alias else None

                # Check if this is a relationship (has nested selection_set)
                if selection.selection_set:
                    # It's a relationship - recursively parse
                    nested_meta = self._parse_selection_set(selection.selection_set)
                    relationships[field_name] = RelationshipSelection(
                        name=field_name,
                        fields=nested_meta.fields,
                        relationships=nested_meta.relationships,
                    )
                else:
                    # It's a scalar field
                    fields.append(FieldSelection(name=field_name, alias=alias))

        return QueryMeta(fields=fields, relationships=relationships)
