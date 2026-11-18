"""Ownership change between two dates (plan F5).

A relation is present at a date when it has started (``valid_from`` empty or not after the date) and not ended
(``valid_to`` empty or not before the date): the same rule as the Network page. Relations present at only one of
the two dates are added or removed; relations present at both whose stake differs are changed.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Any

from taxnetlab.views import _active


def _date(text: str) -> str:
    try:
        return dt.date.fromisoformat(str(text)).isoformat()
    except (TypeError, ValueError):
        raise ValueError(f"'{text}' is not a date (YYYY-MM-DD)") from None


def ownership_changes(dataset, date_a: str, date_b: str) -> dict[str, Any]:
    a, b = _date(date_a), _date(date_b)
    where = {e["entity_id"]: e["jurisdiction_id"] for e in dataset.tables["entities"]}
    names = {e["entity_id"]: e.get("reported_name") or e.get("display_name") or e["entity_id"]
             for e in dataset.tables["entities"]}
    added, removed, changed = [], [], []
    gained: dict[str, int] = defaultdict(int)
    lost: dict[str, int] = defaultdict(int)

    def row(o: dict[str, Any]) -> dict[str, Any]:
        return {"relation_id": o["relation_id"], "relation_type": o["relation_type"],
                "holder_id": o["holder_id"], "holder": names.get(o["holder_id"]),
                "holder_jurisdiction": where.get(o["holder_id"]), "held_id": o["held_id"],
                "held": names.get(o["held_id"]), "held_jurisdiction": where.get(o["held_id"]),
                "fraction": o["fraction"], "valid_from": o.get("valid_from"), "valid_to": o.get("valid_to")}

    at_a = {o["relation_id"]: o for o in dataset.tables["ownership"] if _active(o, a)}
    at_b = {o["relation_id"]: o for o in dataset.tables["ownership"] if _active(o, b)}
    for rid in sorted(set(at_b) - set(at_a)):
        r = row(at_b[rid])
        added.append(r)
        for j in {r["holder_jurisdiction"], r["held_jurisdiction"]} - {None}:
            gained[j] += 1
    for rid in sorted(set(at_a) - set(at_b)):
        r = row(at_a[rid])
        removed.append(r)
        for j in {r["holder_jurisdiction"], r["held_jurisdiction"]} - {None}:
            lost[j] += 1
    for rid in sorted(set(at_a) & set(at_b)):
        fa, fb = at_a[rid]["fraction"], at_b[rid]["fraction"]
        if fa != fb:  # the same row cannot differ; kept for datasets that version a relation in place
            changed.append({**row(at_b[rid]), "fraction_before": fa})
    juris = sorted(set(gained) | set(lost))
    return {"from": a, "to": b, "counts": {"added": len(added), "removed": len(removed), "changed": len(changed)},
            "added": added, "removed": removed, "changed": changed,
            "jurisdictions": [{"jurisdiction_id": j, "gained": gained[j], "lost": lost[j], "net": gained[j] - lost[j]}
                              for j in juris]}
