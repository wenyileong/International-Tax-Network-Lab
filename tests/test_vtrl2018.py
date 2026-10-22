"""Optimal tax routing engine (spec docs/specs/vtrl2018_tax_routing.md).

Worked example (fixture ``taxnetlab.fixtures.vtrl_fixture``), unweighted world average CIT excluding k:
    tbar_H = (0.35+0.25+0.20)/3, tbar_P = (0.30+0.25+0.20)/3, tbar_C = (0.30+0.35+0.20)/3, tbar_X = (0.30+0.35+0.25)/3

H -> P direct (P credit; no treaty, so H's general WHT 0.15):
    d = max(0.15, (0.35-0.30)/(1-0.30)) = 0.15;  t^e = 1 - 0.70*0.85 = 0.405
H -> C -> P:
    leg 1 (C exemption, treaty 0.05): d1 = 0.05
    leg 2 (P credit, conduit uses tbar_C; C's WHT 0): d2 = (0.35 - tbar_C)/(1 - tbar_C)
    d = 1 - 0.95(1-d2);  t^e = 1 - 0.70(1-d)            -> cheapest route
X -> P direct (credit, treaty 0.05): d = max(0.05, 0.15/0.80) = 0.1875; t^e = 0.35
X -> C -> P: d1 = 0.10 (C exemption, X general WHT), d2 as above -> t^e slightly below 0.35, within 0.5pp
H -> X direct (X deduction, treaty 0): d = 1 - (1-0)(1-0.20) = 0.20; t^e = 0.44
"""

import copy
import itertools
import math

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from taxnetlab.datasets import Dataset
from taxnetlab.engines import get_engine
from taxnetlab.fixtures import vtrl_fixture
from taxnetlab.synthetic import generate

ENGINE = "vtrl2018.tax_routing"
TBAR_C = (0.30 + 0.35 + 0.20) / 3


def run(ds, **params):
    eng = get_engine(ENGINE)
    resolved, rep = eng.resolve_parameters(params)
    assert rep.ok, rep.format_text()
    v = eng.validate(ds, resolved)
    assert v.ok, v.format_text()
    res = eng.run(ds, resolved)
    assert res.outcome == "ok", res.warnings
    return res, resolved


def pairs(res):
    return {(r["host"], r["home"]): r for r in res.outputs["pairs"]}


def test_status_is_implemented_not_verified():
    spec = get_engine(ENGINE).spec
    assert spec.track == "reproduction" and spec.status == "implemented" and spec.runnable and not spec.verified
    assert "draft" in spec.spec_ref


def test_direct_route_formulas_by_relief_method():
    res, _ = run(vtrl_fixture())
    p = pairs(res)
    assert p[("FIC_H", "FIC_P")]["direct_d"] == pytest.approx(0.15)          # credit, WHT binds
    assert p[("FIC_H", "FIC_P")]["direct_te"] == pytest.approx(0.405)
    assert p[("FIC_X", "FIC_P")]["direct_d"] == pytest.approx(0.15 / 0.80)    # credit, home tax binds
    assert p[("FIC_X", "FIC_P")]["direct_te"] == pytest.approx(0.35)
    assert p[("FIC_H", "FIC_X")]["direct_d"] == pytest.approx(0.20)           # deduction
    assert p[("FIC_H", "FIC_X")]["direct_te"] == pytest.approx(0.44)
    assert p[("FIC_H", "FIC_C")]["direct_d"] == pytest.approx(0.05)           # exemption, treaty rate
    assert p[("FIC_H", "FIC_P")]["direct_wht_basis"] == "general"
    assert p[("FIC_H", "FIC_C")]["direct_wht_basis"] == "treaty"


def test_hand_calculated_indirect_route_and_conduit_world_average():
    res, _ = run(vtrl_fixture())
    p = pairs(res)
    d2 = (0.35 - TBAR_C) / (1 - TBAR_C)
    d = 1 - 0.95 * (1 - d2)
    hp = p[("FIC_H", "FIC_P")]
    assert hp["best_route"] == "FIC_H>FIC_C>FIC_P" and hp["intermediates"] == 1
    assert hp["best_d"] == pytest.approx(d) and hp["best_te"] == pytest.approx(1 - 0.70 * (1 - d))
    assert hp["shop"] == pytest.approx(0.405 - (1 - 0.70 * (1 - d)))
    legs = [lg for lg in res.outputs["legs"] if (lg["host"], lg["home"]) == ("FIC_H", "FIC_P")]
    assert [lg["payer_cit_basis"] for lg in legs] == ["statutory", "world_average_excluding_conduit"]
    assert legs[1]["payer_cit_used"] == pytest.approx(TBAR_C)
    # Recomputing the route from its legs reproduces the route distance (R1).
    assert 1 - math.prod(1 - lg["d_leg"] for lg in legs) == pytest.approx(hp["best_d"])


