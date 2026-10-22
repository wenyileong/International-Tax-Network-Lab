"""Optimal tax routing: reproduction variant of van 't Riet and Lejour.

Specification: ``docs/specs/vtrl2018_tax_routing.md`` (v0.1, draft). Section and interpretation numbers
in comments (s 4, I5 and so on) refer to that document. The specification is a reconstruction from an
automated transcription of CPB Discussion Paper 349; until the author has checked it against the source,
this engine stays at ``implemented`` status and its results carry the "unverified" watermark.

Model in brief. For an ordered pair (S, P) the tax distance d_SP is the extra tax on repatriating a
dividend from S to P beyond S's corporate income tax (CIT):

* exemption: d = w_SP
* deduction: d = 1 - (1 - w_SP)(1 - t_P)
* credit:    d = max(w_SP, (t_P - t_S) / (1 - t_S))

A route composes multiplicatively, d(1,n) = 1 - prod(1 - d(k,k+1)), and the combined effective rate is
t^e = 1 - (1 - t_host)(1 - d). On legs after the first, where the next parent gives credit, the conduit's
creditable CIT is the world average excluding the conduit (s 5), which keeps legs independent of the path,
so a shortest-path search on -ln(1 - d) is exact.
"""

from __future__ import annotations

import heapq
import math
from collections import defaultdict
from typing import Any

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
from taxnetlab.schema import RATE_MAX, RELIEF_METHODS
from taxnetlab.validation import ValidationReport

SPEC = "docs/specs/vtrl2018_tax_routing.md v0.1 (draft)"
TIE_EPS = 1e-12
OVERRIDE_KINDS = ("cit", "wht", "relief", "treaty", "relief_pair")

PAIR_COLUMNS = ("host", "home", "direct_relief", "direct_wht", "direct_wht_basis", "direct_d", "direct_te",
                "best_d", "best_te", "best_route", "intermediates", "shop", "routes_in_range", "routes_strict",
                "enumeration_capped")
LEG_COLUMNS = ("host", "home", "leg", "from_jurisdiction", "to_jurisdiction", "relief_method", "wht_rate",
               "wht_basis", "payer_cit_used", "payer_cit_basis", "recipient_cit", "d_leg")
CENTRALITY_COLUMNS = ("jurisdiction_id", "btwns", "strct", "occur", "unwtd")
SUMMARY_COLUMNS = ("measure", "value")


