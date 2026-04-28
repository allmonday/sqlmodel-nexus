"""Query executor using level-by-level DataLoader resolution."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from graphql import FieldNode, OperationDefinitionNode, parse
from sqlmodel import SQLModel

from sqlmodel_graphql.execution.argument_builder import ArgumentBuilder
from sqlmodel_graphql.loader.pagination import PageArgs, PageLoadCommand
from sqlmodel_graphql.query_parser import FieldSelection

if TYPE_CHECKING:
    from sqlmodel_graphql.loader.registry import LoaderRegistry, RelationshipInfo


class QueryExecutor:
    """Executes GraphQL queries using DataLoader for relationship resolution.

    Uses a separate _results dict to store resolved relationship data
    (including paginated results) since SQLAlchemy relationship fields
    cannot hold dict values.

    Execution flow:
    1. Execute root query method → get root entity instances
    2. resolve_relationships: level-by-level batch load via DataLoader
    3. Build response from resolved data
    """

    def __init__(
        self,
        loader_registry: LoaderRegistry,
        enable_pagination: bool = False,
    ):
        self._registry = loader_registry
        self._enable_pagination = enable_pagination
        self._argument_builder = ArgumentBuilder()
        # (id(entity), field_name) -> resolved value
        self._results: dict[tuple[int, str], Any] = {}

    def _store(self, entity: Any, field_name: str, value: Any) -> None:
        """Store resolved relationship value."""
        self._results[(id(entity), field_name)] = value

    def _retrieve(self, entity: Any, field_name: str) -> Any:
        """Retrieve resolved relationship value."""
        return self._results.get((id(entity), field_name))

    async def execute_query(
        self,
        query: str,
        variables: dict[str, Any] | None,
        operation_name: str | None,
        parsed_selections: dict[str, FieldSelection],
        query_methods: dict[str, tuple[type[SQLModel], Any]],
        mutation_methods: dict[str, tuple[type[SQLModel], Any]],
        entities: list[type[SQLModel]],
    ) -> dict[str, Any]:
        """Execute a GraphQL query or mutation."""
        document = parse(query)
        data: dict[str, Any] = {}
        errors: list[dict[str, Any]] = []
        entity_names = {e.__name__ for e in entities}

        # Clear caches for this request
        self._registry.clear_cache()
        self._results.clear()

        for definition in document.definitions:
            if isinstance(definition, OperationDefinitionNode):
                op_type = definition.operation.value

                for selection in definition.selection_set.selections:
                    if isinstance(selection, FieldNode):
                        field_name = selection.name.value

                        try:
                            if op_type == "query":
                                method_info = query_methods.get(field_name)
                            else:
                                method_info = mutation_methods.get(field_name)

                            if method_info is None:
                                op_name = op_type.title()
                                errors.append(
                                    {
                                        "message": (
                                            f"Cannot query field '{field_name}'"
                                            f" on type '{op_name}'"
                                        ),
                                        "path": [field_name],
                                    }
                                )
                                continue

                            entity, method = method_info

                            # Build arguments (no query_meta anymore)
                            args = self._argument_builder.build_arguments(
                                selection, variables, method, entity, entity_names
                            )

                            # Execute the method
                            result = method(**args)
                            if inspect.isawaitable(result):
                                result = await result

                            # Get selection tree
                            field_sel = parsed_selections.get(field_name)

                            # Resolve relationships via DataLoader
                            if field_sel and result is not None:
                                await self._resolve_result(
                                    result, entity, field_sel
                                )

                            # Serialize
                            data[field_name] = self._serialize(
                                result, entity, field_sel
                            )

                        except Exception as e:
                            errors.append(
                                {"message": str(e), "path": [field_name]}
                            )

        response: dict[str, Any] = {}
        if data:
            response["data"] = data
        if errors:
            response["errors"] = errors
        return response

    async def _resolve_result(
        self,
        result: Any,
        entity: type[SQLModel],
        field_sel: FieldSelection,
    ) -> None:
        """Resolve relationships for a query result (single or list)."""
        if result is None:
            return

        if isinstance(result, list):
            await self._resolve_relationships(result, entity, field_sel)
        else:
            await self._resolve_relationships([result], entity, field_sel)

    async def _resolve_relationships(
        self,
        parents: list,
        parent_entity: type[SQLModel],
        field_sel: FieldSelection,
    ) -> None:
        """Level-by-level relationship resolution using DataLoaders."""
        if not parents or not field_sel.sub_fields:
            return

        for field_name, child_sel in field_sel.sub_fields.items():
            if not child_sel.sub_fields:
                rel_info = self._registry.get_relationship(parent_entity, field_name)
                if rel_info is None:
                    continue
                continue

            rel_info = self._registry.get_relationship(parent_entity, field_name)
            if rel_info is None:
                continue

            # Collect FK values
            fk_values = [getattr(p, rel_info.fk_field, None) for p in parents]
            valid_indices = [i for i, fk in enumerate(fk_values) if fk is not None]
            if not valid_indices:
                continue

            valid_parents = [parents[i] for i in valid_indices]
            valid_fks = [fk_values[i] for i in valid_indices]

            if (
                self._enable_pagination
                and rel_info.is_list
                and rel_info.page_loader is not None
            ):
                await self._load_paginated(
                    valid_parents, valid_fks, rel_info, child_sel
                )
            else:
                await self._load_batch(
                    valid_parents, valid_fks, rel_info, child_sel
                )

    async def _load_batch(
        self,
        parents: list,
        fk_values: list,
        rel_info: RelationshipInfo,
        child_sel: FieldSelection,
    ) -> None:
        """Batch load relationship data and recursively resolve nested."""
        loader = self._registry.get_loader(rel_info.loader)
        results = await loader.load_many(fk_values)

        for parent, result in zip(parents, results, strict=True):
            if rel_info.is_list:
                items = result or []
                self._store(parent, rel_info.name, items)
                if items:
                    await self._resolve_relationships(
                        items, rel_info.target_entity, child_sel
                    )
            else:
                self._store(parent, rel_info.name, result)
                if result is not None:
                    await self._resolve_relationships(
                        [result], rel_info.target_entity, child_sel
                    )

    async def _load_paginated(
        self,
        parents: list,
        fk_values: list,
        rel_info: RelationshipInfo,
        child_sel: FieldSelection,
    ) -> None:
        """Load paginated relationship data."""
        page_args = self._extract_page_args(child_sel, rel_info)

        loader = self._registry.get_loader(rel_info.page_loader)
        commands = [
            PageLoadCommand(fk_value=fk, page_args=page_args) for fk in fk_values
        ]
        results = await loader.load_many(commands)

        all_items = []

        for parent, page_result in zip(parents, results, strict=True):
            self._store(parent, rel_info.name, page_result)
            if page_result and page_result.get("items"):
                all_items.extend(page_result["items"])

        # Recursively resolve nested relationships on items
        if all_items and child_sel.sub_fields:
            items_sel = child_sel.sub_fields.get("items")
            if items_sel and items_sel.sub_fields:
                await self._resolve_relationships(
                    all_items, rel_info.target_entity, items_sel
                )

    def _extract_page_args(
        self, field_sel: FieldSelection, rel_info: RelationshipInfo
    ) -> PageArgs:
        """Extract PageArgs from GraphQL field arguments."""
        args = field_sel.arguments or {}
        return PageArgs(
            limit=args.get("limit"),
            offset=args.get("offset", 0),
            default_page_size=rel_info.default_page_size,
            max_page_size=rel_info.max_page_size,
        )

    def _serialize(
        self,
        result: Any,
        entity: type[SQLModel],
        field_sel: FieldSelection | None,
    ) -> Any:
        """Serialize result to JSON-compatible dict."""
        if result is None:
            return None

        if isinstance(result, list):
            return [self._serialize_item(item, entity, field_sel) for item in result]

        return self._serialize_item(result, entity, field_sel)

    def _serialize_item(
        self,
        item: Any,
        entity: type[SQLModel],
        field_sel: FieldSelection | None,
    ) -> dict[str, Any]:
        """Serialize a single entity or page result to dict."""
        if isinstance(item, dict):
            return item

        if not field_sel or not field_sel.sub_fields:
            # Fallback: use model_dump
            if hasattr(item, "model_dump"):
                return self._filter_output(item.model_dump(mode="json"), entity)
            return {"_value": str(item)}

        result = {}
        for field_name, child_sel in field_sel.sub_fields.items():
            rel_info = self._registry.get_relationship(entity, field_name)

            if rel_info is not None:
                value = self._retrieve(item, field_name)
                result[field_name] = self._serialize_relationship_value(
                    value, rel_info, child_sel
                )
            else:
                # Scalar field
                result[field_name] = getattr(item, field_name, None)

        return result

    def _serialize_relationship_value(
        self,
        value: Any,
        rel_info: RelationshipInfo,
        child_sel: FieldSelection,
    ) -> Any:
        """Serialize a relationship value (list, single, or paginated result)."""
        if value is None:
            return None

        if (
            self._enable_pagination
            and rel_info.is_list
            and isinstance(value, dict)
            and "items" in value
        ):
            # Paginated result: { items: [...], pagination: {...} }
            items = value.get("items", [])
            pagination = value.get("pagination")
            # items child_sel is inside child_sel.sub_fields["items"]
            items_sel = child_sel.sub_fields.get("items") if child_sel.sub_fields else None
            serialized_items = [
                self._serialize_entity(v, rel_info.target_entity, items_sel)
                for v in items
            ]
            page_result: dict[str, Any] = {"items": serialized_items}
            # Only include pagination if the user selected it in the query
            wants_pagination = (
                child_sel.sub_fields is not None and "pagination" in child_sel.sub_fields
            )
            if wants_pagination and pagination:
                # Filter pagination fields by user selection
                pag_sel = child_sel.sub_fields.get("pagination")
                pag_fields = (
                    set(pag_sel.sub_fields.keys())
                    if pag_sel and pag_sel.sub_fields
                    else None
                )
                if isinstance(pagination, dict):
                    raw = pagination
                else:
                    raw = pagination.model_dump(mode="json")
                if pag_fields:
                    page_result["pagination"] = {k: v for k, v in raw.items() if k in pag_fields}
                else:
                    page_result["pagination"] = raw
            return page_result

        if isinstance(value, list):
            return [
                self._serialize_entity(v, rel_info.target_entity, child_sel)
                for v in value
            ]

        return self._serialize_entity(value, rel_info.target_entity, child_sel)

    def _serialize_entity(
        self,
        item: Any,
        entity: type[SQLModel],
        field_sel: FieldSelection | None,
    ) -> dict[str, Any] | None:
        """Serialize a single entity with nested fields."""
        if item is None:
            return None
        if isinstance(item, dict):
            return item
        return self._serialize_item(item, entity, field_sel)

    def _filter_output(
        self, data: dict[str, Any], entity: type[SQLModel]
    ) -> dict[str, Any]:
        """Remove FK fields and relationship fields from output dict."""
        fk_fields = self._get_fk_fields(entity)
        relationship_names = self._get_relationship_names(entity)
        excluded = fk_fields | relationship_names | {"metadata"}
        return {k: v for k, v in data.items() if k not in excluded}

    def _get_fk_fields(self, entity: type[SQLModel]) -> set[str]:
        """Get foreign key field names for an entity."""
        fk_fields: set[str] = set()
        for field_name, field_info in entity.model_fields.items():
            if hasattr(field_info, "foreign_key") and isinstance(
                field_info.foreign_key, str
            ):
                fk_fields.add(field_name)
            if hasattr(field_info, "metadata"):
                for meta in field_info.metadata:
                    if hasattr(meta, "foreign_key") and isinstance(
                        meta.foreign_key, str
                    ):
                        fk_fields.add(field_name)
        return fk_fields

    def _get_relationship_names(self, entity: type[SQLModel]) -> set[str]:
        """Get relationship field names for an entity."""
        names: set[str] = set()
        if hasattr(entity, "__sqlmodel_relationships__"):
            names.update(entity.__sqlmodel_relationships__.keys())
        try:
            from sqlalchemy import inspect as sa_inspect

            mapper = sa_inspect(entity)
            if mapper and hasattr(mapper, "relationships"):
                names.update(mapper.relationships.keys())
        except Exception:
            pass
        return names