def test_tolerance_and_betweenness():
    res, _ = run(vtrl_fixture(), centrality_weights="unweighted")
    p = pairs(res)
    xp = p[("FIC_X", "FIC_P")]
    d = 1 - 0.90 * (1 - (0.35 - TBAR_C) / (1 - TBAR_C))
    assert xp["best_route"] == "FIC_X>FIC_C>FIC_P" and xp["best_te"] == pytest.approx(1 - 0.80 * (1 - d))
    assert xp["routes_in_range"] == 2 and xp["routes_strict"] == 1  # the direct route lies within 0.5pp
    assert p[("FIC_H", "FIC_P")]["routes_in_range"] == 1             # direct is 0.8pp dearer: outside
    cent = {r["jurisdiction_id"]: r for r in res.outputs["centrality"]}
    # C is the sole intermediate of H->P (1 of 1 routes) and of X->P (1 of 2 routes in range).
    n_pairs = len(res.outputs["pairs"])
    routes_through_c = [r for r in res.outputs["pairs"] if "FIC_C" in r["best_route"].split(">")[1:-1]]
    assert {(r["host"], r["home"]) for r in routes_through_c} >= {("FIC_H", "FIC_P"), ("FIC_X", "FIC_P")}
    assert cent["FIC_C"]["btwns"] > 0 and cent["FIC_C"]["strct"] >= cent["FIC_C"]["btwns"]
    # unweighted: each pair weighs 100 / n_pairs; strict counts give C at least 2 full pairs
    assert cent["FIC_C"]["strct"] >= 2 * 100 / n_pairs - 1e-9
    # a host is never an intermediate on its own routes
    assert all(r["host"] not in r["best_route"].split(">")[1:] for r in res.outputs["pairs"])
    # with zero tolerance the range set equals the strict set
    res0, _ = run(vtrl_fixture(), tolerance=0.0)
    assert all(r["routes_in_range"] == r["routes_strict"] for r in res0.outputs["pairs"])


def test_weights_sum_and_gdp_scaling_invariance():
    res, _ = run(vtrl_fixture())
    ds = vtrl_fixture()
    tables = copy.deepcopy(ds.tables)
    for a in tables["jurisdiction_attributes"]:
        a["value"] *= 7.5
    scaled, _ = Dataset.from_rows("scaled", tables)
    res2, _ = run(scaled)
    assert res.outputs["centrality"] == res2.outputs["centrality"]


def test_penalty_prefers_fewer_intermediates_on_equal_tax():
    # Everything exempt with zero WHT: every route is tax-free, so the penalty must pick the direct route.
    ds = vtrl_fixture()
    tables = copy.deepcopy(ds.tables)
    for r in tables["tax_domestic"]:
        r.update(relief_method="exemption", dividend_wht_rate=0.0)
    for r in tables["tax_treaty_dividends"]:
        r["dividend_wht_rate"] = 0.0
    flat, _ = Dataset.from_rows("flat", tables)
    res, _ = run(flat)
    for r in res.outputs["pairs"]:
        assert r["intermediates"] == 0 and r["best_d"] == 0 and r["shop"] == 0
        assert r["direct_te"] == pytest.approx(dict((k, v[0]) for k, v in {
            "FIC_H": (0.30,), "FIC_P": (0.35,), "FIC_C": (0.25,), "FIC_X": (0.20,)}.items())[r["host"]])


