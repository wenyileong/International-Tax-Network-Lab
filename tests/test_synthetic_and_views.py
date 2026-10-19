"""Synthetic generator and graph views (plan v2.1, s 5.2; Appendix B, B3, B5, B8 to B10)."""

import pytest
from conftest import rebuild

from taxnetlab.synthetic import build_0_1_fixture, generate
from taxnetlab.views import jurisdiction_matrix, jurisdiction_view, ownership_view, value_flow_view, view_to_json


def test_b3_seed_changes_data_and_is_deterministic():
    assert generate(seed=1).dataset_id == generate(seed=1).dataset_id
    assert generate(seed=1).dataset_id != generate(seed=2).dataset_id


def test_generator_output_is_fictional_and_labelled():
    ds = generate(seed=5, n_jurisdictions=8, n_groups=6)
    assert ds.data_status == "synthetic"
    assert all(j["fictional"] and j["jurisdiction_id"].startswith("FIC_") for j in ds.tables["jurisdictions"])
    assert {o["value_currency"] for o in ds.tables["ownership"]} == {"XTS"}
    assert ds.metadata["generator"]["seed"] == 5


def test_generator_rejects_out_of_range_parameters():
    with pytest.raises(ValueError):
        generate(n_jurisdictions=1)


def test_b9_fixture_uses_fractions():
    ds = build_0_1_fixture()
    assert {round(o["fraction"], 2) for o in ds.tables["ownership"]} == {0.8, 0.7, 0.6, 0.25, 0.51, 1.0}
    assert all(0 <= o["fraction"] <= 1 for o in ds.tables["ownership"])


def test_b10_direction_conventions(fixture01):
    own, flow = ownership_view(fixture01).graph, value_flow_view(fixture01).graph
    assert own.has_edge("CO_001", "CO_002") and not own.has_edge("CO_002", "CO_001")
    assert flow.has_edge("CO_002", "CO_001") and not flow.has_edge("CO_001", "CO_002")
    assert own.number_of_edges() == flow.number_of_edges() == 6
    assert ownership_view(fixture01).meta["direction"] == "holder -> held"
    assert value_flow_view(fixture01).meta["direction"] == "held -> holder"


def test_b5_parallel_relations_are_separate_edges(fixture01):
    ds, _ = rebuild(fixture01, lambda t: t["ownership"].append(
        dict(t["ownership"][0], relation_id="R77777", share_class="B", fraction=0.05)))
    g = ownership_view(ds).graph
    assert g.number_of_edges("CO_001", "CO_002") == 2


def test_as_of_filters_by_validity_period(fixture01):
    ds, _ = rebuild(fixture01, lambda t: t["ownership"][0].update(valid_to="2026-06-30"))
    assert ownership_view(ds).graph.number_of_edges() == 5  # current: valid_to set means ended
    assert ownership_view(ds, as_of="2026-01-01").graph.number_of_edges() == 6
    assert ownership_view(ds, as_of="2024-01-01").graph.number_of_edges() == 0


def test_jurisdiction_aggregation_rules(fixture01):
    count = jurisdiction_view(fixture01, "count").graph
    assert count["FIC_A"]["FIC_B"]["weight"] == 1.0
    assert not count.has_edge("FIC_A", "FIC_A")  # CO_001 -> CO_006 is domestic and excluded by default
    with_dom = jurisdiction_view(fixture01, "count", include_domestic=True).graph
    assert with_dom["FIC_A"]["FIC_A"]["weight"] == 1.0
    assert jurisdiction_view(fixture01, "fraction_sum").graph["FIC_A"]["FIC_D"]["weight"] == pytest.approx(0.25)
    assert jurisdiction_view(fixture01, "value_sum").graph["FIC_A"]["FIC_B"]["weight"] == pytest.approx(120.0)


def test_value_sum_refuses_mixed_currencies(fixture01):
    ds, _ = rebuild(fixture01, lambda t: t["ownership"][0].update(value_currency="XXX"))
    with pytest.raises(ValueError, match="currencies"):
        jurisdiction_view(ds, "value_sum")


def test_matrix_total_equals_relations(world):
    m = jurisdiction_matrix(world, "count", include_domestic=True)
    assert sum(map(sum, m["values"])) == len(world.tables["ownership"])


def test_view_json_has_positions_and_metadata(world):
    js = view_to_json(world, ownership_view(world))
    assert len(js["nodes"]) == len(world.tables["entities"])
    assert all(isinstance(n["x"], float) and isinstance(n["y"], float) for n in js["nodes"])
    assert js["meta"]["view"] == "ownership" and js["data_status"] == "synthetic"
