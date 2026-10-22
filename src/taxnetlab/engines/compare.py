"""Model comparison: namespaced measures side by side, the agreement rule and robustness shares.

Specification: ``docs/specs/compare_models.md`` (v0.1). Plan v2.4: s 8 (model comparison), s 6.3 (agreement
rule: a ranking is declared only where every reading of an ambiguous specification agrees; otherwise the
result is a tie with the readings side by side), s 3.2 (robustness shares).

Readings are the documented alternative interpretations of each source (tax routing: I2 world average and
I8 pair weights; conduits and sinks: I1 normalisation for missing shareholders and I5 conduit denominator).
No measure is combined with another into a score.
"""

from __future__ import annotations

import itertools
import json
import math
from typing import Any

from taxnetlab import progress
from taxnetlab.datasets import Dataset
from taxnetlab.engines.base import INVALID_INPUT, OK, ORIGINAL, Engine, EngineResult, EngineSpec, Parameter
from taxnetlab.engines.upstream import UpstreamError, run_upstream
from taxnetlab.validation import ValidationReport

SPEC = "docs/specs/compare_models.md v0.1"

# engine -> list of (reading label, parameters); the first reading is the engine's default.
READINGS: dict[str, list[tuple[str, dict[str, Any]]]] = {
    "vtrl2018.tax_routing": [
        (f"I2={wa}; I8={w}", {"world_average": wa, "centrality_weights": w})
        for wa, w in (("unweighted", "gdp_product"), ("gdp", "gdp_product"), ("unweighted", "unweighted"),
                      ("gdp", "unweighted"))],
    "gb2017.conduits_sinks": [
        (f"I1={'normalised' if n else 'as reported'}; I5={d}", {"normalise_missing_shareholders": n,
                                                                  "conduit_denominator": d})
        for n, d in ((True, "subset_total"), (True, "all_g3"), (False, "subset_total"), (False, "all_g3"))],
    "ph.vietoris_rips": [("default", {})],
}
# measure -> (engine, output table, column or derivation)
MEASURES: dict[str, tuple[str, str, str]] = {
    "vtrl2018.btwns": ("vtrl2018.tax_routing", "centrality", "btwns"),
    "vtrl2018.occur": ("vtrl2018.tax_routing", "centrality", "occur"),
    "vtrl2018.shop_as_host": ("vtrl2018.tax_routing", "pairs", "mean shop over homes"),
    "gb2017.sink_centrality": ("gb2017.conduits_sinks", "jurisdictions", "sink_centrality"),
    "gb2017.conduit_in": ("gb2017.conduits_sinks", "jurisdictions", "conduit_in"),
    "gb2017.conduit_out": ("gb2017.conduits_sinks", "jurisdictions", "conduit_out"),
    "ph.influence_h1": ("ph.vietoris_rips", "influence", "bottleneck_h1"),
}
CLASSES = {"gb2017.sink_ofc": "is_sink", "gb2017.conduit_ofc": "is_conduit"}

READING_COLUMNS = ("measure", "reading", "jurisdiction_id", "value", "rank")
AGREEMENT_COLUMNS = ("jurisdiction_id", "measure", "readings", "ranked_readings", "rank_min", "rank_max", "agreed",
                     "rank", "value_default")
CLASS_COLUMNS = ("jurisdiction_id", "classification", "readings", "classified_in", "share", "robust")
CORRELATION_COLUMNS = ("measure_a", "measure_b", "n", "spearman", "kendall_tau_b")
ENGINE_COLUMNS = ("engine_id", "reading", "parameters", "outcome", "status", "outputs_sha256", "note")
SUMMARY_COLUMNS = ("measure", "value")


