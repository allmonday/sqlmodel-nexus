"""Graph filtering utilities.

Migrated from fastapi-voyager.
"""
from __future__ import annotations

from collections import deque

from sqlmodel_nexus.voyager.type import PK, Link, Route, SchemaNode, Tag


def filter_graph(
    *,
    schema: str | None,
    schema_field: str | None,
    tags: list[Tag],
    routes: list[Route],
    nodes: list[SchemaNode],
    links: list[Link],
    node_set: dict[str, SchemaNode],
) -> tuple[list[Tag], list[Route], list[SchemaNode], list[Link]]:
    """Filter tags, routes, schema nodes and links based on a target schema and optional field."""
    if schema is None:
        return tags, routes, nodes, links

    seed_node_ids = {n.id for n in nodes if n.id == schema}
    if not seed_node_ids:
        return tags, routes, nodes, links

    if schema_field:
        current_targets = set(seed_node_ids)
        accepted_targets = set(seed_node_ids)
        accepted_links: list[Link] = []
        parent_subset_links = [lk for lk in links if lk.type in ("parent", "subset")]
        other_links = [lk for lk in links if lk.type not in ("parent", "subset")]

        while current_targets:
            next_targets: set[str] = set()
            for lk in parent_subset_links:
                if (
                    lk.target_origin in current_targets
                    and lk.source_origin not in accepted_targets
                    and lk.source_origin in node_set
                    and lk.target_origin in node_set
                ):
                    src_node = node_set.get(lk.source_origin)
                    if src_node and any(f.name == schema_field for f in src_node.fields):
                        accepted_links.append(lk)
                        next_targets.add(lk.source_origin)
                        accepted_targets.add(lk.source_origin)
                elif lk.target_origin in current_targets and lk.source_origin in accepted_targets:
                    src_node = node_set.get(lk.source_origin)
                    if src_node and any(f.name == schema_field for f in src_node.fields):
                        if lk not in accepted_links:
                            accepted_links.append(lk)
            current_targets = next_targets
        filtered_links = other_links + accepted_links
    else:
        filtered_links = links

    fwd: dict[str, set[str]] = {}
    rev: dict[str, set[str]] = {}
    for lk in filtered_links:
        fwd.setdefault(lk.source_origin, set()).add(lk.target_origin)
        rev.setdefault(lk.target_origin, set()).add(lk.source_origin)

    upstream: set[str] = set()
    frontier = set(seed_node_ids)
    while frontier:
        new_layer: set[str] = set()
        for nid in frontier:
            for src in rev.get(nid, ()):
                if src not in upstream and src not in seed_node_ids:
                    new_layer.add(src)
        upstream.update(new_layer)
        frontier = new_layer

    downstream: set[str] = set()
    frontier = set(seed_node_ids)
    while frontier:
        new_layer: set[str] = set()
        for nid in frontier:
            for tgt in fwd.get(nid, ()):
                if tgt not in downstream and tgt not in seed_node_ids:
                    new_layer.add(tgt)
        downstream.update(new_layer)
        frontier = new_layer

    included_ids: set[str] = set(seed_node_ids) | upstream | downstream

    _nodes = [n for n in nodes if n.id in included_ids]
    _links = [
        lk for lk in filtered_links
        if lk.source_origin in included_ids and lk.target_origin in included_ids
    ]
    _tags = [t for t in tags if t.id in included_ids]
    _routes = [r for r in routes if r.id in included_ids]

    return _tags, _routes, _nodes, _links


