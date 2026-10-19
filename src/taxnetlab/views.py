"""Graph views derived from a dataset (plan v2.1, s 5.2). Views are never stored as truth.

* ``ownership``: holder -> held, one edge per stored relation (parallel relations kept).
* ``value_flow``: held -> holder; the direction in which returns travel towards the ultimate owner.
* ``jurisdiction``: entities collapsed to jurisdictions under a declared aggregation rule,
  oriented holder jurisdiction -> held jurisdiction.

Every view carries metadata stating its direction and the transformation that produced it.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import networkx as nx

from taxnetlab.datasets import Dataset

VIEWS = ("ownership", "value_flow", "jurisdiction")
AGGREGATION_RULES = ("count", "fraction_sum", "value_sum")


@dataclass
class View:
    graph: nx.MultiDiGraph | nx.DiGraph
    meta: dict[str, Any]
    excluded: list[dict[str, Any]] = field(default_factory=list)


def _active(row: dict[str, Any], as_of: str | None) -> bool:
    if as_of is None:
        return row.get("valid_to") is None
    if row.get("valid_from") and row["valid_from"] > as_of:
        return False
    return not (row.get("valid_to") and row["valid_to"] < as_of)


def _relations(dataset: Dataset, as_of: str | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept, excluded = [], []
    for o in dataset.tables["ownership"]:
        if _active(o, as_of):
            kept.append(o)
        else:
            excluded.append({"relation_id": o["relation_id"], "reason": "outside_as_of"})
    return kept, excluded


def ownership_view(dataset: Dataset, as_of: str | None = None, reverse: bool = False) -> View:
    rels, excluded = _relations(dataset, as_of)
    g = nx.MultiDiGraph()
    for e in dataset.tables["entities"]:
        g.add_node(e["entity_id"], **e)
    for o in rels:
        u, v = (o["held_id"], o["holder_id"]) if reverse else (o["holder_id"], o["held_id"])
        g.add_edge(u, v, key=o["relation_id"], **o)
    meta = {
        "view": "value_flow" if reverse else "ownership",
        "direction": "held -> holder" if reverse else "holder -> held",
        "transformation": ("reverse of stored ownership relations" if reverse else "stored direct relations as recorded"),
        "as_of": as_of or "current (no valid_to)",
        "parallel_relations": "kept as separate edges",
    }
    return View(g, meta, excluded)


def value_flow_view(dataset: Dataset, as_of: str | None = None) -> View:
    return ownership_view(dataset, as_of, reverse=True)


def jurisdiction_view(
    dataset: Dataset, rule: str = "count", as_of: str | None = None, include_domestic: bool = False
) -> View:
    if rule not in AGGREGATION_RULES:
        raise ValueError(f"rule must be one of {AGGREGATION_RULES}")
    rels, excluded = _relations(dataset, as_of)
    where = {e["entity_id"]: e["jurisdiction_id"] for e in dataset.tables["entities"]}
    g = nx.DiGraph()
    for j in dataset.tables["jurisdictions"]:
        g.add_node(j["jurisdiction_id"], **j)
    weights: dict[tuple[str, str], float] = defaultdict(float)
    counts: dict[tuple[str, str], int] = defaultdict(int)
    currencies: dict[tuple[str, str], set] = defaultdict(set)
    for o in rels:
        a, b = where[o["holder_id"]], where[o["held_id"]]
        if a == b and not include_domestic:
            excluded.append({"relation_id": o["relation_id"], "reason": "domestic"})
            continue
        if rule == "count":
            w = 1.0
        elif rule == "fraction_sum":
            if o.get("fraction") is None:
                excluded.append({"relation_id": o["relation_id"], "reason": "fraction_missing"})
                continue
            w = o["fraction"]
        else:
            if o.get("value_amount") is None:
                excluded.append({"relation_id": o["relation_id"], "reason": "value_missing"})
                continue
            w = o["value_amount"]
            currencies[(a, b)].add(o["value_currency"])
        weights[(a, b)] += w
        counts[(a, b)] += 1
    mixed_currency = sorted({c for s in currencies.values() for c in s})
    if rule == "value_sum" and len(mixed_currency) > 1:
        raise ValueError(f"value_sum would add different currencies {mixed_currency}; convert first")
    for (a, b), w in weights.items():
        g.add_edge(a, b, weight=w, relations=counts[(a, b)])
    meta = {
        "view": "jurisdiction",
        "direction": "holder jurisdiction -> held jurisdiction",
        "transformation": f"entities collapsed to jurisdictions; edge weight = {rule}"
                          + ("" if include_domestic else "; domestic relations excluded"),
        "rule": rule,
        "currency": mixed_currency[0] if mixed_currency else None,
        "as_of": as_of or "current (no valid_to)",
    }
    return View(g, meta, excluded)


def build_view(dataset: Dataset, view: str, rule: str = "count", as_of: str | None = None,
               include_domestic: bool = False) -> View:
    if view == "ownership":
        return ownership_view(dataset, as_of)
    if view == "value_flow":
        return value_flow_view(dataset, as_of)
    if view == "jurisdiction":
        return jurisdiction_view(dataset, rule, as_of, include_domestic)
    raise ValueError(f"view must be one of {VIEWS}")


# ---------------------------------------------------------------------- layout and JSON
def _cluster_layout(dataset: Dataset, node_ids: list[str]) -> dict[str, tuple[float, float]]:
    """Deterministic layout without numerical libraries: jurisdictions sit on a circle and their
    entities on a small ring around each jurisdiction's position."""
    jurisdictions = [j["jurisdiction_id"] for j in dataset.tables["jurisdictions"]]
    where = {e["entity_id"]: e["jurisdiction_id"] for e in dataset.tables["entities"]}
    n = max(len(jurisdictions), 1)
    centre = {j: (math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)) for i, j in enumerate(jurisdictions)}
    groups: dict[str, list[str]] = defaultdict(list)
    for node in sorted(node_ids):
        groups[where.get(node, node)].append(node)
    pos = {}
    for jur, members in groups.items():
        cx, cy = centre.get(jur, (0.0, 0.0))
        m = len(members)
        radius = 0.0 if m == 1 else min(0.32, 0.08 + 0.025 * m)
        for k, node in enumerate(members):
            angle = 2 * math.pi * k / max(m, 1) + 0.3
            pos[node] = (round(cx + radius * math.cos(angle), 5), round(cy + radius * math.sin(angle), 5))
    return pos


