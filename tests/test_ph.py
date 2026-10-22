"""Persistent homology (spec docs/specs/ph_vietoris_rips.md).

Hand fixtures (s 8, item 1):
* unit square: edges 1 (four sides) and sqrt 2 (diagonals). Three H0 bars [0, 1), one essential; one loop
  born when the fourth side closes the square (1) and killed when a diagonal fills it (sqrt 2).
* equilateral triangle: the triangle enters with its last edge, so no loop survives.
* regular hexagon with side 1: sides 1, short diagonals sqrt 3, long diagonals 2. One loop [1, sqrt 3):
  at sqrt 3 every triangle of three alternate vertices fills the hexagon.
"""

import itertools
import math
import random

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from taxnetlab import topology
from taxnetlab.api import Api
from taxnetlab.engines import get_engine
from taxnetlab.synthetic import generate
from taxnetlab.topology import Bar, betti_at, betti_curve, bottleneck, classical_mds, rips_persistence

ENGINE = "ph.vietoris_rips"


def dmat(points):
    return [[math.dist(a, b) for b in points] for a in points]


def finite(p, dim):
    return sorted((round(b.birth, 9), round(b.death, 9)) for b in p.diagram(dim) if b.death is not None)


# ------------------------------------------------------------------ hand fixtures
def test_square_has_one_loop():
    p = rips_persistence(dmat([(0, 0), (1, 0), (1, 1), (0, 1)]))
    assert finite(p, 0) == [(0, 1.0)] * 3
    assert len([b for b in p.diagram(0) if b.death is None]) == 1
    assert finite(p, 1) == [(1.0, round(math.sqrt(2), 9))]
    loop = p.diagram(1)[0]
    assert len(loop.cycle) == 5 and loop.cycle[0] == loop.cycle[-1] and set(loop.cycle) == {0, 1, 2, 3}


def test_equilateral_triangle_has_no_loop():
    p = rips_persistence(dmat([(0, 0), (1, 0), (0.5, math.sqrt(3) / 2)]))
    assert finite(p, 1) == []
    assert p.zero_pairs[1] == 1


def test_hexagon_loop():
    hexagon = [(math.cos(k * math.pi / 3), math.sin(k * math.pi / 3)) for k in range(6)]
    p = rips_persistence(dmat(hexagon))
    assert finite(p, 1) == [(1.0, round(math.sqrt(3), 9))]


def test_two_pairs_merge_at_gap():
    p = rips_persistence(dmat([(0, 0), (0.1, 0), (5, 0), (5.1, 0)]))
    assert sorted(b.death for b in p.diagram(0) if b.death is not None)[-1] == pytest.approx(4.9)
    merge = max((b for b in p.diagram(0) if b.death is not None), key=lambda b: b.death)
    assert set(merge.members) == {2, 3}  # the component with the larger smallest index dies


def test_duplicates_counted_not_listed():
    p = rips_persistence(dmat([(0, 0), (0, 0), (1, 0)]))
    assert p.zero_pairs[0] == 1 and len(p.diagram(0)) == 2


def test_truncation_and_budget():
    pts = [(math.cos(k * math.pi / 3), math.sin(k * math.pi / 3)) for k in range(6)]
    p = rips_persistence(dmat(pts), max_scale=1.5)
    assert [b.death for b in p.diagram(1)] == [None]  # alive at the truncation scale: essential
    q = rips_persistence(dmat(pts), simplex_budget=1)
    assert q.budget_reached and q.max_scale is not None
    assert all(b.death is None or b.death <= q.max_scale for b in q.bars)


def test_rejects_bad_matrices():
    for bad in ([[0, 1], [2, 0]], [[1, 0], [0, 0]], [[0, -1], [-1, 0]], [[0, float("nan")], [float("nan"), 0]]):
        with pytest.raises(ValueError):
            rips_persistence(bad)


