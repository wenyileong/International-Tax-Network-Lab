"""Sensitivity sweeps (docs/specs/sensitivity.md)."""

import pytest

from taxnetlab.engines import get_engine
from taxnetlab.engines.sensitivity import parse_grid
from taxnetlab.synthetic import generate

ENGINE = "sensitivity.sweep"


@pytest.fixture(scope="module")
def world():
    return generate(seed=7, n_jurisdictions=12, n_groups=8)


def run(ds, **params):
    e = get_engine(ENGINE)
    p, rep = e.resolve_parameters(params)
    rep.extend(e.validate(ds, p))
    return e, p, rep


def test_grid_parsing():
    assert parse_grid("a=1|2; b=x") == {"a": ["1", "2"], "b": ["x"]}
    with pytest.raises(ValueError):
        parse_grid("a")


def test_draws_and_shares(world):
    e, p, rep = run(world, grid="sink_threshold=2|5|10; conduit_denominator=subset_total|all_g3")
    assert rep.ok, rep.format_text()
    res = e.run(world, p)
    assert res.outcome == "ok" and len(res.outputs["draws"]) == 6
    ranks = {}
    for v in res.outputs["values"]:
        ranks.setdefault(v["jurisdiction_id"], []).append(v["rank"])
    for row in res.outputs["robustness"]:
        rs = [r for r in ranks[row["jurisdiction_id"]] if r is not None]
        assert row["share_top_k"] == pytest.approx(sum(r <= 5 for r in rs) / 6)
        assert row["robust_top_k"] == (row["share_top_k"] >= 0.9)
        assert 0 <= row["share_sink"] <= 1


def test_single_value_grid_matches_base_run(world):
    e, p, rep = run(world, grid="sink_threshold=10")
    res = e.run(world, p)
    gb = get_engine("gb2017.conduits_sinks")
    q, _ = gb.resolve_parameters({"sink_threshold": 10})
    gb.validate(world, q)
    sinks = {r["jurisdiction_id"] for r in gb.run(world, q).outputs["jurisdictions"] if r["is_sink"]}
    assert {r["jurisdiction_id"] for r in res.outputs["robustness"] if r["share_sink"] == 1.0} == sinks


def test_excluded_draws_are_counted():
    ds = generate(seed=3, n_jurisdictions=6)
    e, p, rep = run(ds, engine="ph.vietoris_rips", grid="features=cit|gb_conduit_out", measure="ph.influence_h1")
    assert rep.ok, rep.format_text()
    res = e.run(ds, p)
    summary = {r["measure"]: r["value"] for r in res.outputs["summary"]}
    assert summary["draws"] == 2 and summary["draws_excluded"] in (0, 1)
    assert all(d["outcome"] in ("ok", "excluded") for d in res.outputs["draws"])


@pytest.mark.parametrize("grid,measure", [("period=2025", "gb2017.sink_centrality"), ("nonsense=1", "gb2017.sink_centrality"),
                                          ("sink_threshold=-5", "gb2017.sink_centrality"),
                                          ("sink_threshold=1", "vtrl2018.btwns")])
def test_invalid_grids_refused(world, grid, measure):
    _, _, rep = run(world, grid=grid, measure=measure)
    assert not rep.ok
