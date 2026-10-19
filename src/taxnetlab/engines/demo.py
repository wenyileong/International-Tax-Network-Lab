"""Demonstration engine: direct cross-border link summary per jurisdiction.

This is a pipeline demonstration, not a research method (plan v2.1, Phase 1). It counts and sums
stored direct relations; it does not implement or approximate any published measure, and its
outputs must not be read as conduit, sink or routing indicators.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from taxnetlab.datasets import Dataset
from taxnetlab.engines.base import (
    DEMONSTRATION,
    OK,
    Engine,
    EngineResult,
    EngineSpec,
    Measure,
    Parameter,
)
from taxnetlab.validation import ValidationReport
from taxnetlab.views import _active

COLUMNS = ("jurisdiction_id", "outbound_links", "inbound_links", "domestic_links", "outbound_value",
           "inbound_value", "net_outbound_value")


class LinkSummaryEngine(Engine):
    spec = EngineSpec(
        engine_id="demo.link_summary",
        display_name="Cross-border link summary (demonstration)",
        track=DEMONSTRATION,
        variant="baseline",
        version="0.2.0",
        status="verified",
        spec_ref="docs/specs/demo_link_summary.md v1",
        purpose="Demonstrates the engine, run-record and replay pipeline on direct ownership relations.",
        boundary="A demonstration. Not a published method and not an indicator of conduit, sink or routing behaviour.",
        next_step="None; kept as a pipeline test engine.",
        input_schema=("entities", "ownership"),
        parameters=(
            Parameter("as_of", "date", None, description="Relations valid on this date; empty means current relations."),
            Parameter("relation_type", "choice", "equity", choices=("equity", "voting", "control", "economic_interest")),
        ),
        measures=(
            Measure("demo.outbound_links", "Direct relations held by entities of the jurisdiction in entities of other jurisdictions.",
                    "count of relations", "none", "relations", "demo spec s 2"),
            Measure("demo.inbound_links", "Direct relations held in entities of the jurisdiction by entities of other jurisdictions.",
                    "count of relations", "none", "relations", "demo spec s 2"),
            Measure("demo.domestic_links", "Direct relations where holder and held are in the same jurisdiction.",
                    "count of relations", "none", "relations", "demo spec s 2"),
            Measure("demo.outbound_value", "Sum of reported value of outbound cross-border relations.",
                    "sum of value_amount", "none", "dataset currency", "demo spec s 3"),
            Measure("demo.inbound_value", "Sum of reported value of inbound cross-border relations.",
                    "sum of value_amount", "none", "dataset currency", "demo spec s 3"),
            Measure("demo.net_outbound_value", "outbound_value minus inbound_value.",
                    "outbound_value - inbound_value", "none", "dataset currency", "demo spec s 3"),
        ),
        outputs={"jurisdiction_summary": COLUMNS},
        output_keys={"jurisdiction_summary": ("jurisdiction_id",)},
    )

    def validate(self, dataset: Dataset, params: dict[str, Any]) -> ValidationReport:
        r = ValidationReport()
        currencies = {o["value_currency"] for o in dataset.tables["ownership"] if o.get("value_amount") is not None}
        if len(currencies) > 1:
            r.error("mixed_currency", f"values in several currencies {sorted(currencies)}; convert before summing",
                    params={"currencies": ", ".join(sorted(currencies))})
        return r

    def _run(self, dataset: Dataset, params: dict[str, Any]) -> EngineResult:
        where = {e["entity_id"]: e["jurisdiction_id"] for e in dataset.tables["entities"]}
        rels = [o for o in dataset.tables["ownership"]
                if o["relation_type"] == params["relation_type"] and _active(o, params["as_of"])]
        stats: dict[str, dict[str, float]] = {
            j["jurisdiction_id"]: defaultdict(float) for j in dataset.tables["jurisdictions"]}
        missing_value = 0
        for o in rels:
            a, b = where[o["holder_id"]], where[o["held_id"]]
            if a == b:
                stats[a]["domestic_links"] += 1
                continue
            stats[a]["outbound_links"] += 1
            stats[b]["inbound_links"] += 1
            if o.get("value_amount") is None:
                missing_value += 1
            else:
                stats[a]["outbound_value"] += o["value_amount"]
                stats[b]["inbound_value"] += o["value_amount"]
        rows = []
        for jid, s in stats.items():
            rows.append({
                "jurisdiction_id": jid,
                "outbound_links": int(s["outbound_links"]), "inbound_links": int(s["inbound_links"]),
                "domestic_links": int(s["domestic_links"]),
                "outbound_value": round(s["outbound_value"], 6), "inbound_value": round(s["inbound_value"], 6),
                "net_outbound_value": round(s["outbound_value"] - s["inbound_value"], 6),
            })
        warnings = []
        if missing_value:
            warnings.append(f"{missing_value} cross-border relation(s) without a reported value were counted as links but not summed.")
        trace = [
            {"step": 1, "description": "Select relations", "detail": f"relation_type = {params['relation_type']}; as_of = {params['as_of'] or 'current'}",
             "result": f"{len(rels)} relations"},
            {"step": 2, "description": "Locate holder and held entities in jurisdictions", "detail": "entities.jurisdiction_id",
             "result": f"{len(stats)} jurisdictions"},
            {"step": 3, "description": "Count and sum cross-border relations", "detail": "domestic relations counted separately",
             "result": f"{sum(r['outbound_links'] for r in rows)} cross-border relations"},
            {"step": 4, "description": "Identity check", "detail": "total outbound = total inbound (links and value)",
             "result": "holds" if _identity_holds(rows) else "FAILS"},
        ]
        return EngineResult(OK, {"jurisdiction_summary": rows}, trace, warnings,
                            ["Relations are counted as stored; parallel relations count separately."])


def _identity_holds(rows: list[dict[str, Any]]) -> bool:
    links = sum(r["outbound_links"] for r in rows) == sum(r["inbound_links"] for r in rows)
    value = abs(sum(r["outbound_value"] for r in rows) - sum(r["inbound_value"] for r in rows)) < 1e-6
    return links and value