def test_scenario_overrides_change_results_and_are_validated():
    base, _ = run(vtrl_fixture())
    # Remove C's advantage: C now withholds 20% on outbound dividends.
    res, params = run(vtrl_fixture(), overrides=[{"kind": "wht", "jurisdiction": "FIC_C", "value": 0.20}])
    assert pairs(res)[("FIC_H", "FIC_P")]["best_route"] == "FIC_H>FIC_P"
    assert params["overrides"][0]["value"] == 0.20
    # One-sided relief: P exempts dividends from H only (directional override).
    res, _ = run(vtrl_fixture(), overrides=[{"kind": "relief_pair", "relieving": "FIC_P", "taxing": "FIC_H",
                                              "value": "exemption"}])
    assert pairs(res)[("FIC_H", "FIC_P")]["direct_relief"] == "exemption"
    assert pairs(res)[("FIC_X", "FIC_P")]["direct_relief"] == "credit"
    # Adding a treaty, then removing it again, restores the base results.
    res, _ = run(vtrl_fixture(), overrides=[{"kind": "treaty", "payer": "FIC_H", "recipient": "FIC_P", "value": 0.0},
                                             {"kind": "treaty", "payer": "FIC_H", "recipient": "FIC_P", "value": None}])
    assert res.outputs == base.outputs
    eng = get_engine(ENGINE)
    for bad in ([{"kind": "cit", "jurisdiction": "FIC_Q", "value": 0.1}],
                [{"kind": "cit", "jurisdiction": "FIC_H", "value": 1.5}],
                [{"kind": "relief", "jurisdiction": "FIC_H", "value": "none"}],
                [{"kind": "treaty", "payer": "FIC_H", "recipient": "FIC_H", "value": 0.1}],
                [{"kind": "magic"}],
                [{"kind": "cit", "jurisdiction": "FIC_H", "value": 0.1, "colour": "red"}]):
        resolved, rep = eng.resolve_parameters({"overrides": bad})
        assert rep.ok
        assert not eng.validate(vtrl_fixture(), resolved).ok, bad


def test_validation_without_tax_data_and_unknown_period():
    from taxnetlab.synthetic import build_0_1_fixture
    eng = get_engine(ENGINE)
    resolved, _ = eng.resolve_parameters({})
    assert not eng.validate(build_0_1_fixture(), resolved).ok
    resolved, _ = eng.resolve_parameters({"period": "1999"})
    assert any(i.code == "unknown_period" for i in eng.validate(vtrl_fixture(), resolved).errors)
    resolved, _ = eng.resolve_parameters({})
    eng.validate(vtrl_fixture(), resolved)
    assert resolved["period"] == "2025"  # resolved period is recorded


def test_gdp_required_only_for_gdp_weights():
    ds = vtrl_fixture()
    tables = copy.deepcopy(ds.tables)
    tables["jurisdiction_attributes"] = []
    nogdp, _ = Dataset.from_rows("nogdp", tables)
    eng = get_engine(ENGINE)
    resolved, _ = eng.resolve_parameters({})
    assert any(i.code == "gdp_missing" for i in eng.validate(nogdp, resolved).errors)
    run(nogdp, centrality_weights="unweighted")


# ---------------------------------------------------------------------- differential and property tests
def brute_force(eng, ds, params):
    """Enumerate every simple route (host never revisited); return all penalised keys per pair."""
    from taxnetlab.engines.vtrl2018 import _World
    w = _World(ds, params)
    best = {}
    for s, p in itertools.permutations(w.codes, 2):
        others = [c for c in w.codes if c not in (s, p)]
        keys = []
        for m in range(len(others) + 1):
            for mids in itertools.permutations(others, m):
                route = [s, *mids, p]
                k = 0.0
                for i in range(len(route) - 1):
                    lg = w.leg(route[i], route[i + 1], i == 0)
                    k += lg["cost"] + (params["penalty"] if i > 0 else 0.0)
                keys.append(k)
        best[(s, p)] = sorted(keys)
    return best, w


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(seed=st.integers(0, 50_000), nj=st.integers(2, 6))
def test_dijkstra_matches_brute_force(seed, nj):
    ds = generate(seed=seed, n_jurisdictions=nj, n_groups=1, entities_per_group=2)
    eng = get_engine(ENGINE)
    res, params = run(ds, max_intermediates=6)
    best, w = brute_force(eng, ds, params)
    for r in res.outputs["pairs"]:
        route = r["best_route"].split(">")
        k = sum(w.leg(route[i], route[i + 1], i == 0)["cost"] + (params["penalty"] if i > 0 else 0.0)
                for i in range(len(route) - 1))
        keys = best[(r["host"], r["home"])]
        assert k == pytest.approx(keys[0], abs=1e-9)
        # The near-optimal set has exactly the routes within the tolerance (spec s 6, I6).
        t_s = w.cit[r["host"]]
        bound = 1 - (1 - (1 - t_s) * math.exp(-keys[0])) - params["tolerance"]
        limit = math.inf if bound <= 0 else -math.log(bound / (1 - t_s))
        expected = sum(1 for x in keys if x <= max(limit, keys[0] + 1e-12) + 1e-12)
        assert r["routes_in_range"] == expected
        assert r["routes_strict"] == sum(1 for x in keys if x <= keys[0] + 2e-12)
        assert r["best_te"] <= r["direct_te"] + 1e-12 and r["shop"] >= -1e-12


@settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(seed=st.integers(0, 50_000), j=st.integers(0, 5), bump=st.floats(0.0, 0.3))
def test_raising_a_withholding_rate_never_lowers_any_tax(seed, j, bump):
    ds = generate(seed=seed, n_jurisdictions=6, n_groups=1, entities_per_group=2)
    base, _ = run(ds, centrality_weights="unweighted")
    code = sorted(r["jurisdiction_id"] for r in ds.tables["tax_domestic"])[j]
    current = next(r["dividend_wht_rate"] for r in ds.tables["tax_domestic"] if r["jurisdiction_id"] == code)
    res, _ = run(ds, centrality_weights="unweighted",
                 overrides=[{"kind": "wht", "jurisdiction": code, "value": min(0.9, current + bump)}])
    b, n = pairs(base), pairs(res)
    for key in b:
        assert n[key]["best_te"] >= b[key]["best_te"] - 1e-12


def test_engine_through_run_records_and_replay(workspace):
    from taxnetlab import runs
    did = workspace.save_dataset(vtrl_fixture())
    rec = runs.execute(workspace, runs.RunSpec(ENGINE, did, {"overrides": [
        {"kind": "cit", "jurisdiction": "FIC_P", "value": 0.4}]}, "fixture run"))
    assert rec["outcome"] == "ok" and rec["parameters"]["period"] == "2025"
    assert rec["parameters"]["overrides"][0]["value"] == 0.4
    assert set(rec["outputs"]) == {"pairs", "legs", "centrality", "summary"}
    assert runs.replay(workspace, rec["run_id"])["match"]


def test_synthetic_worlds_are_routable_and_fast():
    import time
    ds = generate(seed=11, n_jurisdictions=12)
    t = time.time()
    res, _ = run(ds)
    assert time.time() - t < 5
    summary = {r["measure"]: r["value"] for r in res.outputs["summary"]}
    assert summary["avg_best_te"] <= summary["avg_direct_te"]
    assert sum(r["btwns"] for r in res.outputs["centrality"]) > 0


def test_route_budget_bounds_work_and_is_reported():
    ds = generate(seed=3, n_jurisdictions=10)
    codes = [r["jurisdiction_id"] for r in ds.tables["tax_domestic"]]
    flat = [{"kind": "wht", "jurisdiction": c, "value": 0.0} for c in codes] + \
           [{"kind": "relief", "jurisdiction": c, "value": "exemption"} for c in codes]
    res, _ = run(ds, overrides=flat, route_budget=1000)
    capped = [r for r in res.outputs["pairs"] if r["enumeration_capped"]]
    assert capped and any("route budget" in w for w in res.warnings)
    # The cheapest routes themselves never depend on the budget.
    full, _ = run(ds, overrides=flat, route_budget=20_000_000)
    assert [(r["host"], r["home"], r["best_te"]) for r in res.outputs["pairs"]] == \
           [(r["host"], r["home"], r["best_te"]) for r in full.outputs["pairs"]]


def test_datasets_saved_before_tax_tables_keep_their_ids(tmp_path):
    from taxnetlab.synthetic import build_0_1_fixture
    ds = build_0_1_fixture()
    assert ds.dataset_id == "30873d73b11e520c"  # the id it had in release 0.2
    path = ds.save(tmp_path)
    for t in ("tax_domestic", "tax_treaty_dividends", "tax_relief_overrides"):
        (path / f"{t}.csv").unlink()  # a 0.2 workspace has no such files
    assert Dataset.load(path).dataset_id == "30873d73b11e520c"
