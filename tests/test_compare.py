"""Model comparison (docs/specs/compare_models.md): agreement rule, robustness shares, rank correlations."""

import random

import pytest

from taxnetlab.api import Api
from taxnetlab.engines import get_engine
from taxnetlab.engines.compare import READINGS, _competition_ranks, kendall_tau_b, spearman
from taxnetlab.fixtures import gb_fixture
from taxnetlab.synthetic import generate

ENGINE = "compare.models"


def run(ds, **params):
    eng = get_engine(ENGINE)
    resolved, rep = eng.resolve_parameters(params)
    rep.extend(eng.validate(ds, resolved))
    assert rep.ok, rep.format_text()
    return eng.run(ds, resolved)


def test_competition_ranks():
    assert _competition_ranks({"a": 3.0, "b": 5.0, "c": 3.0, "d": 1.0}) == {"b": 1, "a": 2, "c": 2, "d": 4}
    assert _competition_ranks({"a": 0.1 + 0.2, "b": 0.3}) == {"a": 1, "b": 1}  # noise does not split a tie


def test_correlations_by_hand():
    # x = 1..5, y reversed: rho = tau = -1; with one swap: rho = 0.9, tau = 0.8
    assert spearman([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]) == pytest.approx(-1)
    assert kendall_tau_b([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]) == pytest.approx(-1)
    assert spearman([1, 2, 3, 4, 5], [2, 1, 3, 4, 5]) == pytest.approx(0.9)
    assert kendall_tau_b([1, 2, 3, 4, 5], [2, 1, 3, 4, 5]) == pytest.approx(0.8)
    assert spearman([1, 1, 1], [1, 2, 3]) is None and kendall_tau_b([1, 2], [1, 2]) is None


@pytest.mark.parametrize("seed", range(6))
def test_correlations_against_scipy(seed):
    stats = pytest.importorskip("scipy.stats")
    rnd = random.Random(seed)
    xs = [rnd.choice([0, 1, 2, 3, 4]) for _ in range(15)]
    ys = [x + rnd.choice([-1, 0, 1, 2]) for x in xs]
    assert spearman(xs, ys) == pytest.approx(stats.spearmanr(xs, ys)[0])
    assert kendall_tau_b(xs, ys) == pytest.approx(stats.kendalltau(xs, ys)[0])


@pytest.fixture(scope="module")
def world():
    return generate(seed=7, n_jurisdictions=20, n_groups=12)


def test_agreement_rule_consistent_with_readings(world):
    res = run(world)
    assert res.outcome == "ok"
    ranks = {}
    for r in res.outputs["readings"]:
        ranks.setdefault((r["jurisdiction_id"], r["measure"]), []).append(r["rank"])
    for a in res.outputs["agreement"]:
        rs = ranks[(a["jurisdiction_id"], a["measure"])]
        assert len(rs) == a["readings"] == len(READINGS[{"vtrl2018": "vtrl2018.tax_routing", "gb2017": "gb2017.conduits_sinks",
                                                         "ph": "ph.vietoris_rips"}[a["measure"].split(".")[0]]])
        all_equal = None not in rs and len(set(rs)) == 1
        assert a["agreed"] == all_equal
        assert a["rank"] == (rs[0] if all_equal else None)


def test_readings_that_do_not_touch_a_measure_agree(world):
    """I5 changes only the conduit denominators, I1 the ownership weights: sink centrality is unaffected by I5, so
    within each I1 setting the two I5 readings must give identical sink ranks."""
    res = run(world)
    rows = [r for r in res.outputs["readings"] if r["measure"] == "gb2017.sink_centrality"]
    by = {}
    for r in rows:
        by.setdefault(r["reading"].split(";")[0], {}).setdefault(r["reading"], {})[r["jurisdiction_id"]] = r["rank"]
    for i1, readings in by.items():
        a, b = readings.values()
        assert a == b, i1


def test_robustness_shares(world):
    res = run(world)
    for r in res.outputs["classification"]:
        assert r["share"] == pytest.approx(r["classified_in"] / r["readings"])
        assert r["robust"] == (r["classified_in"] == r["readings"])


def test_unranked_engine_is_reported_not_zero():
    res = run(gb_fixture(), include_topology=False)
    assert res.outcome == "ok"
    eng = {r["engine_id"]: r["outcome"] for r in res.outputs["engines"]}
    assert eng["vtrl2018.tax_routing"] == "unranked" and eng["gb2017.conduits_sinks"] == "ok"
    assert not any(r["measure"].startswith("vtrl2018") for r in res.outputs["agreement"])
    assert any("unranked" in w for w in res.warnings)


def test_no_combined_score(world):
    cols = set(get_engine(ENGINE).spec.outputs["agreement"]) | set(get_engine(ENGINE).spec.outputs["readings"])
    assert not cols & {"score", "combined", "index", "composite"}


def test_preview_and_replay(workspace):
    api = Api(workspace)
    did = api.generate_synthetic({"seed": 3, "n_jurisdictions": 8})["dataset_id"]
    run_ = api.run({"engine_id": ENGINE, "dataset_id": did, "parameters": {}})
    from taxnetlab.engines import upstream

    upstream._CACHE.clear()  # replay must recompute the upstream engines, not reuse them
    assert run_["executed"] and api.replay(run_["record"]["run_id"])["match"]
