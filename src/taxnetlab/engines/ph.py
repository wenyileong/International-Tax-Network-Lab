"""Persistent homology of jurisdictions (Vietoris–Rips filtration): an alternative topological method.

Specification: ``docs/specs/ph_vietoris_rips.md`` (v0.1); section numbers in comments refer to it. This
engine is one of the alternatives recorded in plan v2.4, s 9.4. Under design constraints D1 to D5 it uses no
lens, no cover, no clustering within cover elements and no graph of clusters, so it is separate from the
patent-method engine ``us10417262.tda``, which stays at ``interface`` behind the IP gate.

Two inputs (s 3): a declared FeatureMatrix of jurisdictions (``features``), or a network-native distance,
the cost of the cheapest tax route between two jurisdictions under van 't Riet and Lejour
(``routing_cost``).
"""

from __future__ import annotations

import math
from typing import Any

from taxnetlab import progress
from taxnetlab import features as fm
from taxnetlab.canonical import canonical_json, sha256_text
from taxnetlab.datasets import Dataset
from taxnetlab.engines.base import (
    INVALID_INPUT,
    OK,
    REPRODUCTION,
    Engine,
    EngineResult,
    EngineSpec,
    Measure,
    Parameter,
)
from taxnetlab.engines.upstream import UpstreamError, run_upstream
from taxnetlab.topology import Bar, betti_curve, bottleneck, classical_mds, rips_persistence
from taxnetlab.validation import ValidationReport

SPEC = "docs/specs/ph_vietoris_rips.md v0.1"
MEMBER_LIMIT = 60

POINT_COLUMNS = ("jurisdiction_id", "included", "missing_features", "x", "y")
FEATURE_COLUMNS = ("jurisdiction_id", "feature", "raw", "scaled")
DISTANCE_COLUMNS = ("a", "b", "distance")
DIAGRAM_COLUMNS = ("feature_id", "dimension", "birth", "death", "persistence", "essential", "birth_simplex",
                   "death_simplex", "members", "representative_cycle")
BETTI_COLUMNS = ("step", "scale", "b0", "b1")
INFLUENCE_COLUMNS = ("jurisdiction_id", "bottleneck_h0", "bottleneck_h1", "rank_h1")
SUMMARY_COLUMNS = ("measure", "value")


_Upstream = UpstreamError


