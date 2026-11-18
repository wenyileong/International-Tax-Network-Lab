"""Sensitivity sweeps and robustness shares (plan v2.5, s 3.2 status `robust`, s 6.3, Phase 8).

Runs one method engine over a grid of parameter values and reports, for every jurisdiction, how its rank on a
chosen measure varies, the share of draws in which it is in the top k, and (for the conduits and sinks engine)
the share of draws in which it is classified as a sink or conduit. Draws whose outcome is not ``ok`` are counted
and excluded, never treated as zero (plan s 6.3). Specification: ``docs/specs/sensitivity.md``.
"""

from __future__ import annotations

import itertools
import json
import statistics
from typing import Any

from taxnetlab import progress
from taxnetlab.datasets import Dataset
from taxnetlab.engines.base import INVALID_INPUT, OK, ORIGINAL, Engine, EngineResult, EngineSpec, Parameter
from taxnetlab.engines.compare import CLASSES, MEASURES, _competition_ranks, _values
from taxnetlab.engines.upstream import UpstreamError, run_upstream
from taxnetlab.validation import ValidationReport

SPEC = "docs/specs/sensitivity.md v0.1"
MAX_DRAWS = 200
TARGETS = ("vtrl2018.tax_routing", "gb2017.conduits_sinks", "ph.vietoris_rips")

DRAW_COLUMNS = ("draw", "parameters", "outcome", "note")
VALUE_COLUMNS = ("draw", "jurisdiction_id", "value", "rank")
ROBUST_COLUMNS = ("jurisdiction_id", "draws_ranked", "rank_min", "rank_max", "rank_median", "share_top_k",
                  "share_sink", "share_conduit", "robust_top_k")
SUMMARY_COLUMNS = ("measure", "value")


def parse_grid(text: str | None) -> dict[str, list[str]]:
    """``name=v1|v2|v3; other=a|b`` -> {name: [v1, v2, v3], other: [a, b]} (values as text)."""
    grid: dict[str, list[str]] = {}
    for part in (text or "").split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"'{part}': expected name=value1|value2")
        name, values = part.split("=", 1)
        vals = [v.strip() for v in values.split("|") if v.strip()]
        if not name.strip() or not vals:
            raise ValueError(f"'{part}': expected name=value1|value2")
        grid[name.strip()] = vals
    return grid


