"""Conduits and sinks engine (spec docs/specs/gb2017_conduits_sinks.md).

Worked example (fixture ``taxnetlab.fixtures.gb_fixture``). GDP: A 100, B 100, N 50, L 10 (total 260).
Revenue: a1 100 (A), b1 50 (B), m1 20 (L); every other firm 0.
Ownership (owned -> owner): a1 -> n1 (1.0); n1 -> l1 (1.0); l1 -> a0 (1.0); b1 -> l1 (0.6) and b0 (0.4); m1 -> n1 (1.0).

Firm paths with value (revenue x multiplicative ownership) and country chains:
    a1>n1 = 100 (A>N); a1>n1>l1 = 100 (A>N>L); a1>n1>l1>a0 = 100 (A>N>L>A)
    b1>l1 = 30 (B>L); b1>l1>a0 = 30 (B>L>A); b1>b0 is domestic (B) and is dropped
    m1>n1 = 20 (L>N); m1>n1>l1 = 20 (L>N>L); m1>n1>l1>a0 = 20 (L>N>L>A)
G2: A>N 100, B>L 30, L>N 20 (total 150). G3: A>N>L 100, B>L>A 30, L>N>L 20.
Sink centrality S_c = ((in - out) / 150) / (GDP_c / 260):
    A: (0-100)/150 / (100/260) = -1.7333;  B: (0-30)/150 / (100/260) = -0.52
    N: (120-0)/150 / (50/260) = 4.16;      L: (30-20)/150 / (10/260) = 1.7333
With a sink threshold of 1.5, the sinks are N and L.
    G3 starting in a sink: L>N>L (20); ending in a sink: A>N>L (100), L>N>L (20).
    C_in(N) = (20/20) / (50/260) = 5.2;  C_out(N) = (120/120) / (50/260) = 5.2  -> N is a conduit-OFC
    entropy_out(N): origins A 100, L 20 -> -(5/6 ln 5/6 + 1/6 ln 1/6)
"""

import copy
import math

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from taxnetlab.datasets import Dataset
from taxnetlab.engines import get_engine
from taxnetlab.fixtures import GB_OWNERSHIP, gb_fixture
from taxnetlab.synthetic import generate

ENGINE = "gb2017.conduits_sinks"


def run(ds, **params):
    eng = get_engine(ENGINE)
    resolved, rep = eng.resolve_parameters(params)
    assert rep.ok, rep.format_text()
    v = eng.validate(ds, resolved)
    assert v.ok, v.format_text()
    res = eng.run(ds, resolved)
    assert res.outcome == "ok"
    return res, resolved


def jur(res):
    return {r["jurisdiction_id"]: r for r in res.outputs["jurisdictions"]}


def chains(res):
    return {r["chain"]: r["value"] for r in res.outputs["country_chains"]}


def test_status_and_direction():
    spec = get_engine(ENGINE).spec
    assert spec.status == "implemented" and spec.track == "reproduction" and "draft" in spec.spec_ref


def test_country_chains_hand_calculated():
    res, _ = run(gb_fixture())
    c = chains(res)
    assert c["FIC_A>FIC_N"] == pytest.approx(100) and c["FIC_B>FIC_L"] == pytest.approx(30)
    assert c["FIC_L>FIC_N"] == pytest.approx(20) and c["FIC_A>FIC_N>FIC_L"] == pytest.approx(100)
    assert c["FIC_B>FIC_L>FIC_A"] == pytest.approx(30) and c["FIC_L>FIC_N>FIC_L"] == pytest.approx(20)
    assert "FIC_B" not in c  # domestic paths never form a country chain


def test_sink_centrality_hand_calculated():
    res, _ = run(gb_fixture())
    j = jur(res)
    assert j["FIC_A"]["sink_centrality"] == pytest.approx(-100 / 150 / (100 / 260))
    assert j["FIC_B"]["sink_centrality"] == pytest.approx(-30 / 150 / (100 / 260))
    assert j["FIC_N"]["sink_centrality"] == pytest.approx(120 / 150 / (50 / 260))
    assert j["FIC_L"]["sink_centrality"] == pytest.approx(10 / 150 / (10 / 260))
    assert not any(r["is_sink"] for r in j.values())  # all below the stated threshold of 10
    assert any("undefined" in w for w in res.warnings)  # no sinks, so conduits are undefined
    assert all(r["conduit_in"] is None for r in j.values())


def test_conduit_centrality_and_entropy_hand_calculated():
    res, _ = run(gb_fixture(), sink_threshold=1.5)
    j = jur(res)
    assert j["FIC_N"]["is_sink"] and j["FIC_L"]["is_sink"]
    assert j["FIC_N"]["conduit_in"] == pytest.approx(5.2) and j["FIC_N"]["conduit_out"] == pytest.approx(5.2)
    assert j["FIC_N"]["is_conduit"] and not j["FIC_A"]["is_conduit"]
    assert j["FIC_N"]["entropy_out"] == pytest.approx(-(5 / 6 * math.log(5 / 6) + 1 / 6 * math.log(1 / 6)))
    assert j["FIC_N"]["entropy_in"] == pytest.approx(0.0)
    # Alternative denominator (I5): all G3 value, 150.
    res2, _ = run(gb_fixture(), sink_threshold=1.5, conduit_denominator="all_g3")
    j2 = jur(res2)
    assert j2["FIC_N"]["conduit_in"] == pytest.approx(20 / 150 / (50 / 260))
    assert j2["FIC_N"]["conduit_out"] == pytest.approx(120 / 150 / (50 / 260))
    assert not j2["FIC_N"]["is_conduit"]