# ------------------------------------------------------------------ independent check: ranks over Z/2
def _rank_z2(rows):
    rows = [r for r in rows if r]
    rank, pivots = 0, {}
    for r in rows:
        r = set(r)
        while r:
            p = max(r)
            if p not in pivots:
                pivots[p] = r
                rank += 1
                break
            r ^= pivots[p]
    return rank


def _betti_by_rank(D, e):
    n = len(D)
    edges = [(i, j) for i in range(n) for j in range(i + 1, n) if D[i][j] <= e]
    eidx = {ed: k for k, ed in enumerate(edges)}
    tris = [(i, j, k) for i, j, k in itertools.combinations(range(n), 3)
            if {(i, j), (i, k), (j, k)} <= set(eidx)]
    r1 = _rank_z2([{i, j} for i, j in edges])
    r2 = _rank_z2([{eidx[(i, j)], eidx[(i, k)], eidx[(j, k)]} for i, j, k in tris])
    return n - r1, len(edges) - r1 - r2


@pytest.mark.parametrize("seed", range(12))
def test_betti_numbers_match_ranks(seed):
    rnd = random.Random(seed)
    n = rnd.randint(3, 11)
    pts = [(rnd.random(), rnd.random()) for _ in range(n)]
    D = [[round(math.dist(a, b), 1 if seed % 3 == 0 else 6) for b in pts] for a in pts]  # ties for some seeds
    p = rips_persistence(D)
    for e, b0, b1 in betti_curve(p):
        assert (b0, b1) == _betti_by_rank(D, e)
        assert betti_at(p, e) == (b0, b1)


@pytest.mark.parametrize("seed", range(10))
def test_cohomology_equals_homology(seed):
    rnd = random.Random(100 + seed)
    pts = [(rnd.random(), rnd.random(), rnd.random()) for _ in range(rnd.randint(4, 30))]
    D = [[round(math.dist(a, b), 2) for b in pts] for a in pts]
    a = rips_persistence(D)
    b = rips_persistence(D, algorithm="homology")
    key = lambda p: sorted((x.dimension, x.birth, -1 if x.death is None else x.death) for x in p.bars)  # noqa: E731
    assert key(a) == key(b) and a.triangles == b.triangles


# ------------------------------------------------------------------ bottleneck and stability
def _brute_bottleneck(A, B):
    A = [(b.birth, b.death) for b in A]
    B = [(b.birth, b.death) for b in B]
    left = A + [None] * len(B)
    right = B + [None] * len(A)
    best = math.inf
    for perm in itertools.permutations(range(len(right))):
        cost = 0.0
        for i, j in enumerate(perm):
            a, b = left[i], right[j]
            if a is not None and b is not None:
                c = max(abs(a[0] - b[0]), abs(a[1] - b[1]))
            elif a is not None:
                c = (a[1] - a[0]) / 2
            elif b is not None:
                c = (b[1] - b[0]) / 2
            else:
                c = 0.0
            cost = max(cost, c)
        best = min(best, cost)
    return best


@pytest.mark.parametrize("seed", range(25))
def test_bottleneck_matches_brute_force(seed):
    rnd = random.Random(seed)

    def dgm(k):
        out = []
        for _ in range(k):
            b = rnd.random()
            out.append(Bar(1, b, b + rnd.random(), (0,), None))
        return out

    A, B = dgm(rnd.randint(0, 3)), dgm(rnd.randint(0, 3))
    assert bottleneck(A, B) == pytest.approx(_brute_bottleneck(A, B), abs=1e-12)


def test_bottleneck_essential_classes():
    a = [Bar(0, 0.0, None, (0,), None)]
    assert bottleneck(a, a) == 0.0
    assert bottleneck(a, a + a) is None


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.integers(0, 10_000), st.floats(0.0, 0.05))
def test_stability_under_perturbation(seed, delta):
    rnd = random.Random(seed)
    n = rnd.randint(3, 12)
    pts = [(rnd.random(), rnd.random()) for _ in range(n)]
    D = dmat(pts)
    E = [row[:] for row in D]
    for i in range(n):
        for j in range(i + 1, n):
            E[i][j] = E[j][i] = max(0.0, D[i][j] + rnd.uniform(-delta, delta))
    actual = max(abs(D[i][j] - E[i][j]) for i in range(n) for j in range(n))
    p, q = rips_persistence(D), rips_persistence(E)
    for dim in (0, 1):
        assert bottleneck(p.diagram(dim), q.diagram(dim)) <= actual + 1e-12