class ModelComparisonEngine(Engine):
    spec = EngineSpec(
        engine_id="compare.models",
        display_name="Model comparison (agreement rule)",
        track=ORIGINAL, variant="original", version="0.1.0", status="implemented",
        spec_ref=SPEC,
        purpose="Places the namespaced measures of the method engines side by side by jurisdiction, ranks each under "
                "every documented reading of its source, declares a rank only where all readings agree, and reports "
                "robustness shares of classifications and rank correlations between measures.",
        boundary="A comparison, not a method: it adds no measure of its own and never combines measures into a score. "
                 "Its status can be no higher than that of the engines it compares, which are reported with every row.",
        next_step="Author check of the specification; promotion with the engines it compares.",
        input_schema=("outputs of vtrl2018.tax_routing, gb2017.conduits_sinks and ph.vietoris_rips",),
        parameters=(
            Parameter("period", "text", None, description="Period; empty selects the latest period with tax rules."),
            Parameter("include_topology", "bool", True, description="Include the persistent homology influence measure."),
        ),
        outputs={"readings": READING_COLUMNS, "agreement": AGREEMENT_COLUMNS, "classification": CLASS_COLUMNS,
                 "correlation": CORRELATION_COLUMNS, "engines": ENGINE_COLUMNS, "summary": SUMMARY_COLUMNS},
        output_keys={"readings": ("measure", "reading", "jurisdiction_id"), "agreement": ("jurisdiction_id", "measure"),
                     "classification": ("jurisdiction_id", "classification"), "correlation": ("measure_a", "measure_b"),
                     "engines": ("engine_id", "reading"), "summary": ("measure",)},
    )

    def validate(self, dataset: Dataset, params: dict[str, Any]) -> ValidationReport:
        r = ValidationReport()
        periods = sorted({row["period"] for row in dataset.tables["tax_domestic"]}
                         | {row["period"] for row in dataset.tables["entity_financials"]})
        if params.get("period") is None:
            params["period"] = periods[-1] if periods else None
        if params["period"] is None:
            r.error("no_period", "the dataset has neither tax rules nor revenue figures to compare", params={})
        return r

    def _run(self, dataset: Dataset, params: dict[str, Any]) -> EngineResult:
        warnings: list[str] = []
        engine_rows: list[dict[str, Any]] = []
        outputs: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = {}
        for eid, readings in READINGS.items():
            if eid == "ph.vietoris_rips" and not params["include_topology"]:
                continue
            for label, extra in readings:
                progress.report(len(engine_rows), sum(len(r) for r in READINGS.values()), f"{eid}: {label}")
                upstream = {"period": params["period"], **extra}
                try:
                    out, prov = run_upstream(dataset, eid, upstream, "the comparison")
                except UpstreamError as exc:
                    engine_rows.append({"engine_id": eid, "reading": label, "parameters": json.dumps(extra, sort_keys=True),
                                        "outcome": "unranked", "status": None, "outputs_sha256": None, "note": str(exc)[:300]})
                    continue
                outputs[(eid, label)] = out
                engine_rows.append({"engine_id": eid, "reading": label, "parameters": json.dumps(extra, sort_keys=True),
                                    "outcome": OK, "status": prov["status"], "outputs_sha256": prov["outputs_sha256"],
                                    "note": None})
        unranked = sorted({r["engine_id"] for r in engine_rows if r["outcome"] != OK})
        for eid in unranked:
            bad = [r for r in engine_rows if r["engine_id"] == eid and r["outcome"] != OK]
            warnings.append(f"{eid}: {len(bad)} reading(s) could not run and are unranked ({bad[0]['note']}).")
        if not outputs:
            return EngineResult(INVALID_INPUT, outputs={}, warnings=warnings + ["No engine could run on this dataset."])
        jurisdictions = sorted(j["jurisdiction_id"] for j in dataset.tables["jurisdictions"])

        # Values and ranks per measure and reading.
        reading_rows: list[dict[str, Any]] = []
        table: dict[str, dict[str, dict[str, tuple[float | None, int | None]]]] = {}
        for measure, (eid, out_table, column) in MEASURES.items():
            labels = [lab for lab, _ in READINGS[eid] if (eid, lab) in outputs]
            if not labels:
                continue
            table[measure] = {}
            for lab in labels:
                values = _values(outputs[(eid, lab)], measure, out_table, column, jurisdictions)
                ranks = _competition_ranks(values)
                table[measure][lab] = {j: (values.get(j), ranks.get(j)) for j in jurisdictions}
                for j in jurisdictions:
                    v, rk = table[measure][lab][j]
                    reading_rows.append({"measure": measure, "reading": lab, "jurisdiction_id": j, "value": _r(v), "rank": rk})

        # Agreement rule (plan s 6.3).
        agreement_rows = []
        for measure, by_reading in table.items():
            labels = list(by_reading)
            for j in jurisdictions:
                ranks = [by_reading[lab][j][1] for lab in labels]
                ranked = [r for r in ranks if r is not None]
                agreed = len(ranked) == len(labels) and len(set(ranked)) == 1
                agreement_rows.append({
                    "jurisdiction_id": j, "measure": measure, "readings": len(labels), "ranked_readings": len(ranked),
                    "rank_min": min(ranked) if ranked else None, "rank_max": max(ranked) if ranked else None,
                    "agreed": agreed, "rank": ranked[0] if agreed else None,
                    "value_default": _r(by_reading[labels[0]][j][0])})

        # Robustness shares of classifications (plan s 3.2).
        class_rows = []
        gb_labels = [lab for lab, _ in READINGS["gb2017.conduits_sinks"] if ("gb2017.conduits_sinks", lab) in outputs]
        if gb_labels:
            for cls, col in CLASSES.items():
                for j in jurisdictions:
                    hits = sum(1 for lab in gb_labels for row in outputs[("gb2017.conduits_sinks", lab)]["jurisdictions"]
                               if row["jurisdiction_id"] == j and row[col])
                    class_rows.append({"jurisdiction_id": j, "classification": cls, "readings": len(gb_labels),
                                       "classified_in": hits, "share": _r(hits / len(gb_labels)),
                                       "robust": hits == len(gb_labels)})

        # Rank correlations between measures, on each measure's default reading.
        corr_rows = []
        defaults = {m: by[next(iter(by))] for m, by in table.items()}
        for a, b in itertools.combinations(sorted(defaults), 2):
            xs, ys = [], []
            for j in jurisdictions:
                va, vb = defaults[a][j][0], defaults[b][j][0]
                if va is not None and vb is not None:
                    xs.append(va)
                    ys.append(vb)
            corr_rows.append({"measure_a": a, "measure_b": b, "n": len(xs), "spearman": _r(spearman(xs, ys)),
                              "kendall_tau_b": _r(kendall_tau_b(xs, ys))})

        n_cells = len(agreement_rows)
        n_agreed = sum(r["agreed"] for r in agreement_rows)
        summary = [
            {"measure": "period", "value": params["period"]},
            {"measure": "jurisdictions", "value": len(jurisdictions)},
            {"measure": "measures", "value": len(table)},
            {"measure": "readings_run", "value": len(outputs)},
            {"measure": "engines_unranked", "value": ", ".join(unranked) or "none"},
            {"measure": "rank_cells", "value": n_cells},
            {"measure": "rank_cells_agreed", "value": n_agreed},
            {"measure": "share_agreed", "value": _r(n_agreed / n_cells) if n_cells else None},
            {"measure": "lowest_engine_status", "value": _lowest_status(engine_rows)},
        ]
        trace = [
            {"step": 1, "description": "Run each engine under each documented reading", "detail": "; ".join(
                f"{e}: {len(r)}" for e, r in READINGS.items()), "result": f"{len(outputs)} ran, {len(engine_rows) - len(outputs)} unranked"},
            {"step": 2, "description": "Rank each measure under each reading", "detail": "descending; ties share the lower rank",
             "result": f"{len(table)} measures"},
            {"step": 3, "description": "Agreement rule (plan s 6.3)", "detail": "a rank only where every reading agrees",
             "result": f"{n_agreed} of {n_cells} jurisdiction-measure cells agreed"},
            {"step": 4, "description": "Robustness shares and rank correlations", "detail": "classification shares over gb2017 readings; "
             "Spearman and Kendall tau-b on default readings", "result": f"{len(corr_rows)} measure pairs"},
        ]
        assumptions = ["Higher values rank first for every measure; undefined values are unranked, never zero.",
                       "Measures are compared side by side; no combined score is computed (plan s 8).",
                       "Readings are the documented alternative interpretations of each source; other parameters are at "
                       "their defaults."]
        return EngineResult(OK, {"readings": reading_rows, "agreement": agreement_rows, "classification": class_rows,
                                 "correlation": corr_rows, "engines": engine_rows, "summary": summary}, trace, warnings,
                            assumptions)