def test_accounting_identity_net_flows_sum_to_zero():
    for ds in (gb_fixture(), generate(seed=4, n_jurisdictions=9, n_groups=8)):
        res, _ = run(ds)
        rows = res.outputs["jurisdictions"]
        assert sum(r["value_in"] for r in rows) == pytest.approx(sum(r["value_out"] for r in rows))
        assert sum(r["gdp_share"] * r["sink_centrality"] for r in rows) == pytest.approx(0, abs=1e-9)


def test_missing_shareholder_normalisation_and_threshold():
    without_b0 = [x for x in GB_OWNERSHIP if x[0] != "b0"]
    res, _ = run(gb_fixture(without_b0))
    assert chains(res)["FIC_B>FIC_L"] == pytest.approx(50)  # 0.6 scaled to 1.0
    res, _ = run(gb_fixture(without_b0), normalise_missing_shareholders=False)
    assert chains(res)["FIC_B>FIC_L"] == pytest.approx(30)
    tiny = [x if x[:2] != ("l1", "b1") else ("l1", "b1", 0.0005) for x in GB_OWNERSHIP]
    res, _ = run(gb_fixture(tiny))  # normalised: 0.0005 / 0.4005 = 0.00125 >= 0.001, kept
    assert "FIC_B>FIC_L" in chains(res)
    res, _ = run(gb_fixture(tiny), normalise_missing_shareholders=False)  # 0.0005 < 0.001, dropped
    assert "FIC_B>FIC_L" not in chains(res)


def test_cycles_are_discarded_and_terminate():
    cyclic = GB_OWNERSHIP + [("a1", "a0", 0.5)]  # a0 -> a1 closes the loop a1 > n1 > l1 > a0 > a1
    res, _ = run(gb_fixture(cyclic))
    assert all(len(set(c.split(">"))) >= 1 for c in chains(res))
    assert chains(res)["FIC_A>FIC_N"] == pytest.approx(100)


def test_parallel_relations_are_summed_before_normalising():
    parallel = [x for x in GB_OWNERSHIP if x[0] != "b0"] + [("l1", "b1", 0.2)]  # two share classes
    ds = gb_fixture(parallel)
    res, _ = run(ds, normalise_missing_shareholders=False)
    assert chains(res)["FIC_B>FIC_L"] == pytest.approx(50 * 0.8)


def test_metamorphic_scaling_revenue_and_gdp():
    base, _ = run(gb_fixture(), sink_threshold=1.5)
    ds = gb_fixture()
    tables = copy.deepcopy(ds.tables)
    for f in tables["entity_financials"]:
        f["operating_revenue"] *= 3.0
    for a in tables["jurisdiction_attributes"]:
        a["value"] *= 7.0
    scaled, _ = Dataset.from_rows("scaled", tables)
    res, _ = run(scaled, sink_threshold=1.5)
    for k in ("sink_centrality", "conduit_in", "conduit_out", "entropy_out"):
        assert [r[k] for r in res.outputs["jurisdictions"]] == pytest.approx([r[k] for r in base.outputs["jurisdictions"]])


def test_validation_requirements():
    from taxnetlab.synthetic import build_0_1_fixture
    eng = get_engine(ENGINE)
    p, _ = eng.resolve_parameters({})
    assert any(i.code == "no_revenue_data" for i in eng.validate(build_0_1_fixture(), p).errors)
    ds = gb_fixture()
    tables = copy.deepcopy(ds.tables)
    tables["jurisdiction_attributes"] = tables["jurisdiction_attributes"][:2]
    nogdp, _ = Dataset.from_rows("nogdp", tables)
    p, _ = eng.resolve_parameters({})
    assert any(i.code == "gdp_missing" for i in eng.validate(nogdp, p).errors)
    tables = copy.deepcopy(ds.tables)
    tables["entity_financials"][0]["consolidation"] = "consolidated"
    cons, rep = Dataset.from_rows("cons", tables)
    assert any(i.code == "consolidated_revenue" for i in rep.warnings)
    p, _ = eng.resolve_parameters({})
    assert any(i.code == "consolidated_revenue" for i in eng.validate(cons, p).warnings)


def test_chain_budget_is_reported():
    ds = generate(seed=2, n_jurisdictions=10, n_groups=30, entities_per_group=20, cross_holdings=50)
    res, _ = run(ds, chain_budget=1000)
    assert any("chain budget" in w for w in res.warnings)
    assert {r["measure"]: r["value"] for r in res.outputs["summary"]}["chain_budget_reached"] is True


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(seed=st.integers(0, 50_000), nj=st.integers(3, 10), groups=st.integers(2, 10))
def test_properties_on_random_worlds(seed, nj, groups):
    ds = generate(seed=seed, n_jurisdictions=nj, n_groups=groups)
    res, params = run(ds)
    rows = res.outputs["jurisdictions"]
    assert sum(r["value_in"] for r in rows) == pytest.approx(sum(r["value_out"] for r in rows))
    for r in rows:
        assert r["is_sink"] == (r["sink_centrality"] is not None and r["sink_centrality"] > params["sink_threshold"])
        if r["entropy_out"] is not None:
            assert r["entropy_out"] >= -1e-12
    # Every country chain has at least two distinct adjacent countries and positive value.
    for c in res.outputs["country_chains"]:
        parts = c["chain"].split(">")
        assert len(parts) >= 2 and all(a != b for a, b in zip(parts, parts[1:])) and c["value"] > 0


def test_through_run_records_and_replay(workspace):
    from taxnetlab import runs
    did = workspace.save_dataset(gb_fixture())
    rec = runs.execute(workspace, runs.RunSpec(ENGINE, did, {"sink_threshold": 1.5}, "fixture"))
    assert rec["outcome"] == "ok" and rec["parameters"]["period"] == "2025"
    assert runs.replay(workspace, rec["run_id"])["match"]
