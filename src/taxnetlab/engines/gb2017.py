"""Conduits and sinks: reproduction variant of Garcia-Bernardo, Fichtner, Takes and Heemskerk (2017).

Specification: ``docs/specs/gb2017_conduits_sinks.md`` (v0.1, draft); section and interpretation numbers
(s 5, I4 and so on) refer to it. The source's equations were garbled in automated extraction, so the GDP
normalisation and the conduit denominators are reconstructions; the engine stays at ``implemented`` until
the author has checked them, and its results carry the "unverified" watermark.

Outline. Value flows from owned firms to owners. From every firm with revenue, all upward ownership paths
with multiplicative ownership at or above a threshold are enumerated; each path carries the first firm's
revenue times its multiplicative ownership. Paths are mapped to country sequences (adjacent repeats merged)
and summed. Sink centrality compares a country's net share of two-country chain value with its share of
GDP; conduit centralities do the same for three-country chains that start or end in a sink-OFC.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from taxnetlab.datasets import Dataset
from taxnetlab.engines.base import (
    OK,
    REPRODUCTION,
    Engine,
    EngineResult,
    EngineSpec,
    Measure,
    Parameter,
)
from taxnetlab.validation import ValidationReport
from taxnetlab.views import _active

SPEC = "docs/specs/gb2017_conduits_sinks.md v0.1 (draft)"
SEP = ">"

JUR_COLUMNS = ("jurisdiction_id", "gdp", "gdp_share", "value_in", "value_out", "sink_centrality", "is_sink",
               "conduit_in", "conduit_out", "is_conduit", "entropy_in", "entropy_out")
CHAIN_COLUMNS = ("chain", "countries", "value", "firm_paths")
SUMMARY_COLUMNS = ("measure", "value")


def _gdp(dataset: Dataset, period: str) -> dict[str, float]:
    best: dict[str, tuple[str, float]] = {}
    for a in dataset.tables["jurisdiction_attributes"]:
        if a["attribute"].lower() != "gdp":
            continue
        j, per = a["jurisdiction_id"], a["period"]
        cur = best.get(j)
        if cur is None or per == period or (cur[0] != period and per > cur[0]):
            best[j] = (per, a["value"])
    return {j: v for j, (_, v) in best.items()}


def _entropy(values: list[float]) -> float | None:
    total = math.fsum(values)
    if total <= 0:
        return None
    return -math.fsum((v / total) * math.log(v / total) for v in values if v > 0) + 0.0


class ConduitsSinksEngine(Engine):
    spec = EngineSpec(
        engine_id="gb2017.conduits_sinks",
        display_name="Conduits and sinks (Garcia-Bernardo and others, 2017)",
        track=REPRODUCTION, variant="reproduction", version="0.1.0", status="implemented",
        spec_ref=SPEC,
        purpose="Identifies sink jurisdictions (where a disproportionate share of value ends, relative to GDP) and "
                "conduit jurisdictions (through which value passes to and from sinks) in corporate ownership chains.",
        boundary="Reproduction under documented interpretations; the GDP normalisation and conduit denominators are "
                 "reconstructions awaiting the author's check. Network position is not evidence of avoidance or "
                 "illegality. Consumes the value-flow direction (owned firm to owner).",
        next_step="Author check of the specification against the published article; then promotion to verified.",
        input_schema=("entities", "ownership", "entity_financials", "jurisdiction_attributes (gdp)"),
        parameters=(
            Parameter("period", "text", None, description="Revenue period; empty selects the latest."),
            Parameter("as_of", "date", None, description="Ownership valid on this date; empty means current."),
            Parameter("ownership_threshold", "float", 0.001, minimum=0.000001, maximum=0.5,
                      description="Minimum multiplicative ownership for a chain to continue (s 3, I2)."),
            Parameter("normalise_missing_shareholders", "bool", True,
                      description="Scale each firm's known shareholdings to sum to one (I1)."),
            Parameter("sink_threshold", "float", 10.0, minimum=0.0, maximum=1000.0,
                      description="Sink-OFC if sink centrality exceeds this (s 5, I10)."),
            Parameter("conduit_threshold", "float", 1.0, minimum=0.0, maximum=1000.0,
                      description="Conduit-OFC if both conduit centralities exceed this (s 6, I10)."),
            Parameter("conduit_denominator", "choice", "subset_total", choices=("subset_total", "all_g3"),
                      description="Denominator of the conduit centralities (s 6, I5)."),
            Parameter("chain_budget", "int", 1_000_000, minimum=1000, maximum=50_000_000,
                      description="Bound on firm-level paths enumerated; reaching it is reported (I11)."),
        ),
        measures=(
            Measure("gb2017.sink_centrality", "Net share of two-country chain value ending in the jurisdiction, "
                    "relative to its share of GDP.", "(value in - value out) / total G2 value", "GDP share",
                    "ratio", "spec s 5, I4"),
            Measure("gb2017.conduit_in", "Share of value from sink-OFCs passing through the jurisdiction, relative to "
                    "its GDP share.", "G3 value from a sink through c", "subset total (I5) x GDP share", "ratio",
                    "spec s 6"),
            Measure("gb2017.conduit_out", "Share of value passing through the jurisdiction to sink-OFCs, relative to "
                    "its GDP share.", "G3 value through c to a sink", "subset total (I5) x GDP share", "ratio",
                    "spec s 6"),
            Measure("gb2017.entropy_in", "Shannon entropy of the destinations of sink-originating value through c.",
                    "-sum p ln p", "none", "nats", "spec s 7"),
            Measure("gb2017.entropy_out", "Shannon entropy of the origins of sink-bound value through c.",
                    "-sum p ln p", "none", "nats", "spec s 7"),
        ),
        outputs={"jurisdictions": JUR_COLUMNS, "country_chains": CHAIN_COLUMNS, "summary": SUMMARY_COLUMNS},
        output_keys={"jurisdictions": ("jurisdiction_id",), "country_chains": ("chain",), "summary": ("measure",)},
    )

    # ------------------------------------------------------------------ validation
    def validate(self, dataset: Dataset, params: dict[str, Any]) -> ValidationReport:
        r = ValidationReport()
        fin = dataset.tables["entity_financials"]
        periods = sorted({f["period"] for f in fin})
        if not periods:
            r.error("no_revenue_data", "the dataset has no entity_financials rows; chains are weighted by revenue",
                    params={})
            return r
        if params.get("period") is None:
            params["period"] = periods[-1]
        if params["period"] not in periods:
            r.error("unknown_period", f"no revenue for period '{params['period']}'",
                    params={"period": params["period"], "periods": ", ".join(periods)})
            return r
        currencies = {f["currency"] for f in fin if f["period"] == params["period"]}
        if len(currencies) > 1:
            r.error("mixed_currency", f"revenues in several currencies {sorted(currencies)}; convert first",
                    params={"currencies": ", ".join(sorted(currencies))})
        gdp = _gdp(dataset, params["period"])
        used = {e["jurisdiction_id"] for e in dataset.tables["entities"]}
        missing = sorted(j for j in used if not gdp.get(j, 0) > 0)
        if missing:
            r.error("gdp_missing", f"GDP is missing or not positive for {missing}", params={"ids": ", ".join(missing)})
        consolidated = sum(1 for f in fin if f["period"] == params["period"] and f["consolidation"] == "consolidated")
        if consolidated:
            r.warning("consolidated_revenue", f"{consolidated} consolidated revenue figure(s) double count subsidiaries",
                      params={"id": str(consolidated)})
        return r

    # ------------------------------------------------------------------ computation
    def _run(self, dataset: Dataset, params: dict[str, Any]) -> EngineResult:
        warnings: list[str] = []
        where = {e["entity_id"]: e["jurisdiction_id"] for e in dataset.tables["entities"]}
        revenue = {f["entity_id"]: f["operating_revenue"] for f in dataset.tables["entity_financials"]
                   if f["period"] == params["period"]}

        # I1: owners of each firm with (normalised) weights; parallel relations between a pair are summed.
        raw: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        skipped = 0
        for o in dataset.tables["ownership"]:
            if o["relation_type"] != "equity" or not _active(o, params["as_of"]) or o["holder_id"] == o["held_id"]:
                continue
            if o.get("fraction") is None:
                skipped += 1
                continue
            raw[o["held_id"]][o["holder_id"]] += o["fraction"]
        owners: dict[str, list[tuple[str, float]]] = {}
        for held, holders in raw.items():
            total = math.fsum(holders.values())
            if total <= 0:
                continue
            scale = (1.0 / total) if params["normalise_missing_shareholders"] else 1.0
            owners[held] = sorted((h, f * scale) for h, f in holders.items() if f > 0)
        if skipped:
            warnings.append(f"{skipped} equity relation(s) without a fraction were left out (never imputed).")

        # s 3 and I2, I3: enumerate upward paths; keep the maximum value per (first firm, last firm, country chain).
        threshold = params["ownership_threshold"]
        budget = params["chain_budget"]
        best: dict[tuple[str, str, tuple[str, ...]], float] = {}
        paths = 0
        budget_hit = False
        for start in sorted(revenue):
            r0 = revenue[start]
            if r0 <= 0 or start not in where:
                continue
            stack = [(start, 1.0, (start,))]
            while stack and not budget_hit:
                firm, mo, path = stack.pop()
                for owner, w in owners.get(firm, ()):
                    if owner in path:  # cycles are discarded (stated)
                        continue
                    nmo = mo * w
                    if nmo < threshold - 1e-15:
                        continue
                    npath = path + (owner,)
                    paths += 1
                    if paths >= budget:
                        budget_hit = True
                    countries: list[str] = []
                    for f in npath:  # merge adjacent firms in the same country (stated)
                        c = where[f]
                        if not countries or countries[-1] != c:
                            countries.append(c)
                    if len(countries) >= 2:
                        key = (start, owner, tuple(countries))
                        value = r0 * nmo
                        if value > best.get(key, -1.0):
                            best[key] = value
                    stack.append((owner, nmo, npath))
        if budget_hit:
            warnings.append(f"The chain budget ({params['chain_budget']}) was reached; results use the paths found. "
                            "Raise chain_budget or the ownership threshold.")

        chains: dict[tuple[str, ...], float] = defaultdict(float)
        chain_paths: dict[tuple[str, ...], int] = defaultdict(int)
        for (_, _, seq), value in best.items():
            chains[seq] += value
            chain_paths[seq] += 1

        jurisdictions = [j["jurisdiction_id"] for j in dataset.tables["jurisdictions"]]
        gdp_all = _gdp(dataset, params["period"])
        gdp = {j: gdp_all.get(j) for j in jurisdictions}
        gdp_total = math.fsum(v for v in gdp.values() if v and v > 0)
        share = {j: (gdp[j] / gdp_total if gdp[j] and gdp_total else None) for j in jurisdictions}

        g2 = {seq: v for seq, v in chains.items() if len(seq) == 2}
        g3 = {seq: v for seq, v in chains.items() if len(seq) == 3}
        t2 = math.fsum(g2.values())
        vin: dict[str, float] = defaultdict(float)
        vout: dict[str, float] = defaultdict(float)
        for (a, b), v in g2.items():
            vout[a] += v
            vin[b] += v

        def ratio(num: float, den: float, j: str) -> float | None:
            if den <= 0 or not share[j]:
                return None
            return (num / den) / share[j]

        sink = {j: ratio(vin[j] - vout[j], t2, j) for j in jurisdictions}
        sinks = {j for j, s in sink.items() if s is not None and s > params["sink_threshold"]}
        if t2 <= 0:
            warnings.append("No two-country chains carry value; sink centrality is undefined.")

        s1 = {seq: v for seq, v in g3.items() if seq[0] in sinks}
        s3 = {seq: v for seq, v in g3.items() if seq[2] in sinks}
        all3 = math.fsum(g3.values())
        d_in = math.fsum(s1.values()) if params["conduit_denominator"] == "subset_total" else all3
        d_out = math.fsum(s3.values()) if params["conduit_denominator"] == "subset_total" else all3
        through_in: dict[str, float] = defaultdict(float)
        through_out: dict[str, float] = defaultdict(float)
        dest_in: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        orig_out: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for (a, c, b), v in s1.items():
            through_in[c] += v
            dest_in[c][b] += v
        for (a, c, b), v in s3.items():
            through_out[c] += v
            orig_out[c][a] += v

        rows = []
        for j in jurisdictions:
            cin = ratio(through_in[j], d_in, j)
            cout = ratio(through_out[j], d_out, j)
            rows.append({
                "jurisdiction_id": j, "gdp": gdp[j], "gdp_share": _r(share[j]),
                "value_in": _r(vin[j]), "value_out": _r(vout[j]), "sink_centrality": _r(sink[j]),
                "is_sink": j in sinks, "conduit_in": _r(cin), "conduit_out": _r(cout),
                "is_conduit": bool(cin is not None and cout is not None and cin > params["conduit_threshold"]
                                   and cout > params["conduit_threshold"]),
                "entropy_in": _r(_entropy(list(dest_in[j].values()))),
                "entropy_out": _r(_entropy(list(orig_out[j].values()))),
            })
        if sinks and d_in <= 0:
            warnings.append("No three-country chain starts in a sink-OFC; inward conduit centrality is undefined (I9).")
        if not sinks:
            warnings.append("No jurisdiction exceeds the sink threshold, so conduit centralities are undefined (I9).")

        chain_rows = [{"chain": SEP.join(seq), "countries": len(seq), "value": _r(v), "firm_paths": chain_paths[seq]}
                      for seq, v in chains.items()]
        conduits = sorted(r["jurisdiction_id"] for r in rows if r["is_conduit"])
        summary = [
            {"measure": "period", "value": params["period"]},
            {"measure": "firm_paths", "value": paths},
            {"measure": "firm_paths_kept", "value": len(best)},
            {"measure": "country_chains", "value": len(chains)},
            {"measure": "g2_chains", "value": len(g2)},
            {"measure": "g3_chains", "value": len(g3)},
            {"measure": "g2_total_value", "value": _r(t2)},
            {"measure": "g3_total_value", "value": _r(all3)},
            {"measure": "sink_ofcs", "value": ", ".join(sorted(sinks)) or "none"},
            {"measure": "conduit_ofcs", "value": ", ".join(conduits) or "none"},
            {"measure": "chain_budget_reached", "value": budget_hit},
        ]
        trace = [
            {"step": 1, "description": "Ownership weights (I1)",
             "detail": "normalised for missing shareholders" if params["normalise_missing_shareholders"] else "as reported",
             "result": f"{len(owners)} owned firms"},
            {"step": 2, "description": "Firm-level chains (s 3, I2, I3)",
             "detail": f"threshold {threshold}; cycles discarded", "result": f"{paths} paths, {len(best)} kept"},
            {"step": 3, "description": "Country chains (s 4)", "detail": "adjacent same-country firms merged",
             "result": f"{len(chains)} chains: {len(g2)} in G2, {len(g3)} in G3"},
            {"step": 4, "description": "Sink centrality (s 5, I4)", "detail": f"threshold {params['sink_threshold']}",
             "result": f"sink-OFCs: {', '.join(sorted(sinks)) or 'none'}"},
            {"step": 5, "description": "Conduit centralities (s 6, I5)",
             "detail": f"denominator {params['conduit_denominator']}; threshold {params['conduit_threshold']}",
             "result": f"conduit-OFCs: {', '.join(conduits) or 'none'}"},
        ]
        return EngineResult(OK, {"jurisdictions": rows, "country_chains": chain_rows, "summary": summary}, trace,
                            warnings, ["Interpretations I1 to I11 of the specification apply.",
                                       "Value flows from owned firms to owners; revenue weights chains."])


def _r(x: float | None) -> float | None:
    return None if x is None else round(float(x), 12)