class _World:
    """Resolved inputs for one period after scenario overrides."""

    def __init__(self, dataset: Dataset, params: dict[str, Any]):
        self.period = params["period"]
        dom = [r for r in dataset.tables["tax_domestic"] if r["period"] == self.period]
        self.codes = sorted(r["jurisdiction_id"] for r in dom)
        self.cit = {r["jurisdiction_id"]: r["cit_rate"] for r in dom}
        self.wht = {r["jurisdiction_id"]: r["dividend_wht_rate"] for r in dom}
        self.relief = {r["jurisdiction_id"]: r["relief_method"] for r in dom}
        self.treaty = {(r["payer_jurisdiction"], r["recipient_jurisdiction"]): r["dividend_wht_rate"]
                       for r in dataset.tables["tax_treaty_dividends"] if r["period"] == self.period}
        self.relief_pair = {(r["relieving_jurisdiction"], r["taxing_jurisdiction"]): r["relief_method"]
                            for r in dataset.tables["tax_relief_overrides"] if r["period"] == self.period}
        self.unverified = sum(1 for t in ("tax_domestic", "tax_treaty_dividends", "tax_relief_overrides")
                              for r in dataset.tables[t]
                              if r["period"] == self.period and not r["verified"]
                              and r["rule_status"] != "synthetic_assumption")
        self.gdp = _gdp(dataset, self.period)
        for o in params["overrides"]:
            kind, value = o["kind"], o.get("value")
            if kind == "cit":
                self.cit[o["jurisdiction"]] = float(value)
            elif kind == "wht":
                self.wht[o["jurisdiction"]] = float(value)
            elif kind == "relief":
                self.relief[o["jurisdiction"]] = value
            elif kind == "treaty":
                key = (o["payer"], o["recipient"])
                if value is None:
                    self.treaty.pop(key, None)
                else:
                    self.treaty[key] = float(value)
            elif kind == "relief_pair":
                key = (o["relieving"], o["taxing"])
                if value is None:
                    self.relief_pair.pop(key, None)
                else:
                    self.relief_pair[key] = value
        # I2: world average CIT excluding each jurisdiction.
        self.tbar: dict[str, float] = {}
        for k in self.codes:
            others = [j for j in self.codes if j != k]
            if not others:
                self.tbar[k] = self.cit[k]
            elif params["world_average"] == "gdp":
                total = sum(self.gdp[j] for j in others)
                self.tbar[k] = sum(self.cit[j] * self.gdp[j] for j in others) / total
            else:
                self.tbar[k] = sum(self.cit[j] for j in others) / len(others)
        self._leg_cache: dict[tuple[str, str, bool], dict[str, Any]] = {}

    def withholding(self, s: str, p: str) -> tuple[float, str]:
        if (s, p) in self.treaty:
            return self.treaty[(s, p)], "treaty"
        return self.wht[s], "general"  # I11

    def relief_of(self, p: str, s: str) -> str:
        return self.relief_pair.get((p, s), self.relief[p])  # I12

    def leg(self, s: str, p: str, first: bool) -> dict[str, Any]:
        key = (s, p, first)
        if key in self._leg_cache:
            return self._leg_cache[key]
        w, basis = self.withholding(s, p)
        method = self.relief_of(p, s)
        t_p = self.cit[p]
        if first:
            t_src, src_basis = self.cit[s], "statutory"
        elif method == "credit":
            t_src, src_basis = self.tbar[s], "world_average_excluding_conduit"  # s 5, I3
        else:
            t_src, src_basis = self.cit[s], "not_used"
        if method == "exemption":
            d = w
        elif method == "deduction":
            d = 1 - (1 - w) * (1 - t_p)
        else:
            d = max(w, (t_p - t_src) / (1 - t_src))
        d = min(max(d, 0.0), 1.0)
        info = {"from": s, "to": p, "relief": method, "w": w, "w_basis": basis, "t_src": t_src,
                "t_src_basis": src_basis, "t_p": t_p, "d": d,
                "cost": math.inf if d >= 1 else -math.log1p(-d)}  # I13
        self._leg_cache[key] = info
        return info


def _gdp(dataset: Dataset, period: str) -> dict[str, float]:
    """GDP per jurisdiction: the value for the period if present, otherwise the latest period."""
    best: dict[str, tuple[str, float]] = {}
    for a in dataset.tables["jurisdiction_attributes"]:
        if a["attribute"].lower() != "gdp":
            continue
        j, per = a["jurisdiction_id"], a["period"]
        cur = best.get(j)
        if cur is None or per == period or (cur[0] != period and per > cur[0]):
            best[j] = (per, a["value"])
    return {j: v for j, (_, v) in best.items()}


def _te(t_host: float, key: float) -> float:
    """Combined effective rate implied by a (penalised) log-retention cost."""
    return 1 - (1 - t_host) * math.exp(-key)