def view_to_json(dataset: Dataset, view: View) -> dict[str, Any]:
    g = view.graph
    is_jur = view.meta["view"] == "jurisdiction"
    if is_jur:
        jlist = [j["jurisdiction_id"] for j in dataset.tables["jurisdictions"]]
        n = max(len(jlist), 1)
        pos = {j: (round(math.cos(2 * math.pi * i / n), 5), round(math.sin(2 * math.pi * i / n), 5))
               for i, j in enumerate(jlist)}
    else:
        pos = _cluster_layout(dataset, list(g.nodes))
    jurisdiction_order = [j["jurisdiction_id"] for j in dataset.tables["jurisdictions"]]
    nodes = []
    for node, attrs in g.nodes(data=True):
        x, y = pos[node]
        nodes.append({
            "id": node,
            "label": attrs.get("display_name") if is_jur else attrs.get("reported_name"),
            "jurisdiction_id": node if is_jur else attrs.get("jurisdiction_id"),
            "entity_type": None if is_jur else attrs.get("entity_type"),
            "x": x, "y": y,
            "in_degree": g.in_degree(node), "out_degree": g.out_degree(node),
            "attributes": {k: v for k, v in attrs.items()},
        })
    edges = []
    if is_jur:
        for u, v, attrs in g.edges(data=True):
            edges.append({"source": u, "target": v, "weight": attrs["weight"], "relations": attrs["relations"]})
    else:
        for u, v, key, attrs in g.edges(keys=True, data=True):
            edges.append({"source": u, "target": v, "relation_id": key, "fraction": attrs.get("fraction"),
                          "value_amount": attrs.get("value_amount"), "value_currency": attrs.get("value_currency"),
                          "relation_type": attrs.get("relation_type"), "share_class": attrs.get("share_class"),
                          "source_id": attrs.get("source_id")})
    return {"meta": view.meta, "nodes": nodes, "edges": edges, "excluded": view.excluded,
            "jurisdiction_order": jurisdiction_order, "data_status": dataset.data_status}


def jurisdiction_matrix(dataset: Dataset, rule: str = "count", as_of: str | None = None,
                        include_domestic: bool = True) -> dict[str, Any]:
    """Holder-jurisdiction by held-jurisdiction matrix of the aggregated weights."""
    view = jurisdiction_view(dataset, rule, as_of, include_domestic)
    order = [j["jurisdiction_id"] for j in dataset.tables["jurisdictions"]]
    matrix = [[0.0 for _ in order] for _ in order]
    index = {j: i for i, j in enumerate(order)}
    for u, v, attrs in view.graph.edges(data=True):
        matrix[index[u]][index[v]] = attrs["weight"]
    return {"rows": order, "columns": order, "values": matrix, "meta": view.meta, "excluded": view.excluded,
            "row_label": "holder jurisdiction", "column_label": "held jurisdiction",
            "data_status": dataset.data_status}
