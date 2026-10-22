"""Expectation register and replication reports (plan s 7.5)."""

import json

import pytest

from taxnetlab.api import Api
from taxnetlab.cli import main
from taxnetlab.expectations import ExpectationError, Register, check_entry, entry_hash
from taxnetlab.fixtures import gb_fixture

# In the conduits-and-sinks fixture (tests/test_gb2017.py), with a sink threshold of 1.5 the sinks are FIC_N and
# FIC_L, FIC_N is the only conduit, and FIC_N has the highest sink centrality (4.16).


def draft(**over):
    d = {"entry_id": "fixture-gb", "title": "Fixture expectations", "engine_id": "gb2017.conduits_sinks",
         "source": "tests/test_gb2017.py worked example", "parameters": {"sink_threshold": 1.5},
         "comparisons": [
             {"label": "sinks", "kind": "set", "output": "jurisdictions", "key": "jurisdiction_id", "flag": "is_sink",
              "expected": ["FIC_N", "FIC_L"], "statistic": "jaccard", "threshold": 1.0},
             {"label": "conduits", "kind": "set", "output": "jurisdictions", "key": "jurisdiction_id", "flag": "is_conduit",
              "expected": ["FIC_N"], "statistic": "recall", "threshold": 1.0},
             {"label": "top sink", "kind": "top_k", "output": "jurisdictions", "key": "jurisdiction_id",
              "column": "sink_centrality", "expected": ["FIC_N"], "statistic": "overlap", "threshold": 1.0},
             {"label": "N sink centrality", "kind": "value", "output": "jurisdictions", "key": "jurisdiction_id",
              "row": "FIC_N", "column": "sink_centrality", "expected": 4.16, "statistic": "absolute", "threshold": 1e-9}],
         "decision_rule": {"replicated_if": "every comparison passes", "discrepancies_if_share_at_least": 0.5}}
    d.update(over)
    return d


@pytest.fixture
def setup(workspace):
    api = Api(workspace)
    did = workspace.save_dataset(gb_fixture())
    return api, did


def test_freeze_then_replicate(setup):
    api, did = setup
    api.freeze_expectation(draft(), "Author")
    run = api.run({"engine_id": "gb2017.conduits_sinks", "dataset_id": did, "parameters": {"sink_threshold": 1.5}})
    rep = api.check_replication("fixture-gb", run["record"]["run_id"])
    assert rep["verdict"] == "replicated" and rep["passed"] == 4, rep
    assert "synthetic" in (rep["note"] or "")
    again = api.check_replication("fixture-gb", run["record"]["run_id"])
    assert again == rep  # stored once, never rewritten
    assert api.replications()[0]["verdict"] == "replicated"


def test_run_before_freeze_is_invalid(setup):
    api, did = setup
    run = api.run({"engine_id": "gb2017.conduits_sinks", "dataset_id": did, "parameters": {"sink_threshold": 1.5}})
    api.freeze_expectation(draft(), "Author")
    assert api.check_replication("fixture-gb", run["record"]["run_id"])["verdict"] == "invalid"


def test_parameter_mismatch_and_discrepancies(setup):
    api, did = setup
    d = draft()
    d["comparisons"][3]["expected"] = 5.0  # one of four comparisons fails
    api.freeze_expectation(d, "Author")
    run = api.run({"engine_id": "gb2017.conduits_sinks", "dataset_id": did, "parameters": {"sink_threshold": 1.5}})
    assert api.check_replication("fixture-gb", run["record"]["run_id"])["verdict"] == "replicated_with_discrepancies"
    wrong = api.run({"engine_id": "gb2017.conduits_sinks", "dataset_id": did, "parameters": {}})
    rep = api.check_replication("fixture-gb", wrong["record"]["run_id"])
    assert rep["verdict"] == "invalid" and any("sink_threshold" in p for p in rep["problems"])


def test_frozen_entries_cannot_change(workspace):
    reg = Register(workspace.expectations_dir)
    entry = reg.freeze(draft(), "Author")
    assert entry["entry_sha256"] == entry_hash(entry)
    with pytest.raises(ExpectationError):
        reg.freeze(draft(), "Author")  # same id: corrections are new entries
    path = workspace.expectations_dir / "fixture-gb.json"
    tampered = json.loads(path.read_text())
    tampered["comparisons"][0]["threshold"] = 0.1
    path.write_text(json.dumps(tampered))
    with pytest.raises(ExpectationError):
        reg.load("fixture-gb")
    assert reg.list()[0]["state"] == "invalid"


def test_correction_supersedes(workspace):
    reg = Register(workspace.expectations_dir)
    reg.freeze(draft(), "Author")
    reg.freeze(draft(entry_id="fixture-gb-2", supersedes="fixture-gb"), "Author")
    states = {e["entry_id"]: e["superseded"] for e in reg.list()}
    assert states == {"fixture-gb": True, "fixture-gb-2": False}
    with pytest.raises(KeyError):
        reg.freeze(draft(entry_id="fixture-gb-3", supersedes="nonexistent"), "Author")


def test_structural_checks():
    with pytest.raises(ExpectationError):
        check_entry(draft(comparisons=[{"kind": "set", "statistic": "median"}]))
    with pytest.raises(ExpectationError):
        Register.__new__(Register)  # noqa: B018 - construction alone is fine
        check_entry(draft(decision_rule={"discrepancies_if_share_at_least": 2}))


def test_repository_draft_is_well_formed():
    from pathlib import Path

    for path in (Path(__file__).resolve().parents[1] / "docs" / "expectations").glob("*.draft.json"):
        entry = json.loads(path.read_text(encoding="utf-8"))
        check_entry(entry)
        assert entry["status"].startswith("draft")


def test_cli(tmp_path, capsys, workspace):
    f = tmp_path / "d.json"
    f.write_text(json.dumps(draft()))
    ws = str(workspace.root)
    assert main(["expect", "freeze", str(f), "--workspace", ws]) == 2  # --by is required
    assert main(["expect", "freeze", str(f), "--by", "Author", "--workspace", ws]) == 0
    assert main(["expect", "list", "--workspace", ws]) == 0
    assert "fixture-gb" in capsys.readouterr().out
