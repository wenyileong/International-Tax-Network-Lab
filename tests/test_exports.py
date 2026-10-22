"""Run reports and export packages by tier (plan s 7.3; Phase 8)."""

import copy
import io
import json
import zipfile

from taxnetlab.api import Api
from taxnetlab.cli import main
from taxnetlab.datasets import Dataset
from taxnetlab.exports import tier_of
from taxnetlab.workspace import Workspace


def _run(api, did, engine="vtrl2018.tax_routing"):
    out = api.run({"engine_id": engine, "dataset_id": did, "parameters": {}, "research_question": "Q <b>&"})
    assert out["executed"]
    return out["record"]["run_id"]


def test_synthetic_package_reproduces_elsewhere(tmp_path):
    a = Api(Workspace(tmp_path / "a"))
    did = a.generate_synthetic({"seed": 4, "n_jurisdictions": 7})["dataset_id"]
    rid = _run(a, did)
    data, tier = a.export_package(rid)
    assert tier == "C"
    z = zipfile.ZipFile(io.BytesIO(data))
    names = set(z.namelist())
    assert {"MANIFEST.json", "README.txt", "report.html", "run/record.json", "data/ownership.csv"} <= names
    assert "SYNTHETIC" in z.read("README.txt").decode() and json.loads(z.read("MANIFEST.json"))["synthetic"]
    assert data == a.export_package(rid)[0]  # byte-identical packages
    b = Api(Workspace(tmp_path / "b"))  # another researcher's empty workspace
    rep = b.reproduce_package(data)
    assert rep["reproduced"] and rep["package_intact"], rep


def test_altered_package_is_refused(tmp_path):
    a = Api(Workspace(tmp_path / "a"))
    did = a.generate_synthetic({"seed": 4, "n_jurisdictions": 6})["dataset_id"]
    data, _ = a.export_package(_run(a, did, "demo.link_summary"))
    src = zipfile.ZipFile(io.BytesIO(data))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in src.namelist():
            body = src.read(n)
            if n == "data/tax_domestic.csv":
                body = body.replace(b"0.25", b"0.26")
            z.writestr(n, body)
    rep = Api(Workspace(tmp_path / "b")).reproduce_package(buf.getvalue())
    assert not rep["reproduced"] and rep["reason"] == "package_altered"


def test_tier_b_withholds_data_and_outputs(tmp_path):
    from taxnetlab.fixtures import gb_fixture

    tables = copy.deepcopy(gb_fixture().tables)
    for s in tables["sources"]:
        s["source_id"] = "ORBIS"
        s["licence_class"] = "licensed_no_redistribution"
    for t in tables.values():
        for r in t:
            if r.get("source_id") == "SYN_GENERATOR":
                r["source_id"] = "ORBIS"
    ds, rep = Dataset.from_rows("licensed", tables)
    assert ds is not None, rep.format_text()
    a = Api(Workspace(tmp_path / "a"))
    did = a.ws.save_dataset(ds)
    rid = _run(a, did, "gb2017.conduits_sinks")
    data, tier = a.export_package(rid)
    names = set(zipfile.ZipFile(io.BytesIO(data)).namelist())
    assert tier == "B" and not any(n.startswith("run/outputs/") for n in names)
    assert not any(n.startswith("data/") and n.endswith(".csv") for n in names)
    b = Api(Workspace(tmp_path / "b"))
    assert b.reproduce_package(data)["reason"] == "licensed_dataset_needed"
    b.ws.save_dataset(ds)  # the other researcher's own licensed copy
    assert b.reproduce_package(data)["reproduced"]
    with_outputs, _ = a.export_package(rid, include_outputs=True)
    assert any(n.startswith("run/outputs/") for n in zipfile.ZipFile(io.BytesIO(with_outputs)).namelist())


def test_report_escapes_and_flags(tmp_path):
    a = Api(Workspace(tmp_path / "a"))
    did = a.generate_synthetic({"seed": 4, "n_jurisdictions": 6})["dataset_id"]
    html = a.run_report(_run(a, did))
    assert "Q &lt;b&gt;&amp;" in html and "<script" not in html
    assert "Synthetic data" in html and "has not yet been verified" in html


def test_tier_rules():
    rec = {"dataset": {"data_status": "real", "sources": [{"licence_class": "public"}]}}
    assert tier_of(rec) == "A"
    rec["dataset"]["sources"].append({"licence_class": "licensed_no_redistribution"})
    assert tier_of(rec) == "B"


def test_cli_export_and_reproduce(tmp_path, capsys):
    ws = str(tmp_path / "ws")
    main(["generate", "--workspace", ws, "--seed", "2"])
    did = capsys.readouterr().out.split()[0]
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps({"engine_id": "demo.link_summary", "dataset_id": did}))
    main(["run", str(spec), "--workspace", ws])
    rid = capsys.readouterr().out.split()[1]
    pkg = tmp_path / "p.zip"
    assert main(["export", rid, "--workspace", ws, "--out", str(pkg), "--report", str(tmp_path / "r.html")]) == 0
    assert main(["reproduce", str(pkg), "--workspace", str(tmp_path / "other")]) == 0