def filter_subgraph_by_module_prefix(
    *,
    tags: list[Tag],
    routes: list[Route],
    links: list[Link],
    nodes: list[SchemaNode],
    module_prefix: str
) -> tuple[list[Tag], list[Route], list[SchemaNode], list[Link]]:
    """Collapse schema graph so routes link directly to nodes whose module matches module_prefix."""
    if not module_prefix:
        return (
            tags, routes, nodes,
            [lk for lk in links if lk.type in ("tag_route", "route_to_schema")]
        )

    route_links = [lk for lk in links if lk.type == "route_to_schema"]
    schema_links = [lk for lk in links if lk.type in {"schema", "parent", "subset"}]
    tag_route_links = [lk for lk in links if lk.type == "tag_route"]

    node_lookup: dict[str, SchemaNode] = {node.id: node for node in nodes}

    filtered_nodes = [
        node for node in nodes
        if node_lookup[node.id].module.startswith(module_prefix)
    ]
    filtered_node_ids = {node.id for node in filtered_nodes}

    adjacency: dict[str, list[str]] = {}
    for link in schema_links:
        if (link.source_origin not in node_lookup
                or link.target_origin not in node_lookup):
            continue
        adjacency.setdefault(link.source_origin, [])
        if link.target_origin not in adjacency[link.source_origin]:
            adjacency[link.source_origin].append(link.target_origin)

    merged_links: list[Link] = []
    seen_pairs: set[tuple[str, str]] = set()

    for link in route_links:
        route_id = link.source_origin
        start_node_id = link.target_origin
        if route_id is None or start_node_id is None:
            continue
        if start_node_id not in node_lookup:
            continue

        visited: set[str] = set()
        queue: deque[str] = deque([start_node_id])

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            if current in filtered_node_ids:
                key = (route_id, current)
                if key not in seen_pairs:
                    seen_pairs.add(key)
                    merged_links.append(
                        Link(
                            source=link.source,
                            source_origin=route_id,
                            target=f"{current}::{PK}",
                            target_origin=current,
                            type="route_to_schema",
                        )
                    )
                continue

            for next_node in adjacency.get(current, ()):
                if next_node not in visited:
                    queue.append(next_node)

    module_prefix_links = [
        lk
        for lk in links
        if (lk.source_origin or "").startswith(module_prefix)
        and (lk.target_origin or "").startswith(module_prefix)
    ]

    filtered_links = tag_route_links + merged_links + module_prefix_links

    return tags, routes, filtered_nodes, filtered_links


def filter_subgraph_from_tag_to_schema_by_module_prefix(
    *,
    tags: list[Tag],
    routes: list[Route],
    links: list[Link],
    nodes: list[SchemaNode],
    module_prefix: str
) -> tuple[list[Tag], list[Route], list[SchemaNode], list[Link]]:
    """Collapse schema graph so tags link directly to nodes whose module matches module_prefix."""
    if not module_prefix:
        return (
            tags, routes, nodes,
            [lk for lk in links if lk.type in ("tag_route", "route_to_schema")]
        )

    route_links = [lk for lk in links if lk.type == "route_to_schema"]
    schema_links = [lk for lk in links if lk.type in {"schema", "parent", "subset"}]
    tag_route_links = [lk for lk in links if lk.type == "tag_route"]

    node_lookup: dict[str, SchemaNode] = {
        node.id: node for node in (nodes + routes)
    }

    filtered_nodes = [
        node for node in nodes
        if node_lookup[node.id].module.startswith(module_prefix)
    ]
    filtered_node_ids = {node.id for node in filtered_nodes}

    adjacency: dict[str, list[str]] = {}
    for link in (schema_links + route_links):
        if (link.source_origin not in node_lookup
                or link.target_origin not in node_lookup):
            continue
        adjacency.setdefault(link.source_origin, [])
        if link.target_origin not in adjacency[link.source_origin]:
            adjacency[link.source_origin].append(link.target_origin)

    merged_links: list[Link] = []
    seen_pairs: set[tuple[str, str]] = set()

    for link in tag_route_links:
        tag_id = link.source_origin
        start_node_id = link.target_origin
        if tag_id is None or start_node_id is None:
            continue
        if start_node_id not in node_lookup:
            continue

        visited: set[str] = set()
        queue: deque[str] = deque([start_node_id])

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            if current in filtered_node_ids:
                key = (tag_id, current)
                if key not in seen_pairs:
                    seen_pairs.add(key)
                    merged_links.append(
                        Link(
                            source=link.source,
                            source_origin=tag_id,
                            target=f"{current}::{PK}",
                            target_origin=current,
                            type="tag_to_schema",
                        )
                    )
                continue

            for next_node in adjacency.get(current, ()):
                if next_node not in visited:
                    queue.append(next_node)

    module_prefix_links = [
        lk
        for lk in links
        if (lk.source_origin or "").startswith(module_prefix)
        and (lk.target_origin or "").startswith(module_prefix)
    ]

    filtered_links = merged_links + module_prefix_links

    return tags, [], filtered_nodes, filtered_links