class SensitivityEngine(Engine):
    spec = EngineSpec(
        engine_id="sensitivity.sweep",
        display_name="Sensitivity sweep (robustness shares)",
        track=ORIGINAL, variant="original", version="0.1.0", status="implemented",
        spec_ref=SPEC,
        purpose="Re-runs a method engine over a grid of parameter values and reports how stable each jurisdiction's "
                "rank and classification are: rank range, share of draws in the top k, share of draws classified.",
        boundary="Describes the sensitivity of a method's outputs to its parameters; adds no measure of its own. Its "
                 "status is bounded by that of the engine it sweeps.",
        next_step="Author check of the specification.",
        input_schema=("as the swept engine",),
        parameters=(
            Parameter("engine", "choice", "gb2017.conduits_sinks", choices=TARGETS, description="Engine to sweep."),
            Parameter("grid", "text", "sink_threshold=5|10|20; ownership_threshold=0.0001|0.001|0.01",
                      description="Parameter values: name=v1|v2; other=a|b (every combination is run)."),
            Parameter("measure", "text", "gb2017.sink_centrality",
                      description="Namespaced measure ranked in each draw (as on the Compare page)."),
            Parameter("top_k", "int", 5, minimum=1, maximum=100, description="Size of the top group whose stability is reported."),
            Parameter("robust_share", "float", 0.9, minimum=0.5, maximum=1.0,
                      description="Share of draws at or above which a top-k membership is called robust."),
            Parameter("period", "text", None, description="Period; empty selects the latest."),
        ),
        outputs={"draws": DRAW_COLUMNS, "values": VALUE_COLUMNS, "robustness": ROBUST_COLUMNS, "summary": SUMMARY_COLUMNS},
        output_keys={"draws": ("draw",), "values": ("draw", "jurisdiction_id"), "robustness": ("jurisdiction_id",),
                     "summary": ("measure",)},
    )

    def validate(self, dataset: Dataset, params: dict[str, Any]) -> ValidationReport:
        r = ValidationReport()
        from taxnetlab.engines import get_engine

        target = get_engine(params["engine"])
        try:
            grid = parse_grid(params["grid"])
        except ValueError as exc:
            r.error("bad_grid", str(exc), params={"detail": str(exc)})
            return r
        known = {p.name for p in target.spec.parameters}
        for name in grid:
            if name not in known or name == "period":
                r.error("bad_grid", f"'{name}' is not a parameter of {params['engine']} that can be swept",
                        params={"detail": name})
        draws = 1
        for vals in grid.values():
            draws *= len(vals)
        if draws > MAX_DRAWS:
            r.error("bad_grid", f"{draws} combinations exceed the limit of {MAX_DRAWS}", params={"detail": str(draws)})
        m = MEASURES.get(params["measure"])
        if m is None or m[0] != params["engine"]:
            ok = sorted(k for k, v in MEASURES.items() if v[0] == params["engine"])
            r.error("bad_measure", f"measure must be one of {ok} for {params['engine']}", params={"detail": ", ".join(ok)})
        if r.ok:  # every value must be valid for the target engine
            for name, vals in grid.items():
                for v in vals:
                    _, rep = target.resolve_parameters({name: _typed(v)})
                    if not rep.ok:
                        r.error("bad_grid", f"{name}={v}: " + "; ".join(i.message for i in rep.errors),
                                params={"detail": f"{name}={v}"})
        if params.get("period") is None and r.ok:
            # the swept engine's own default period (its revenue period for gb2017, tax period for vtrl2018 ...),
            # so that a default sweep runs wherever the engine itself runs
            tp, _ = target.resolve_parameters({})
            target.validate(dataset, tp)
            params["period"] = tp.get("period")
        return r

    def _run(self, dataset: Dataset, params: dict[str, Any]) -> EngineResult:
        grid = parse_grid(params["grid"])
        names = list(grid)
        combos = list(itertools.product(*(grid[n] for n in names))) if names else [()]
        eid, (_, table, column) = params["engine"], MEASURES[params["measure"]]
        jurisdictions = sorted(j["jurisdiction_id"] for j in dataset.tables["jurisdictions"])
        draws, values, ranks, classified = [], [], {}, {}
        for d, combo in enumerate(combos, 1):
            progress.report(d - 1, len(combos), f"draw {d} of {len(combos)}")
            setting = {n: _typed(v) for n, v in zip(names, combo)}
            upstream = {"period": params["period"], **setting} if params["period"] else dict(setting)
            try:
                out, _ = run_upstream(dataset, eid, upstream, "the sweep")
            except UpstreamError as exc:
                draws.append({"draw": d, "parameters": json.dumps(setting, sort_keys=True), "outcome": "excluded",
                              "note": str(exc)[:300]})
                continue
            draws.append({"draw": d, "parameters": json.dumps(setting, sort_keys=True), "outcome": OK, "note": None})
            vals = _values(out, params["measure"], table, column, jurisdictions)
            rk = _competition_ranks(vals)
            ranks[d] = rk
            for j in jurisdictions:
                values.append({"draw": d, "jurisdiction_id": j, "value": _r(vals.get(j)), "rank": rk.get(j)})
            if eid == "gb2017.conduits_sinks":
                classified[d] = {cls: {row["jurisdiction_id"] for row in out["jurisdictions"] if row[col]}
                                 for cls, col in CLASSES.items()}
        ok_draws = sorted(ranks)
        if not ok_draws:
            return EngineResult(INVALID_INPUT, warnings=["No draw could run: " + (draws[0]["note"] if draws else "empty grid")])
        k, thr = params["top_k"], params["robust_share"]
        robust_rows = []
        for j in jurisdictions:
            rs = [ranks[d][j] for d in ok_draws if j in ranks[d]]
            in_top = sum(1 for d in ok_draws if ranks[d].get(j) is not None and ranks[d][j] <= k)
            row = {"jurisdiction_id": j, "draws_ranked": len(rs), "rank_min": min(rs) if rs else None,
                   "rank_max": max(rs) if rs else None, "rank_median": _r(statistics.median(rs)) if rs else None,
                   "share_top_k": _r(in_top / len(ok_draws)),
                   "share_sink": _r(sum(j in classified[d]["gb2017.sink_ofc"] for d in ok_draws) / len(ok_draws)) if classified else None,
                   "share_conduit": _r(sum(j in classified[d]["gb2017.conduit_ofc"] for d in ok_draws) / len(ok_draws)) if classified else None}
            row["robust_top_k"] = in_top / len(ok_draws) >= thr
            robust_rows.append(row)
        excluded = len(draws) - len(ok_draws)
        robust = sorted(r["jurisdiction_id"] for r in robust_rows if r["robust_top_k"])
        summary = [
            {"measure": "engine", "value": eid}, {"measure": "measure", "value": params["measure"]},
            {"measure": "draws", "value": len(draws)}, {"measure": "draws_excluded", "value": excluded},
            {"measure": "top_k", "value": k}, {"measure": "robust_share", "value": thr},
            {"measure": "robust_top_k", "value": ", ".join(robust) or "none"},
        ]
        warnings = [f"{excluded} draw(s) could not run and are excluded (counted, never set to zero)."] if excluded else []
        trace = [{"step": 1, "description": "Grid", "detail": params["grid"], "result": f"{len(draws)} draws"},
                 {"step": 2, "description": "Ranks per draw", "detail": params["measure"], "result": f"{len(ok_draws)} ranked"},
                 {"step": 3, "description": "Robustness shares", "detail": f"top {k}; robust at {thr}",
                  "result": ", ".join(robust) or "none"}]
        return EngineResult(OK, {"draws": draws, "values": values, "robustness": robust_rows, "summary": summary}, trace,
                            warnings, ["Every combination of the grid is run once; other parameters stay at their defaults."])


def _typed(text: str) -> Any:
    t = text.strip()
    if t.lower() in ("true", "false"):
        return t.lower() == "true"
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        return t


def _r(x: float | None) -> float | None:
    return None if x is None else round(float(x), 12) + 0.0