class TaxRoutingEngine(Engine):
    spec = EngineSpec(
        engine_id="vtrl2018.tax_routing",
        display_name="Optimal tax routing (van 't Riet and Lejour)",
        track=REPRODUCTION, variant="reproduction", version="0.1.0", status="implemented",
        spec_ref=SPEC,
        purpose="Routes for repatriated dividends that minimise tax, the treaty-shopping gain, and conduit "
                "betweenness, under the paper's assumptions (dividends only; statutory rates; exemption, credit "
                "or deduction relief; world-average creditable CIT for conduits).",
        boundary="Reproduction of a published model under documented interpretations. Not tax advice; statutory "
                 "rates only; anti-abuse rules, beneficial ownership and participation conditions are assumed "
                 "away as in the source. Implemented, not verified: the specification awaits the author's check.",
        next_step="Author check of the specification against CPB Discussion Paper 349 and the journal version; "
                  "then promotion to verified.",
        input_schema=("tax_domestic", "tax_treaty_dividends", "tax_relief_overrides", "jurisdiction_attributes (gdp)"),
        parameters=(
            Parameter("period", "text", None, description="Tax period to use; empty selects the latest period."),
            Parameter("penalty", "float", 0.0001, minimum=0.0, maximum=0.01, unit="log-retention per intermediate",
                      description="Small penalty per intermediate country (I5)."),
            Parameter("tolerance", "float", 0.005, minimum=0.0, maximum=0.05, unit="combined effective rate",
                      description="Range above the shortest route counted as shortest for BTWNS (I6)."),
            Parameter("max_intermediates", "int", 3, minimum=1, maximum=6,
                      description="Bound on intermediates when enumerating near-optimal routes (I14)."),
            Parameter("max_routes_per_pair", "int", 20000, minimum=100, maximum=200000,
                      description="Bound on enumerated routes per pair; reaching it is reported (I14)."),
            Parameter("route_budget", "int", 300000, minimum=1000, maximum=20000000,
                      description="Bound on routes enumerated across all pairs; afterwards the near-optimal set of the "
                                  "remaining pairs is limited to their strictly cheapest routes and flagged (I14)."),
            Parameter("world_average", "choice", "unweighted", choices=("unweighted", "gdp"),
                      description="Weighting of the world-average CIT used for conduits (I2)."),
            Parameter("centrality_weights", "choice", "gdp_product", choices=("gdp_product", "unweighted"),
                      description="Pair weights for BTWNS, STRCT, OCCUR and the averages (I8)."),
            Parameter("overrides", "overrides", [],
                      description="Scenario overrides: cit, wht, relief, treaty, relief_pair (spec s 9)."),
        ),
        measures=(
            Measure("vtrl2018.direct_d", "Tax distance of the direct route.", "1 - (1-t^e)/(1-t_S)", "none",
                    "share", "spec s 4"),
            Measure("vtrl2018.direct_te", "Combined effective rate of the direct route.", "1 - (1-t_S)(1-d)", "none",
                    "share", "spec s 4"),
            Measure("vtrl2018.best_te", "Combined effective rate of the cheapest route.", "1 - (1-t_S)(1-d(1,n))",
                    "none", "share", "spec s 5, 6"),
            Measure("vtrl2018.shop", "Treaty-shopping gain: direct minus cheapest combined effective rate.",
                    "t^e direct - t^e best", "none", "share", "spec s 7, I10"),
            Measure("vtrl2018.btwns", "Betweenness of a jurisdiction over near-optimal routes, pair-weighted.",
                    "sum of weight x routes through c / routes", "pair weights sum to 100", "percent",
                    "spec s 7, I8"),
            Measure("vtrl2018.strct", "As BTWNS over strictly shortest routes only.", "as BTWNS", "as BTWNS",
                    "percent", "spec s 7"),
            Measure("vtrl2018.occur", "Pair-weighted count of pairs with c on any near-optimal route.",
                    "sum of weight x [c on a route]", "pair weights sum to 100", "percent", "spec s 7, I9"),
            Measure("vtrl2018.unwtd", "As BTWNS with equal pair weights.", "as BTWNS", "equal weights sum to 100",
                    "percent", "spec s 7"),
        ),
        outputs={"pairs": PAIR_COLUMNS, "legs": LEG_COLUMNS, "centrality": CENTRALITY_COLUMNS,
                 "summary": SUMMARY_COLUMNS},
        output_keys={"pairs": ("host", "home"), "legs": ("host", "home", "leg"), "centrality": ("jurisdiction_id",),
                     "summary": ("measure",)},
    )

    # ------------------------------------------------------------------ parameters and validation
    def resolve_parameters(self, params):
        resolved, report = super().resolve_parameters(params)
        return resolved, report

    def validate(self, dataset: Dataset, params: dict[str, Any]) -> ValidationReport:
        r = ValidationReport()
        periods = sorted({row["period"] for row in dataset.tables["tax_domestic"]})
        if not periods:
            r.error("no_tax_data", "the dataset has no tax_domestic rows; this engine needs tax rules", params={})
            return r
        if params.get("period") is None:
            params["period"] = periods[-1]  # recorded in the run as the resolved value
        if params["period"] not in periods:
            r.error("unknown_period", f"no tax rules for period '{params['period']}'",
                    params={"period": params["period"], "periods": ", ".join(periods)})
            return r
        codes = {row["jurisdiction_id"] for row in dataset.tables["tax_domestic"] if row["period"] == params["period"]}
        if len(codes) < 2:
            r.error("too_few_jurisdictions", "at least two jurisdictions with tax rules are needed", params={})
        known = {j["jurisdiction_id"] for j in dataset.tables["jurisdictions"]}
        for o in params["overrides"]:
            self._check_override(o, codes, r)
        needs_gdp = params["centrality_weights"] == "gdp_product" or params["world_average"] == "gdp"
        if needs_gdp:
            gdp = _gdp(dataset, params["period"])
            missing = sorted(c for c in codes if not gdp.get(c, 0) > 0)
            if missing:
                r.error("gdp_missing", f"GDP needed for weights is missing or not positive for {missing}",
                        params={"ids": ", ".join(missing)})
        unknown_partners = {row["recipient_jurisdiction"] for row in dataset.tables["tax_treaty_dividends"]} - known
        if unknown_partners:
            r.error("unknown_jurisdiction", f"treaty partners not known: {sorted(unknown_partners)}",
                    params={"id": ", ".join(sorted(unknown_partners))})
        without = sorted(known - codes)
        if without:
            r.warning("jurisdictions_without_tax_rules",
                      f"{len(without)} jurisdiction(s) have no tax rules for the period and are left out",
                      params={"count": len(without), "ids": ", ".join(without[:20])})
        return r

    @staticmethod
    def _check_override(o: dict[str, Any], codes: set[str], r: ValidationReport) -> None:
        kind = o.get("kind")
        if kind not in OVERRIDE_KINDS:
            r.error("bad_override", f"unknown override kind {kind!r}", params={"kind": str(kind)})
            return
        fields = {"cit": ("jurisdiction",), "wht": ("jurisdiction",), "relief": ("jurisdiction",),
                  "treaty": ("payer", "recipient"), "relief_pair": ("relieving", "taxing")}[kind]
        extra = set(o) - set(fields) - {"kind", "value"}
        if extra:
            r.error("bad_override", f"unexpected override fields {sorted(extra)}", params={"kind": kind})
        for f in fields:
            if o.get(f) not in codes:
                r.error("bad_override", f"{kind}: '{o.get(f)}' is not a jurisdiction with tax rules",
                        params={"kind": kind})
                return
        if len(fields) == 2 and o[fields[0]] == o[fields[1]]:
            r.error("bad_override", f"{kind}: the two jurisdictions must differ", params={"kind": kind})
        value = o.get("value")
        if kind in ("cit", "wht") or (kind == "treaty" and value is not None):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= RATE_MAX:
                r.error("bad_override", f"{kind}: rate must be a number from 0 to {RATE_MAX}", params={"kind": kind})
        if kind == "relief" or (kind == "relief_pair" and value is not None):
            if value not in RELIEF_METHODS:
                r.error("bad_override", f"{kind}: relief must be one of {list(RELIEF_METHODS)}", params={"kind": kind})

    # ------------------------------------------------------------------ computation
    def _run(self, dataset: Dataset, params: dict[str, Any]) -> EngineResult:
        if params.get("period") is None or not dataset.tables["tax_domestic"]:
            report = self.validate(dataset, params)
            if not report.ok:
                return EngineResult(INVALID_INPUT, warnings=[i.message for i in report.errors])
        world = _World(dataset, params)
        codes = world.codes
        mu = params["penalty"]
        warnings: list[str] = []
        if world.unverified:
            warnings.append(f"{world.unverified} legal row(s) used are not verified.")

        # Admissible lower bounds h_P(u): cheapest cost from intermediate u to P on non-first legs,
        # with the penalty counted for u and every later intermediate (reverse Dijkstra).
        h: dict[str, dict[str, float]] = {p: self._reverse_bounds(world, p, mu) for p in codes}

        pair_rows, leg_rows = [], []
        sets: dict[tuple[str, str], dict[str, Any]] = {}
        capped_pairs = 0
        budget = params["route_budget"]
        budget_hit = False
        for s in codes:
            dist, prev = self._dijkstra(world, s, mu)
            for p in codes:
                if p == s:
                    continue
                direct = world.leg(s, p, True)
                t_s = world.cit[s]
                if math.isinf(dist.get(p, math.inf)):
                    continue  # no route can carry income (I13)
                route = self._path(prev, s, p)
                legs = [world.leg(route[i], route[i + 1], i == 0) for i in range(len(route) - 1)]
                d_best = 1 - math.prod(1 - lg["d"] for lg in legs)
                te_best = 1 - (1 - t_s) * (1 - d_best)
                te_direct = 1 - (1 - t_s) * (1 - direct["d"])
                m_best = len(route) - 2
                depth = max(params["max_intermediates"], m_best)
                key_best = dist[p]
                te_pen_best = _te(t_s, key_best)
                limit_strict = key_best + TIE_EPS
                bound = 1 - te_pen_best - params["tolerance"]
                limit_range = math.inf if bound <= 0 else -math.log(bound / (1 - t_s))
                per_pair = min(params["max_routes_per_pair"], max(budget, 1))
                rng = self._enumerate(world, s, p, max(limit_range, limit_strict) if not budget_hit else limit_strict,
                                      depth, h[p], mu, per_pair)
                if budget_hit:
                    rng["capped"] = True
                budget -= len(rng["routes"])
                if budget <= 0 and not budget_hit:
                    budget_hit = True
                strict_routes = [rt for rt, k in rng["routes"] if k <= limit_strict]
                range_routes = [rt for rt, k in rng["routes"] if k <= limit_range or k <= limit_strict]
                if not strict_routes:  # cannot happen: the Dijkstra route is within the depth bound
                    strict_routes = [route]
                capped = rng["capped"]
                capped_pairs += capped
                sets[(s, p)] = {"strict": strict_routes, "range": range_routes or strict_routes}
                pair_rows.append({
                    "host": s, "home": p, "direct_relief": direct["relief"], "direct_wht": direct["w"],
                    "direct_wht_basis": direct["w_basis"], "direct_d": _r(direct["d"]), "direct_te": _r(te_direct),
                    "best_d": _r(d_best), "best_te": _r(te_best), "best_route": ">".join(route),
                    "intermediates": m_best, "shop": _r(te_direct - te_best),
                    "routes_in_range": len(sets[(s, p)]["range"]), "routes_strict": len(strict_routes),
                    "enumeration_capped": capped,
                })
                for i, lg in enumerate(legs, start=1):
                    leg_rows.append({
                        "host": s, "home": p, "leg": i, "from_jurisdiction": lg["from"], "to_jurisdiction": lg["to"],
                        "relief_method": lg["relief"], "wht_rate": lg["w"], "wht_basis": lg["w_basis"],
                        "payer_cit_used": _r(lg["t_src"]), "payer_cit_basis": lg["t_src_basis"],
                        "recipient_cit": lg["t_p"], "d_leg": _r(lg["d"])})
        if budget_hit:
            warnings.append("The route budget was reached; for the remaining pairs only the strictly cheapest routes were "
                            "enumerated (flagged as enumeration_capped). Raise route_budget or lower max_intermediates.")
        if capped_pairs:
            warnings.append(f"Route enumeration reached max_routes_per_pair for {capped_pairs} pair(s); their "
                            "centrality contributions use the routes found (reported as enumeration_capped).")
        if not pair_rows:
            return EngineResult(INVALID_INPUT, warnings=["No pair of jurisdictions has a route that carries income."])

        weights = self._pair_weights(world, list(sets), params["centrality_weights"])
        equal = {k: 100.0 / len(sets) for k in sets}
        cent = {c: defaultdict(float) for c in codes}
        for (s, p), st in sets.items():
            for name, routes, wts, binary in (("btwns", st["range"], weights, False), ("strct", st["strict"], weights, False),
                                              ("occur", st["range"], weights, True), ("unwtd", st["range"], equal, False)):
                counts: dict[str, int] = defaultdict(int)
                for rt in routes:
                    for c in set(rt[1:-1]):
                        counts[c] += 1
                for c, n in counts.items():
                    cent[c][name] += wts[(s, p)] * (1.0 if binary else n / len(routes))
        centrality_rows = [{"jurisdiction_id": c, **{k: _r(cent[c][k]) for k in ("btwns", "strct", "occur", "unwtd")}}
                           for c in codes]

        def wavg(field: str) -> float:
            return sum(weights[(r["host"], r["home"])] * r[field] for r in pair_rows) / 100.0

        n = len(pair_rows)
        summary = [
            {"measure": "period", "value": world.period},
            {"measure": "jurisdictions", "value": len(codes)},
            {"measure": "pairs_with_route", "value": n},
            {"measure": "weights", "value": params["centrality_weights"]},
            {"measure": "avg_direct_d", "value": _r(wavg("direct_d"))},
            {"measure": "avg_best_d", "value": _r(wavg("best_d"))},
            {"measure": "avg_direct_te", "value": _r(wavg("direct_te"))},
            {"measure": "avg_best_te", "value": _r(wavg("best_te"))},
            {"measure": "avg_shop", "value": _r(wavg("shop"))},
            {"measure": "share_pairs_indirect_cheaper", "value": _r(sum(r["shop"] > TIE_EPS for r in pair_rows) / n)},
            {"measure": "share_pairs_zero_distance_direct", "value": _r(sum(r["direct_d"] <= TIE_EPS for r in pair_rows) / n)},
            {"measure": "share_pairs_zero_distance_best", "value": _r(sum(r["best_d"] <= TIE_EPS for r in pair_rows) / n)},
            {"measure": "avg_routes_in_range", "value": _r(sum(r["routes_in_range"] for r in pair_rows) / n)},
            {"measure": "avg_routes_strict", "value": _r(sum(r["routes_strict"] for r in pair_rows) / n)},
        ]
        trace = [
            {"step": 1, "description": "Resolve inputs", "detail": f"period {world.period}; {len(params['overrides'])} scenario override(s)",
             "result": f"{len(codes)} jurisdictions, {len(world.treaty)} treaty rates"},
            {"step": 2, "description": "World-average CIT excluding each conduit (s 5, I2)",
             "detail": params["world_average"], "result": ", ".join(f"{k} {world.tbar[k]:.4f}" for k in codes[:12])
             + (" ..." if len(codes) > 12 else "")},
            {"step": 3, "description": "Leg distances by relief method (s 4)", "detail": "exemption, deduction, credit",
             "result": f"{len(codes) * (len(codes) - 1)} ordered pairs"},
            {"step": 4, "description": "Cheapest routes: Dijkstra on -ln(1-d) + penalty per intermediate (s 6, I4, I5)",
             "detail": f"penalty {mu}", "result": f"{sum(r['shop'] > TIE_EPS for r in pair_rows)} pairs with a cheaper indirect route"},
            {"step": 5, "description": "Near-optimal routes (s 6, I6, I14)",
             "detail": f"tolerance {params['tolerance']}; up to {params['max_intermediates']} intermediates",
             "result": f"{capped_pairs} pair(s) capped"},
            {"step": 6, "description": "Centrality and averages (s 7, I8)", "detail": params["centrality_weights"],
             "result": "pair weights sum to 100"},
        ]
        assumptions = ["Interpretations I1 to I14 of the specification apply.",
                       "Dividends only; statutory rates; participation conditions assumed met (source A1 to A5)."]
        return EngineResult(OK, {"pairs": pair_rows, "legs": leg_rows, "centrality": centrality_rows,
                                 "summary": summary}, trace, warnings, assumptions)

    # ------------------------------------------------------------------ algorithms
    @staticmethod
    def _dijkstra(world: _World, s: str, mu: float) -> tuple[dict[str, float], dict[str, str]]:
        dist = {s: 0.0}
        prev: dict[str, str] = {}
        heap = [(0.0, 0, s)]
        hops = {s: 0}
        while heap:
            k, m, u = heapq.heappop(heap)
            if k > dist.get(u, math.inf) or (k == dist.get(u) and m > hops.get(u, m)):
                continue
            for v in world.codes:
                if v == u or v == s:
                    continue
                lg = world.leg(u, v, u == s)
                if math.isinf(lg["cost"]):
                    continue
                nk = k + lg["cost"] + (0.0 if u == s else mu)
                nm = m + (0 if u == s else 1)
                old = dist.get(v, math.inf)
                # Prefer the cheaper key; on an exact tie prefer fewer intermediates, then the smaller code.
                if nk < old - TIE_EPS or (abs(nk - old) <= TIE_EPS and (nm, u) < (hops.get(v, math.inf), prev.get(v, ""))):
                    dist[v], prev[v], hops[v] = nk, u, nm
                    heapq.heappush(heap, (nk, nm, v))
        return dist, prev

    @staticmethod
    def _path(prev: dict[str, str], s: str, p: str) -> list[str]:
        route = [p]
        while route[-1] != s:
            route.append(prev[route[-1]])
        return route[::-1]

    @staticmethod
    def _reverse_bounds(world: _World, p: str, mu: float) -> dict[str, float]:
        h = {p: 0.0}
        heap = [(0.0, p)]
        while heap:
            k, v = heapq.heappop(heap)
            if k > h.get(v, math.inf):
                continue
            for u in world.codes:
                if u == v:
                    continue
                lg = world.leg(u, v, False)
                if math.isinf(lg["cost"]):
                    continue
                nk = k + lg["cost"] + mu
                if nk < h.get(u, math.inf):
                    h[u] = nk
                    heapq.heappush(heap, (nk, u))
        return h

    @staticmethod
    def _enumerate(world: _World, s: str, p: str, limit: float, depth: int, h: dict[str, float], mu: float,
                   cap: int) -> dict[str, Any]:
        """All simple routes s -> p (s never revisited) with penalised cost <= limit and at most ``depth``
        intermediates. Pruned with the admissible bound h. Stops at ``cap`` routes and reports it."""
        routes: list[tuple[list[str], float]] = []
        capped = False
        stack = [(s, 0.0, [s])]
        while stack:
            u, g, path = stack.pop()
            for v in world.codes:
                if v == s or v in path:
                    continue
                lg = world.leg(u, v, u == s)
                if math.isinf(lg["cost"]):
                    continue
                ng = g + lg["cost"] + (0.0 if u == s else mu)
                if v == p:
                    if ng <= limit + TIE_EPS:
                        routes.append((path + [p], ng))
                        if len(routes) >= cap:
                            return {"routes": routes, "capped": True}
                    continue
                if len(path) - 1 >= depth:  # adding v would exceed the intermediate bound
                    continue
                if ng + h.get(v, math.inf) > limit + TIE_EPS:
                    continue
                stack.append((v, ng, path + [v]))
        return {"routes": routes, "capped": capped}

    @staticmethod
    def _pair_weights(world: _World, pairs: list[tuple[str, str]], mode: str) -> dict[tuple[str, str], float]:
        if mode == "unweighted":
            return {k: 100.0 / len(pairs) for k in pairs}
        raw = {(s, p): world.gdp[s] * world.gdp[p] for s, p in pairs}
        total = sum(raw.values())
        return {k: 100.0 * v / total for k, v in raw.items()}


def _r(x: float) -> float:
    """Round for storage: 12 decimal places keeps hashes stable across platforms' last-bit differences."""
    return round(float(x), 12)
