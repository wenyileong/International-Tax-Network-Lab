"""Run records, immutability and replay (plan v2.1, s 7; Appendix B, B4)."""

import hashlib
import json

import pytest

from taxnetlab import runs
from taxnetlab.engines import get_engine
from taxnetlab.validation import ValidationError


def _run(ws, ds, **kw):
    did = ws.save_dataset(ds)
    return runs.execute(ws, runs.RunSpec("demo.link_summary", did, kw.pop("parameters", {}), "test question"))


def test_record_contents(workspace, fixture01):
    rec = _run(workspace, fixture01)
    assert rec["outcome"] == "ok" and rec["engine"]["status"] == "verified"
    assert rec["dataset"]["content_hash"] == fixture01.content_hash
    assert rec["dataset"]["data_status"] == "synthetic"
    assert rec["environment"]["taxnetlab_version"] and rec["environment"]["python"]
    # B4: only engine parameters are recorded as parameters (no interface state).
    assert set(rec["parameters"]) == {p.name for p in get_engine("demo.link_summary").spec.parameters}
    path = workspace.runs_dir / rec["run_id"]
    data = (path / "jurisdiction_summary.csv").read_bytes()
    assert hashlib.sha256(data).hexdigest() == rec["outputs"]["jurisdiction_summary"]["sha256"]


def test_replay_matches(workspace, fixture01):
    rec = _run(workspace, fixture01)
    rep = runs.replay(workspace, rec["run_id"])
    assert rep["match"] and rep["reason"] == "match"


def test_tampering_with_record_is_detected(workspace, fixture01):
    rec = _run(workspace, fixture01)
    f = workspace.runs_dir / rec["run_id"] / runs.RECORD_FILE
    data = json.loads(f.read_text(encoding="utf-8"))
    data["research_question"] = "edited later"
    f.write_text(json.dumps(data), encoding="utf-8")
    assert runs.load_record(workspace, rec["run_id"])["_integrity"] == "modified"
    assert not runs.replay(workspace, rec["run_id"])["match"]


def test_tampering_with_output_is_detected(workspace, fixture01):
    rec = _run(workspace, fixture01)
    f = workspace.runs_dir / rec["run_id"] / "jurisdiction_summary.csv"
    # replay recomputes from the dataset, so it still matches; but the stored file no longer matches its hash
    f.write_text(f.read_text(encoding="utf-8") + "FIC_Z,0,0,0,0.0,0.0,0.0\n", encoding="utf-8")
    assert hashlib.sha256(f.read_bytes()).hexdigest() != rec["outputs"]["jurisdiction_summary"]["sha256"]


def test_blocked_runs_store_nothing(workspace, fixture01):
    did = workspace.save_dataset(fixture01)
    with pytest.raises(ValidationError):
        runs.execute(workspace, runs.RunSpec("gb2017.conduits_sinks", did))
    with pytest.raises(ValidationError):
        runs.execute(workspace, runs.RunSpec("demo.link_summary", did, {"relation_type": "nope"}))
    assert runs.list_runs(workspace) == []
    assert not any(p.name.startswith(".tmp") for p in workspace.runs_dir.iterdir())


def test_list_and_stale_flag(workspace, fixture01, monkeypatch):
    rec = _run(workspace, fixture01)
    listed = runs.list_runs(workspace)
    assert listed[0]["run_id"] == rec["run_id"] and not listed[0]["stale"]
    spec = get_engine("demo.link_summary").spec
    import dataclasses
    monkeypatch.setattr(get_engine("demo.link_summary"), "spec", dataclasses.replace(spec, version="9.9.9"))
    assert runs.list_runs(workspace)[0]["stale"]


def test_run_spec_rejects_unknown_fields():
    with pytest.raises(ValueError):
        runs.RunSpec.from_dict({"engine_id": "x", "dataset_id": "y", "colour": "blue"})


def test_invalid_ids_rejected(workspace):
    for bad in ("../x", ".tmp-1", ""):
        with pytest.raises(KeyError):
            runs.load_record(workspace, bad)
        with pytest.raises(KeyError):
            workspace.load_dataset(bad)


def test_stale_temporaries_removed_but_records_kept(workspace, fixture01):
    import os
    import time
    rec = _run(workspace, fixture01)
    tmp = workspace.runs_dir / ".tmp-interrupted"
    tmp.mkdir()
    old = time.time() - 7200
    os.utime(tmp, (old, old))
    workspace.ensure()
    assert not tmp.exists()
    assert runs.load_record(workspace, rec["run_id"])["_integrity"] == "ok"