class PersistentHomologyEngine(Engine):
    spec = EngineSpec(
        engine_id="ph.vietoris_rips",
        display_name="Persistent homology (Vietoris–Rips)",
        track=REPRODUCTION, variant="reproduction", version="0.1.0", status="implemented",
        spec_ref=SPEC,
        purpose="The shape of jurisdictions in tax-attribute space, or in tax-routing cost: clusters (H0) and "
                "loops (H1) across all scales, how long each persists, and how much each jurisdiction shapes them.",
        boundary="Published mathematical method (Edelsbrunner, Letscher and Zomorodian 2002; Zomorodian and Carlsson "
                 "2005; stability: Cohen-Steiner, Edelsbrunner and Harer 2007) applied to declared feature "
                 "matrices. No lens, cover, clustering within cover elements or graph of clusters (spec s 2). "
                 "Topological features describe the chosen features and metric, not conduct; no inference of "
                 "avoidance or illegality.",
        next_step="Author check of the specification and of plan s 9.4; landscape search before public distribution.",
        input_schema=("jurisdictions", "tax_domestic", "tax_treaty_dividends", "jurisdiction_attributes (gdp)",
                      "entities", "ownership", "engine outputs as declared features"),
        parameters=(
            Parameter("input", "choice", "features", choices=("features", "routing_cost"),
                      description="Distances from a feature matrix, or from the cost of the cheapest tax route (s 3)."),
            Parameter("features", "text", fm.DEFAULT_FEATURES,
                      description="Comma-separated feature identifiers (s 3.1)."),
            Parameter("period", "text", None, description="Period; empty selects the latest period with tax rules."),
            Parameter("scaling", "choice", "zscore", choices=fm.SCALINGS,
                      description="Feature scaling before distances (s 3.1)."),
            Parameter("metric", "choice", "euclidean", choices=fm.METRICS, description="Distance between rows."),
            Parameter("symmetrise", "choice", "max", choices=("max", "mean"),
                      description="Routing cost is directional; combine the two directions (s 3.2)."),
            Parameter("max_dimension", "int", 1, minimum=0, maximum=1,
                      description="Highest homology dimension computed (0: clusters; 1: also loops)."),
            Parameter("max_scale", "float", 0.0, minimum=0.0, maximum=1e12,
                      description="Truncate the filtration at this scale; 0 means no truncation (s 4.5)."),
            Parameter("simplex_budget", "int", 3_000_000, minimum=1000, maximum=50_000_000,
                      description="Bound on triangles; reaching it truncates the filtration and is reported (s 4.5)."),
            Parameter("influence", "bool", True,
                      description="Leave-one-out influence of each jurisdiction on the diagrams (s 5.3)."),
            Parameter("influence_limit", "int", 40, minimum=3, maximum=300,
                      description="Influence is computed only up to this many observations (cost grows quickly)."),
        ),
        measures=(
            Measure("ph.persistence", "Lifetime of a topological feature: death scale minus birth scale.",
                    "death - birth", "none", "distance units", "spec s 4"),
            Measure("ph.betti_0", "Number of clusters (connected components) at a scale.", "count", "none",
                    "count", "spec s 5.1"),
            Measure("ph.betti_1", "Number of independent loops at a scale.", "count", "none", "count", "spec s 5.1"),
            Measure("ph.influence_h1", "Bottleneck distance between the H1 diagram with and without the jurisdiction.",
                    "d_B(Dgm_1(X), Dgm_1(X minus j))", "none", "distance units", "spec s 5.3"),
            Measure("ph.influence_h0", "As influence_h1, for H0.", "d_B(Dgm_0(X), Dgm_0(X minus j))", "none",
                    "distance units", "spec s 5.3"),
        ),
        outputs={"points": POINT_COLUMNS, "features": FEATURE_COLUMNS, "distances": DISTANCE_COLUMNS,
                 "diagram": DIAGRAM_COLUMNS, "betti": BETTI_COLUMNS, "influence": INFLUENCE_COLUMNS,
                 "summary": SUMMARY_COLUMNS},
        output_keys={"points": ("jurisdiction_id",), "features": ("jurisdiction_id", "feature"),
                     "distances": ("a", "b"), "diagram": ("feature_id",), "betti": ("step",),
                     "influence": ("jurisdiction_id",), "summary": ("measure",)},
    )

    # ------------------------------------------------------------------ validation
    def validate(self, dataset: Dataset, params: dict[str, Any]) -> ValidationReport:
        r = ValidationReport()
        periods = sorted({row["period"] for row in dataset.tables["tax_domestic"]})
        if params.get("period") is None:
            fallback = sorted({a["period"] for a in dataset.tables["jurisdiction_attributes"]})
            params["period"] = (periods or fallback or [None])[-1]
        period_free = {"outward_links", "inward_links"}  # current holdings: no period needed
        if params["input"] == "routing_cost":
            if params["period"] is None:
                r.error("no_period", "the dataset has neither tax rules nor jurisdiction attributes", params={})
            elif params["period"] not in periods:
                r.error("unknown_period", f"no tax rules for period '{params['period']}'",
                        params={"period": params["period"], "periods": ", ".join(periods)})
            return r
        ids, unknown = fm.parse_features(params["features"])
        if unknown:
            r.error("unknown_feature", f"unknown feature(s) {unknown}; known: {sorted(fm.CATALOGUE)}",
                    params={"ids": ", ".join(unknown)})
        if not ids:
            r.error("no_features", "select at least one feature", params={})
        if params["period"] is None and set(ids) - period_free:
            r.error("no_period", "the dataset has neither tax rules nor jurisdiction attributes; without them only "
                    "the features outward_links and inward_links can be used", params={})
            return r
        needs_tax = {"cit", "dividend_wht", "mean_applicable_wht", "treaty_count", "vtrl_btwns", "vtrl_mean_shop"}
        if needs_tax & set(ids) and params["period"] not in periods:
            r.error("unknown_period", f"no tax rules for period '{params['period']}'",
                    params={"period": params["period"], "periods": ", ".join(periods)})
        if not unknown:
            params["features"] = ",".join(ids)  # recorded in canonical form
        return r

    # ------------------------------------------------------------------ computation
    def _run(self, dataset: Dataset, params: dict[str, Any]) -> EngineResult:
        warnings: list[str] = []
        provenance: list[dict[str, Any]] = []

        def runner(engine_id: str, upstream: dict[str, Any]):
            outputs, prov = run_upstream(dataset, engine_id, upstream, "these features")
            provenance.append(prov)
            if prov["status"] not in ("verified", "replicated", "replicated_with_discrepancies"):
                warnings.append(f"Features use {engine_id} at '{prov['status']}' status (not verified).")
            return outputs, prov

        try:
            if params["input"] == "features":
                matrix = fm.build(dataset, params["period"], params["features"].split(","), params["scaling"], runner)
                names = matrix.observations
                vectors = [matrix.scaled[j] for j in names]
                D = [[fm.distance(u, v, params["metric"]) for v in vectors] for u in vectors]
                matrix_hash = matrix.matrix_sha256
            else:
                matrix = None
                names, D = _routing_distances(runner, params)
                matrix_hash = sha256_text(canonical_json({"routing_cost": D, "names": names}))
        except _Upstream as exc:
            return EngineResult(INVALID_INPUT, warnings=[str(exc)])

        excluded = matrix.excluded if matrix else {}
        if excluded:
            warnings.append(f"{len(excluded)} jurisdiction(s) excluded for missing features (never imputed): "
                            + "; ".join(f"{j} ({', '.join(m)})" for j, m in sorted(excluded.items())[:12]))
        if matrix and matrix.constant:
            warnings.append(f"Feature(s) without variation contribute nothing to distances: {', '.join(matrix.constant)}.")
        if len(names) < 3:
            return EngineResult(INVALID_INPUT, warnings=warnings + [
                f"Only {len(names)} jurisdiction(s) have every selected feature; at least 3 are needed."])
        unverified = sum(1 for t in ("tax_domestic", "tax_treaty_dividends") for row in dataset.tables[t]
                         if row["period"] == params["period"] and not row["verified"]
                         and row["rule_status"] != "synthetic_assumption")
        if unverified:
            warnings.append(f"{unverified} legal row(s) used are not verified.")

        max_scale = params["max_scale"] or None
        pers = rips_persistence(D, params["max_dimension"], max_scale, params["simplex_budget"])
        if pers.budget_reached:
            warnings.append(f"The simplex budget ({params['simplex_budget']}) was reached; the filtration was "
                            f"truncated at scale {_r(pers.max_scale)} and classes alive there are reported as "
                            "essential. Raise simplex_budget or set max_scale.")

        # Diagram rows: most persistent first within each dimension (essential classes first).
        def sort_key(b: Bar):
            return (b.dimension, 0 if b.death is None else 1, -(b.persistence or 0.0), b.birth, b.birth_simplex)

        diagram_rows = []
        ids: dict[int, str] = {}
        counters = {0: 0, 1: 0}
        bars = sorted(pers.bars, key=sort_key)
        for b in bars:
            counters[b.dimension] += 1
            fid = f"H{b.dimension}-{counters[b.dimension]:04d}"
            ids[id(b)] = fid
            members = [names[m] for m in b.members]
            diagram_rows.append({
                "feature_id": fid, "dimension": b.dimension, "birth": _r(b.birth), "death": _r(b.death),
                "persistence": _r(b.persistence), "essential": b.death is None,
                "birth_simplex": ",".join(names[v] for v in b.birth_simplex),
                "death_simplex": ",".join(names[v] for v in b.death_simplex) if b.death_simplex else None,
                "members": (", ".join(members[:MEMBER_LIMIT]) + (f" (+{len(members) - MEMBER_LIMIT} more)"
                                                                  if len(members) > MEMBER_LIMIT else "")) or None,
                "representative_cycle": ">".join(names[v] for v in b.cycle) or None,
            })
        betti_rows = [{"step": k, "scale": _r(e), "b0": b0, "b1": b1 if params["max_dimension"] >= 1 else None}
                      for k, (e, b0, b1) in enumerate(betti_curve(pers))]

        # Influence (s 5.3): leave one jurisdiction out and compare diagrams in bottleneck distance.
        influence_rows: list[dict[str, Any]] = []
        n = len(names)
        do_influence = params["influence"] and n > 3
        if params["influence"] and n > params["influence_limit"]:
            do_influence = False
            warnings.append(f"Influence not computed: {n} observations exceed influence_limit "
                            f"({params['influence_limit']}).")
        if do_influence:
            for k in range(n):
                progress.report(k, n, "influence")
                Dk = [[D[i][j] for j in range(n) if j != k] for i in range(n) if i != k]
                q = rips_persistence(Dk, params["max_dimension"], max_scale, params["simplex_budget"])
                h0 = bottleneck(pers.diagram(0), q.diagram(0))
                h1 = bottleneck(pers.diagram(1), q.diagram(1)) if params["max_dimension"] >= 1 else None
                influence_rows.append({"jurisdiction_id": names[k], "bottleneck_h0": _r(h0), "bottleneck_h1": _r(h1)})
            ranked = sorted(influence_rows, key=lambda r: (-(r["bottleneck_h1"] or 0.0), r["jurisdiction_id"]))
            for rank, row in enumerate(ranked, 1):
                row["rank_h1"] = rank if params["max_dimension"] >= 1 else None

        # Display projection (s 6, D4): drawn, never read by the computation above.
        coords, _, converged = classical_mds(D)
        stress = _stress(D, coords)
        if not converged:
            warnings.append("The display projection did not fully converge; the computation does not use it.")
        all_names = sorted(set(names) | set(excluded))
        index = {j: i for i, j in enumerate(names)}
        point_rows = [{"jurisdiction_id": j, "included": j in index,
                       "missing_features": ", ".join(excluded.get(j, [])) or None,
                       "x": _r(coords[index[j]][0], 9) if j in index else None,
                       "y": _r(coords[index[j]][1], 9) if j in index else None} for j in all_names]
        feature_rows = []
        if matrix:
            for j in all_names:
                for pos, f in enumerate(matrix.features):
                    feature_rows.append({"jurisdiction_id": j, "feature": f.feature_id,
                                         "raw": _r(matrix.raw[j][f.feature_id]),
                                         "scaled": _r(matrix.scaled[j][pos]) if j in matrix.scaled else None})
        distance_rows = [{"a": names[i], "b": names[j], "distance": _r(D[i][j])}
                         for i in range(n) for j in range(i + 1, n)]

        h1 = [row for row in diagram_rows if row["dimension"] == 1]
        top = h1[0] if h1 else None
        top_infl = min(influence_rows, key=lambda r: r["rank_h1"] or 0) if influence_rows and h1 else None
        summary = [
            {"measure": "input", "value": params["input"]},
            {"measure": "period", "value": params["period"]},
            {"measure": "observations", "value": n},
            {"measure": "excluded", "value": ", ".join(sorted(excluded)) or "none"},
            {"measure": "feature_matrix_sha256", "value": matrix_hash},
            {"measure": "features", "value": params["features"] if matrix else "routing cost"},
            {"measure": "edges", "value": pers.edges},
            {"measure": "triangles", "value": pers.triangles},
            {"measure": "max_scale_effective", "value": _r(pers.max_scale) if pers.max_scale is not None else "none"},
            {"measure": "simplex_budget_reached", "value": pers.budget_reached},
            {"measure": "h0_bars", "value": sum(1 for row in diagram_rows if row["dimension"] == 0)},
            {"measure": "h1_bars", "value": len(h1)},
            {"measure": "h1_most_persistent", "value": f"{top['feature_id']} ({top['persistence']})" if top else "none"},
            {"measure": "duplicate_points", "value": pers.zero_pairs[0]},
            {"measure": "projection_stress", "value": _r(stress, 6)},
            {"measure": "influence_computed", "value": bool(influence_rows)},
            {"measure": "most_influential_h1", "value": top_infl["jurisdiction_id"] if top_infl else "none"},
        ]
        trace = [
            {"step": 1, "description": "Observations and distances (s 3)",
             "detail": (f"features {params['features']}; scaling {params['scaling']}; metric {params['metric']}"
                        if matrix else f"routing cost -ln(1 - d), symmetrised by {params['symmetrise']}"),
             "result": f"{n} jurisdictions; matrix {matrix_hash[:16]}"},
            {"step": 2, "description": "Vietoris–Rips filtration (s 4.1, 4.5)",
             "detail": f"max scale {params['max_scale'] or 'none'}; budget {params['simplex_budget']}",
             "result": f"{pers.edges} edges, {pers.triangles} triangles"},
            {"step": 3, "description": "Persistence pairs (s 4.2, 4.3)",
             "detail": "H0 by union-find; H1 by persistent cohomology with clearing",
             "result": f"{summary[10]['value']} H0 and {len(h1)} H1 bars"},
            {"step": 4, "description": "Influence (s 5.3)", "detail": "leave one out; bottleneck distance",
             "result": "computed" if influence_rows else "not computed"},
            {"step": 5, "description": "Display projection (s 6)", "detail": "classical MDS; display only (D4)",
             "result": f"Kruskal stress {round(stress, 3)}"},
        ]
        assumptions = ["Rips complex: a simplex enters when its longest edge does (s 4.1).",
                       "Stability: changing any distance by at most delta moves each diagram by at most delta in "
                       "bottleneck distance (Cohen-Steiner, Edelsbrunner and Harer 2007; spec s 5.2).",
                       "Missing values are never imputed; observations lacking a feature are excluded.",
                       "The two-dimensional projection is for display only and is approximate."]
        return EngineResult(OK, {"points": point_rows, "features": feature_rows, "distances": distance_rows,
                                 "diagram": diagram_rows, "betti": betti_rows, "influence": influence_rows,
                                 "summary": summary}, trace, warnings, assumptions)


