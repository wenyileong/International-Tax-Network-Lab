"""Independent checks of the economic engines (review of 1.0.0rc2, fixed in 1.0.0rc3).

Each engine is compared with a brute-force or independently written reference on random worlds, and the
four defects found in the review are pinned: misleading route-cap warning, chain-budget off-by-one, the
sensitivity sweep's default period, and GDP from a later period.
"""

import itertools
import math
import random

import pytest

from taxnetlab import synthetic
from taxnetlab.datasets import Dataset
from taxnetlab.engines import get_engine
from taxnetlab.topology import Bar, bottleneck, rips_persistence


def _run(engine_id, ds, **params):
    eng = get_engine(engine_id)
    p, rep = eng.resolve_parameters(params)
    assert rep.ok, rep.to_dict()
    v = eng.validate(ds, p)
    return p, v, (eng.run(ds, p) if v.ok else None)


# ---------------------------------------------------------------- tax routing against every simple route
def _routing_oracle(ds, period, overrides, mu):
    dom = {r["jurisdiction_id"]: r for r in ds.tables["tax_domestic"] if r["period"] == period}
    codes = sorted(dom)
    cit = {c: dom[c]["cit_rate"] for c in codes}
    wht = {c: dom[c]["dividend_wht_rate"] for c in codes}
    rel = {c: dom[c]["relief_method"] for c in codes}
    tr = {(r["payer_jurisdiction"], r["recipient_jurisdiction"]): r["dividend_wht_rate"]
          for r in ds.tables["tax_treaty_dividends"] if r["period"] == period}
    rp = {(r["relieving_jurisdiction"], r["taxing_jurisdiction"]): r["relief_method"]
          for r in ds.tables["tax_relief_overrides"] if r["period"] == period}
    for o in overrides:
        if o["kind"] == "relief":
            rel[o["jurisdiction"]] = o["value"]
        elif o["kind"] == "cit":
            cit[o["jurisdiction"]] = o["value"]
    tbar = {k: math.fsum(cit[j] for j in codes if j != k) / (len(codes) - 1) for k in codes}

    def d(s, p, first):
        w, m, tp = tr.get((s, p), wht[s]), rp.get((p, s), rel[p]), cit[p]
        if m == "exemption":
            x = w
        elif m == "deduction":
            x = 1 - (1 - w) * (1 - tp)
        else:
            ts = cit[s] if first else tbar[s]
            x = max(w, (tp - ts) / (1 - ts))  # t^e = max(t_S + w(1 - t_S), t_P)
        return min(max(x, 0.0), 1.0)

    out = {}
    for s, p in itertools.permutations(codes, 2):
        others = [c for c in codes if c not in (s, p)]
        best = None
        for m in range(len(others) + 1):
            for mid in itertools.permutations(others, m):
                r = [s, *mid, p]
                ret = math.prod(1 - d(r[i], r[i + 1], i == 0) for i in range(len(r) - 1))
                key = (-math.log(ret) + mu * m, m)
                if best is None or key < best[0]:
                    best = (key, 1 - (1 - cit[s]) * ret)
        out[(s, p)] = best[1]
    return out


def test_tax_routing_matches_exhaustive_search():
    rnd = random.Random(1)
    for seed in range(12):
        ds = synthetic.generate(seed=seed, n_jurisdictions=rnd.randint(3, 5))
        codes = sorted({r["jurisdiction_id"] for r in ds.tables["tax_domestic"]})
        overrides = [{"kind": "relief", "jurisdiction": c, "value": rnd.choice(["exemption", "credit", "deduction"])}
                     for c in codes if rnd.random() < 0.6]
        p, v, res = _run("vtrl2018.tax_routing", ds, overrides=overrides, max_intermediates=6,
                         centrality_weights="unweighted")
        ref = _routing_oracle(ds, p["period"], overrides, p["penalty"])
        for row in res.outputs["pairs"]:
            assert row["best_te"] == pytest.approx(ref[(row["host"], row["home"])], abs=1e-9), (seed, row)


def test_route_budget_does_not_claim_the_per_pair_limit():
    ds = synthetic.generate(seed=3, n_jurisdictions=12)
    _, _, res = _run("vtrl2018.tax_routing", ds, route_budget=1000, tolerance=0.05, max_intermediates=4)
    assert any("route budget was reached" in w for w in res.warnings)
    assert not any("max_routes_per_pair" in w for w in res.warnings)