# ------------------------------------------------------------------ differential (optional dependencies)
@pytest.mark.parametrize("seed", range(8))
def test_against_ripser(seed):
    ripser = pytest.importorskip("ripser")
    np = pytest.importorskip("numpy")
    rnd = random.Random(seed)
    pts = [(rnd.random(), rnd.random(), rnd.random()) for _ in range(rnd.randint(5, 40))]
    D = dmat(pts)
    theirs = ripser.ripser(np.array(D), distance_matrix=True, maxdim=1)["dgms"]
    p = rips_persistence(D)
    for dim in (0, 1):
        ours = sorted((b.birth, math.inf if b.death is None else b.death) for b in p.diagram(dim))
        ref = sorted((float(x), float(y)) for x, y in theirs[dim] if y > x)
        assert len(ours) == len(ref)
        for (a, b), (c, d) in zip(ours, ref):
            assert a == pytest.approx(c, abs=1e-6) and (b == d or b == pytest.approx(d, abs=1e-6))


def test_bottleneck_against_gudhi():
    gudhi = pytest.importorskip("gudhi")
    rnd = random.Random(7)
    for _ in range(50):
        A = [Bar(1, b, b + rnd.random(), (0,), None) for b in (rnd.random() for _ in range(rnd.randint(0, 9)))]
        B = [Bar(1, b, b + rnd.random(), (0,), None) for b in (rnd.random() for _ in range(rnd.randint(0, 9)))]
        ref = gudhi.bottleneck_distance([(x.birth, x.death) for x in A], [(x.birth, x.death) for x in B])
        assert bottleneck(A, B) == pytest.approx(ref, abs=1e-9)


# ------------------------------------------------------------------ projection
def test_mds_recovers_planar_distances():
    pts = [(0, 0), (3, 0), (0, 4), (3, 4), (1, 2)]
    coords, share, converged = classical_mds(dmat(pts))
    assert converged and share == pytest.approx(1.0)
    D2 = dmat(coords)
    for i in range(5):
        for j in range(5):
            assert D2[i][j] == pytest.approx(math.dist(pts[i], pts[j]), abs=1e-6)


# ------------------------------------------------------------------ engine
def run(ds, **params):
    eng = get_engine(ENGINE)
    resolved, rep = eng.resolve_parameters(params)
    assert rep.ok, rep.format_text()
    v = eng.validate(ds, resolved)
    assert v.ok, v.format_text()
    return eng.run(ds, resolved), resolved


@pytest.fixture(scope="module")
def big():
    return generate(seed=7, n_jurisdictions=20, n_groups=12)


def test_engine_features(big):
    res, params = run(big)
    assert res.outcome == "ok"
    summary = {r["measure"]: r["value"] for r in res.outputs["summary"]}
    assert summary["observations"] == 20 and summary["excluded"] == "none"
    h0 = [r for r in res.outputs["diagram"] if r["dimension"] == 0]
    assert len(h0) == 20 and sum(r["essential"] for r in h0) == 1
    h1 = [r for r in res.outputs["diagram"] if r["dimension"] == 1]
    assert h1 and h1[0]["feature_id"] == "H1-0001"
    assert h1[0]["persistence"] == max(r["persistence"] for r in h1)
    cyc = h1[0]["representative_cycle"].split(">")
    assert cyc[0] == cyc[-1] and len(cyc) >= 4
    assert len(res.outputs["distances"]) == 190
    assert len(res.outputs["influence"]) == 20
    assert sorted(r["rank_h1"] for r in res.outputs["influence"]) == list(range(1, 21))
    assert params["features"].startswith("cit,")