def _routing_distances(runner, params: dict[str, Any]) -> tuple[list[str], list[list[float]]]:
    outputs, _ = runner("vtrl2018.tax_routing", {"period": params["period"]})
    cost: dict[tuple[str, str], float] = {}
    for row in outputs["pairs"]:
        cost[(row["host"], row["home"])] = -math.log(1.0 - row["best_d"]) if row["best_d"] < 1 else math.inf
    names = sorted({a for a, _ in cost} | {b for _, b in cost})
    D = [[0.0] * len(names) for _ in names]
    for i, a in enumerate(names):
        for j in range(i + 1, len(names)):
            b = names[j]
            u, v = cost.get((a, b)), cost.get((b, a))
            if u is None or v is None or math.isinf(u) or math.isinf(v):
                raise _Upstream(f"routing cost missing or unbounded between {a} and {b}")
            d = max(u, v) if params["symmetrise"] == "max" else (u + v) / 2
            D[i][j] = D[j][i] = d
    return names, D


def _stress(D: list[list[float]], coords: list[list[float]]) -> float:
    """Kruskal stress-1 of the display projection: 0 is exact; above about 0.2 the picture misleads."""
    num = den = 0.0
    n = len(D)
    for i in range(n):
        for j in range(i + 1, n):
            dh = math.dist(coords[i], coords[j])
            num += (D[i][j] - dh) ** 2
            den += D[i][j] ** 2
    return math.sqrt(num / den) if den > 0 else 0.0


def _r(x: float | None, digits: int = 12) -> float | None:
    return None if x is None else round(float(x), digits) + 0.0