def _values(out: dict[str, list[dict[str, Any]]], measure: str, table: str, column: str,
            jurisdictions: list[str]) -> dict[str, float]:
    if measure == "vtrl2018.shop_as_host":
        acc: dict[str, list[float]] = {}
        for row in out["pairs"]:
            acc.setdefault(row["host"], []).append(row["shop"])
        return {j: math.fsum(v) / len(v) for j, v in acc.items() if v}
    return {row["jurisdiction_id"]: float(row[column]) for row in out.get(table, [])
            if row.get(column) is not None}


def _competition_ranks(values: dict[str, float]) -> dict[str, int]:
    """1 for the highest value; equal values share the lower rank (1, 2, 2, 4). Equality is tested after
    rounding to 12 decimal places, so that floating-point noise does not split a tie."""
    ordered = sorted(values.items(), key=lambda kv: (-round(kv[1], 12), kv[0]))
    ranks: dict[str, int] = {}
    for i, (j, v) in enumerate(ordered):
        if i and round(v, 12) == round(ordered[i - 1][1], 12):
            ranks[j] = ranks[ordered[i - 1][0]]
        else:
            ranks[j] = i + 1
    return ranks


def _average_ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        k = i
        while k + 1 < len(order) and xs[order[k + 1]] == xs[order[i]]:
            k += 1
        for m in range(i, k + 1):
            ranks[order[m]] = (i + k) / 2 + 1
        i = k + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Spearman's rho: Pearson correlation of average ranks. None when undefined (fewer than 3 points or a
    constant variable)."""
    if len(xs) < 3:
        return None
    rx, ry = _average_ranks(xs), _average_ranks(ys)
    mx, my = math.fsum(rx) / len(rx), math.fsum(ry) / len(ry)
    sxy = math.fsum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = math.fsum((a - mx) ** 2 for a in rx)
    syy = math.fsum((b - my) ** 2 for b in ry)
    if sxx == 0 or syy == 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def kendall_tau_b(xs: list[float], ys: list[float]) -> float | None:
    """Kendall's tau-b, which corrects for ties in either variable."""
    n = len(xs)
    if n < 3:
        return None
    concordant = discordant = ties_x = ties_y = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx, dy = xs[i] - xs[j], ys[i] - ys[j]
            if dx == 0 and dy == 0:
                continue
            if dx == 0:
                ties_x += 1
            elif dy == 0:
                ties_y += 1
            elif (dx > 0) == (dy > 0):
                concordant += 1
            else:
                discordant += 1
    denom = math.sqrt((concordant + discordant + ties_x) * (concordant + discordant + ties_y))
    return None if denom == 0 else (concordant - discordant) / denom


def _lowest_status(rows: list[dict[str, Any]]) -> str:
    order = ["interface", "specified", "implemented", "verified", "replicated_with_discrepancies", "replicated"]
    found = [r["status"] for r in rows if r["status"] in order]
    return min(found, key=order.index) if found else "none"


def _r(x: float | None) -> float | None:
    return None if x is None else round(float(x), 12) + 0.0