def test_engine_routing_cost(big):
    res, _ = run(big, input="routing_cost")
    assert res.outcome == "ok"
    assert any("vtrl2018.tax_routing" in w for w in res.warnings)
    assert res.outputs["features"] == []


def test_engine_derived_features_record_provenance(big):
    res, _ = run(big, features="cit,vtrl_btwns,gb_sink_centrality")
    assert res.outcome == "ok"
    assert sum("not verified" in w for w in res.warnings) == 2


def test_engine_excludes_missing_without_imputation(big):
    import copy

    from taxnetlab.datasets import Dataset

    tables = copy.deepcopy(big.tables)
    tables["jurisdiction_attributes"] = [a for a in tables["jurisdiction_attributes"]
                                         if not (a["jurisdiction_id"] == "FIC_C" and a["attribute"] == "gdp")]
    ds, _ = Dataset.from_rows("missing gdp", tables)
    res, _ = run(ds)
    points = {r["jurisdiction_id"]: r for r in res.outputs["points"]}
    assert points["FIC_C"]["included"] is False and points["FIC_C"]["missing_features"] == "log_gdp"
    assert any("FIC_C (log_gdp)" in w for w in res.warnings)
    assert not any(r["a"] == "FIC_C" or r["b"] == "FIC_C" for r in res.outputs["distances"])


def test_engine_rejects_unknown_feature(big):
    eng = get_engine(ENGINE)
    resolved, _ = eng.resolve_parameters({"features": "cit,nonsense"})
    assert "unknown_feature" in {i.code for i in eng.validate(big, resolved).errors}


def test_engine_too_few_observations():
    res, _ = run(generate(seed=1, n_jurisdictions=2))
    assert res.outcome == "invalid_input"


def test_projection_is_display_only(big, monkeypatch):
    """D4: every output except the projection coordinates is unchanged when the projection changes."""
    res, _ = run(big)
    monkeypatch.setattr("taxnetlab.engines.ph.classical_mds",
                        lambda D: ([[float(i), -float(i)] for i in range(len(D))], 0.5, True))
    alt, _ = run(big)
    for name in res.outputs:
        if name == "points":
            strip = lambda rows: [{k: v for k, v in r.items() if k not in ("x", "y")} for r in rows]  # noqa: E731
            assert strip(res.outputs[name]) == strip(alt.outputs[name])
        elif name == "summary":
            a = [r for r in res.outputs[name] if r["measure"] != "projection_stress"]
            b = [r for r in alt.outputs[name] if r["measure"] != "projection_stress"]
            assert a == b
        else:
            assert res.outputs[name] == alt.outputs[name], name


def test_design_constraints_no_cover_or_lens_parameters():
    names = {p.name for p in get_engine(ENGINE).spec.parameters}
    assert not names & {"lens", "filter", "cover", "resolution", "overlap", "intervals", "clusterer"}
    assert get_engine("us10417262.tda").spec.status == "interface"  # the patent method stays behind the gate


def test_preview_pin_and_replay(workspace):
    api = Api(workspace)
    did = api.generate_synthetic({"seed": 7, "n_jurisdictions": 12})["dataset_id"]
    prev = api.preview(ENGINE, did, {"metric": "manhattan"})
    assert prev["executed"] and prev["exploratory"] and prev["outcome"] == "ok"
    pinned = api.run({"engine_id": ENGINE, "dataset_id": did, "parameters": {"metric": "manhattan"}})
    assert pinned["executed"] and api.replay(pinned["record"]["run_id"])["match"]
    stored = pinned["outputs"]["diagram"]["rows"]
    assert [r["feature_id"] for r in stored] == sorted(r["feature_id"] for r in prev["outputs"]["diagram"])


def test_topology_module_has_no_cover_code():
    src = open(topology.__file__, encoding="utf-8").read().lower()
    for word in ("def cover", "def lens", "nerve(", "overlap"):
        assert word not in src