# ---------------------------------------------------------------- conduits and sinks
def test_chain_budget_equal_to_the_number_of_paths_is_not_reported_as_reached():
    ds = synthetic.generate(seed=0, n_jurisdictions=12, n_groups=40, entities_per_group=30, cross_holdings=50)
    _, _, full = _run("gb2017.conduits_sinks", ds)
    n = next(r["value"] for r in full.outputs["summary"] if r["measure"] == "firm_paths")
    assert n >= 1000
    for budget, reached in ((n, False), (n - 1, True)):
        _, _, res = _run("gb2017.conduits_sinks", ds, chain_budget=budget)
        assert next(r["value"] for r in res.outputs["summary"] if r["measure"] == "chain_budget_reached") is reached
        assert (res.outputs["country_chains"] == full.outputs["country_chains"]) is not reached or budget == n


def _moved(ds, tables, old, new):
    texts = {t: ds.csv_text(t) for t in ds.tables}
    for t in tables:
        texts[t] = texts[t].replace(f",{old},", f",{new},")
    out, rep = Dataset.from_csv_texts("moved", texts, {})
    assert out is not None, rep.to_dict()
    return out


def test_gdp_from_a_later_period_is_never_used_and_an_earlier_one_is_flagged():
    ds = synthetic.generate(seed=5, n_jurisdictions=6)
    period = ds.tables["entity_financials"][0]["period"]
    later = _moved(ds, ["jurisdiction_attributes"], period, "2999")
    for eid in ("gb2017.conduits_sinks", "vtrl2018.tax_routing"):
        _, v, _ = _run(eid, later)
        assert not v.ok and v.errors[0].code == "gdp_missing", eid
    earlier = _moved(ds, ["jurisdiction_attributes"], period, "1999")
    for eid in ("gb2017.conduits_sinks", "vtrl2018.tax_routing"):
        _, v, res = _run(eid, earlier)
        assert v.ok and any("latest earlier value" in w for w in res.warnings), eid


# ---------------------------------------------------------------- sensitivity sweep
def test_sweep_uses_the_swept_engines_own_default_period():
    ds = synthetic.generate(seed=5, n_jurisdictions=6)
    period = ds.tables["tax_domestic"][0]["period"]
    moved = _moved(ds, ["tax_domestic", "tax_treaty_dividends", "tax_relief_overrides", "tax_treaty_conditions"],
                   period, "2099")
    p, v, res = _run("sensitivity.sweep", moved)
    assert v.ok and p["period"] == period and res.outcome == "ok"
    p, _, res = _run("sensitivity.sweep", moved, engine="vtrl2018.tax_routing", grid="penalty=0.0001|0.001",
                     measure="vtrl2018.btwns")
    assert p["period"] == "2099" and res.outcome == "ok"


# ---------------------------------------------------------------- topology
def _brute_bottleneck(A, B):
    pa = A + [None] * len(B)
    pb = B + [None] * len(A)

    def cost(x, y):
        if x is None and y is None:
            return 0.0
        if x is None:
            return (y[1] - y[0]) / 2
        if y is None:
            return (x[1] - x[0]) / 2
        return max(abs(x[0] - y[0]), abs(x[1] - y[1]))

    return min(max((cost(x, y) for x, y in zip(pa, perm)), default=0.0) for perm in itertools.permutations(pb))


def test_bottleneck_matches_brute_force():
    """Brute force over every matching, independent of any library. (gudhi agrees when called with its default
    error bound; called with e=0 it overestimates on some inputs, for example 0.7518 where the optimum is 0.6221,
    so e=0 must not be used as a reference.)"""
    rnd = random.Random(9)
    for _ in range(150):
        A = [tuple(sorted((rnd.random(), rnd.random() + 1))) for _ in range(rnd.randint(0, 4))]
        B = [tuple(sorted((rnd.random(), rnd.random() + 1))) for _ in range(rnd.randint(0, 3))]
        got = bottleneck([Bar(1, a, b, (), ()) for a, b in A], [Bar(1, a, b, (), ()) for a, b in B])
        assert got == pytest.approx(_brute_bottleneck(A, B), abs=1e-12)


def test_both_persistence_algorithms_agree_on_tied_and_duplicate_points():
    rnd = random.Random(4)
    for trial in range(120):
        n = rnd.randint(2, 11)
        pts = [[rnd.choice([0, 1, 2]) for _ in range(2)] for _ in range(n)]  # heavy ties and duplicates
        D = [[math.dist(a, b) for b in pts] for a in pts]
        a = rips_persistence(D, 1, algorithm="cohomology")
        b = rips_persistence(D, 1, algorithm="homology")
        for dim in (0, 1):
            da = sorted((x.birth, x.death if x.death is not None else math.inf) for x in a.diagram(dim))
            db = sorted((x.birth, x.death if x.death is not None else math.inf) for x in b.diagram(dim))
            assert da == db, (trial, dim)
