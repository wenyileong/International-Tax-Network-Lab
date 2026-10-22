"""Engine interface, status ladder and the demonstration engine (plan v2.1, s 3, 4.2 and 6)."""

import copy

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from taxnetlab.datasets import Dataset
from taxnetlab.engines import get_engine, list_engines
from taxnetlab.engines.base import OUTCOMES, STATUSES, EngineResult, EngineSpec, SpecificationNotValidatedError
from taxnetlab.synthetic import generate

DEMO = "demo.link_summary"


def run_demo(ds, **params):
    engine = get_engine(DEMO)
    resolved, rep = engine.resolve_parameters(params)
    assert rep.ok, rep.format_text()
    return engine.run(ds, resolved)


def by_jur(result):
    return {r["jurisdiction_id"]: r for r in result.outputs["jurisdiction_summary"]}


def test_registry_statuses_are_on_their_ladders():
    specs = {s.engine_id: s for s in list_engines()}
    for s in specs.values():
        assert s.status in STATUSES[s.track]
    for eid in ("gb2017.conduits_sinks", "us10417262.tda"):
        assert specs[eid].status == "interface" and specs[eid].track == "reproduction" and not specs[eid].runnable
    assert specs["vtrl2018.tax_routing"].status == "implemented"
    assert specs[DEMO].track == "demonstration"


@pytest.mark.parametrize("eid", ["gb2017.conduits_sinks", "us10417262.tda"])
def test_interface_engines_fail_explicitly(eid, fixture01):
    with pytest.raises(SpecificationNotValidatedError):
        get_engine(eid).run(fixture01, {})


def test_spec_rejects_status_off_ladder():
    with pytest.raises(ValueError):
        EngineSpec("x", "x", "reproduction", "v", "0", "robust", "", "", "", "", ())
    with pytest.raises(ValueError):
        EngineResult("probably_fine")
    assert "not_converged" in OUTCOMES


def test_parameters_validated():
    engine = get_engine(DEMO)
    _, rep = engine.resolve_parameters({"nonsense": 1})
    assert not rep.ok
    _, rep = engine.resolve_parameters({"relation_type": "friendship"})
    assert not rep.ok
    _, rep = engine.resolve_parameters({"as_of": "2025-02-30"})
    assert not rep.ok
    resolved, rep = engine.resolve_parameters({})
    assert rep.ok and resolved == {"as_of": None, "relation_type": "equity"}


def test_hand_calculated_fixture(fixture01):
    # Build 0.1 network: A->B (120), B->C (85), C->D (55), A->D (40, via CO_007 in D), D->E (32), A->A domestic (65).
    res = run_demo(fixture01)
    j = by_jur(res)
    assert (j["FIC_A"]["outbound_links"], j["FIC_A"]["inbound_links"], j["FIC_A"]["domestic_links"]) == (2, 0, 1)
    assert j["FIC_A"]["outbound_value"] == pytest.approx(160.0)
    assert j["FIC_D"]["inbound_value"] == pytest.approx(95.0) and j["FIC_D"]["outbound_value"] == pytest.approx(32.0)
    assert j["FIC_E"]["net_outbound_value"] == pytest.approx(-32.0)
    assert res.outcome == "ok" and res.trace[-1]["result"] == "holds"


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(seed=st.integers(0, 10_000), nj=st.integers(2, 9), groups=st.integers(1, 6), per=st.integers(2, 8))
def test_identity_outbound_equals_inbound(seed, nj, groups, per):
    rows = run_demo(generate(seed=seed, n_jurisdictions=nj, n_groups=groups, entities_per_group=per)).outputs[
        "jurisdiction_summary"]
    assert sum(r["outbound_links"] for r in rows) == sum(r["inbound_links"] for r in rows)
    assert sum(r["outbound_value"] for r in rows) == pytest.approx(sum(r["inbound_value"] for r in rows))
    total = sum(r["outbound_links"] + r["domestic_links"] for r in rows)
    assert total == len([o for o in generate(seed=seed, n_jurisdictions=nj, n_groups=groups,
                                             entities_per_group=per).tables["ownership"]])


def test_metamorphic_scaling_values(world):
    base = by_jur(run_demo(world))
    tables = copy.deepcopy(world.tables)
    for o in tables["ownership"]:
        o["value_amount"] *= 3
    scaled, _ = Dataset.from_rows("scaled", tables)
    new = by_jur(run_demo(scaled))
    for jid, row in base.items():
        assert new[jid]["outbound_links"] == row["outbound_links"]
        assert new[jid]["outbound_value"] == pytest.approx(3 * row["outbound_value"])


def test_relabelling_identifiers_does_not_change_results(fixture01):
    tables = copy.deepcopy(fixture01.tables)
    rename = {e["entity_id"]: "X" + e["entity_id"][::-1] for e in tables["entities"]}
    for e in tables["entities"]:
        e["entity_id"] = rename[e["entity_id"]]
    for o in tables["ownership"]:
        o["holder_id"], o["held_id"] = rename[o["holder_id"]], rename[o["held_id"]]
        o["relation_id"] = "Z" + o["relation_id"]
    relabelled, _ = Dataset.from_rows("relabelled", tables)
    assert by_jur(run_demo(relabelled)) == by_jur(run_demo(fixture01))


def test_mixed_currency_blocks_demo(fixture01):
    tables = copy.deepcopy(fixture01.tables)
    tables["ownership"][0]["value_currency"] = "XXX"
    ds, _ = Dataset.from_rows("mixed", tables)
    assert not get_engine(DEMO).validate(ds, {}).ok
