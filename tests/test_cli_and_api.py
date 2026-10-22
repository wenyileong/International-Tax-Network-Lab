"""Command line and service layer."""

import json

from taxnetlab.api import Api
from taxnetlab.cli import main


def test_cli_generate_run_replay(tmp_path, capsys):
    ws = str(tmp_path / "ws")
    assert main(["generate", "--workspace", ws, "--seed", "3"]) == 0
    did = capsys.readouterr().out.split()[0]
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"engine_id": "demo.link_summary", "dataset_id": did, "parameters": {},
                                "research_question": "cli"}), encoding="utf-8")
    assert main(["run", str(spec), "--workspace", ws]) == 0
    run_id = capsys.readouterr().out.split()[1]
    assert main(["replay", run_id, "--workspace", ws]) == 0
    assert main(["datasets", "--workspace", ws]) == 0


def test_cli_blocked_run_exit_code(tmp_path, capsys):
    ws = str(tmp_path / "ws")
    main(["generate", "--workspace", ws])
    did = capsys.readouterr().out.split()[0]
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"engine_id": "us10417262.tda", "dataset_id": did}), encoding="utf-8")
    assert main(["run", str(spec), "--workspace", ws]) == 2


def test_import_via_api_round_trip(workspace, world):
    api = Api(workspace)
    texts = {t: world.csv_text(t) for t in world.tables}
    out = api.import_csv("Imported copy", texts)
    assert out["saved"] and out["dataset_id"] == world.dataset_id


def test_import_blocked_reports_errors(workspace):
    out = Api(workspace).import_csv("bad", {"sources": "source_id\nS\n"})
    assert not out["saved"] and not out["validation"]["ok"]


def test_default_dataset_only_once(workspace):
    api = Api(workspace)
    assert api.ensure_default_dataset() is not None
    assert api.ensure_default_dataset() is None
    assert len(api.datasets()) == 1


def test_selftest_passes(capsys):
    """The end-to-end self-test run by CI on the executable must also pass from source."""
    assert main(["selftest"]) == 0
    assert "Self-test passed." in capsys.readouterr().out
