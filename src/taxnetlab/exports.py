"""Export packages by reproducibility tier, and reproduction from a package (plan s 7.3).

Tier C (synthetic data): everything, labelled synthetic in every file. Tier A (public, redistributable data):
everything. Tier B (any licensed, non-redistributable source): the run record, dataset hashes, sources and the
specification of the data, but no dataset tables, and output tables only when the researcher confirms that the
licence permits it. The acceptance criterion: another researcher with lawful access to the same inputs can
reproduce the analysis from the package (:func:`reproduce`).
"""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

from taxnetlab import __version__, runs
from taxnetlab.buildinfo import software_citation
from taxnetlab.canonical import sha256_bytes
from taxnetlab.workspace import Workspace

FIXED_TIME = (2026, 1, 1, 0, 0, 0)
REDISTRIBUTABLE = {"public", "public_attribution"}


def tier_of(record: dict[str, Any]) -> str:
    classes = {s["licence_class"] for s in record["dataset"].get("sources", [])}
    if record["dataset"]["data_status"] == "synthetic" or classes == {"synthetic"}:
        return "C"
    if classes and classes <= REDISTRIBUTABLE | {"synthetic"}:
        return "A"
    return "B"


README = """International Tax Network Lab: export package (tier {tier})
{label}
Run {run_id}; engine {engine} ({status}); dataset {dataset_id}; packaged by version {version}.

Contents
  MANIFEST.json      SHA-256 of every file in this package
  run/record.json    the immutable run record (parameters, assumptions, warnings, environment, output hashes)
  run/outputs/       output tables{outputs_note}
  data/              {data_note}
  report.html        a readable report of the run

Reproduce
  taxnetlab reproduce <this file.zip> [--workspace DIR]
{reproduce_note}
  The engine is re-executed with the recorded parameters and every output hash is compared.

Tiers (plan s 7.3): A public data, full package; B licensed data, no data tables; C synthetic data, full package.

Cite the software: {citation}
"""


def package(ws: Workspace, run_id: str, include_outputs: bool | None = None) -> tuple[bytes, str]:
    record = runs.load_record(ws, run_id)
    tier = tier_of(record)
    if include_outputs is None:
        include_outputs = tier != "B"
    files: dict[str, bytes] = {}
    rec = {k: v for k, v in record.items() if k != "_integrity"}
    files["run/record.json"] = json.dumps(rec, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
    if include_outputs:
        for name in record["outputs"]:
            files[f"run/outputs/{name}.csv"] = runs.output_text(ws, run_id, name).encode("utf-8")
    if tier in ("A", "C"):
        ds = ws.load_dataset(record["dataset"]["dataset_id"])
        for table in ds.tables:
            files[f"data/{table}.csv"] = ds.csv_text(table).encode("utf-8")
    files["data/dataset.json"] = json.dumps({
        "dataset_id": record["dataset"]["dataset_id"], "name": record["dataset"]["name"],
        "content_hash": record["dataset"]["content_hash"], "table_hashes": record["dataset"]["table_hashes"],
        "sources": record["dataset"]["sources"], "data_status": record["dataset"]["data_status"],
        "synthetic": tier == "C", "included": tier in ("A", "C")}, indent=2, ensure_ascii=False).encode("utf-8")
    from taxnetlab.api import Api  # report uses the typed outputs; imported here to avoid a cycle

    api = Api(ws)
    from taxnetlab.reports import run_report_html

    files["report.html"] = run_report_html(record, api._outputs(run_id), software_citation()).encode("utf-8")
    label = ("SYNTHETIC DATA: every jurisdiction, company, value and rate in this package is fictional."
             if tier == "C" else "")
    files["README.txt"] = README.format(
        tier=tier, label=label, run_id=run_id, engine=record["engine"]["engine_id"], status=record["engine"]["status"],
        dataset_id=record["dataset"]["dataset_id"], version=__version__, citation=software_citation(),
        outputs_note="" if include_outputs else " (not included: confirm that the data licence permits it)",
        data_note="all dataset tables and their hashes" if tier in ("A", "C") else
        "dataset hashes and sources only (licensed data are not redistributed)",
        reproduce_note="" if tier in ("A", "C") else
        "  Tier B: first import the same licensed data so that the dataset identifier matches data/dataset.json.",
    ).encode("utf-8")
    manifest = {"package_type": "taxnetlab.export", "tier": tier, "run_id": run_id, "synthetic": tier == "C",
                "taxnetlab_version": __version__, "files": {n: sha256_bytes(b) for n, b in sorted(files.items())}}
    files["MANIFEST.json"] = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, files[name])
    return buf.getvalue(), tier


def reproduce(ws: Workspace, data: bytes) -> dict[str, Any]:
    """Re-run the packaged run in ``ws`` and compare output hashes with the packaged record."""
    from taxnetlab.datasets import Dataset

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = set(z.namelist())
        manifest = json.loads(z.read("MANIFEST.json"))
        bad = [n for n, h in manifest["files"].items() if n not in names or sha256_bytes(z.read(n)) != h]
        record = json.loads(z.read("run/record.json"))
        dsinfo = json.loads(z.read("data/dataset.json"))
        texts = {n[5:-4]: z.read(n).decode("utf-8") for n in names if n.startswith("data/") and n.endswith(".csv")}
    report: dict[str, Any] = {"run_id": record["run_id"], "tier": manifest["tier"], "package_intact": not bad,
                              "altered_files": bad}
    if bad:
        report.update(reproduced=False, reason="package_altered")
        return report
    did = dsinfo["dataset_id"]
    if texts:
        ds, vrep = Dataset.from_csv_texts(record["dataset"]["name"], texts, {"origin": "export_package"})
        if ds is None:
            report.update(reproduced=False, reason="dataset_invalid", validation=vrep.to_dict())
            return report
        if ds.dataset_id != did:
            report.update(reproduced=False, reason="dataset_id_differs")
            return report
        ws.save_dataset(ds)
    elif did not in ws.dataset_ids():
        report.update(reproduced=False, reason="licensed_dataset_needed",
                      note=f"Import the licensed data first; the dataset identifier must be {did}.")
        return report
    spec = record["run_spec"]
    out = runs.execute(ws, runs.RunSpec.from_dict({**spec, "parameters": record["parameters"],
                                                    "research_question": f"reproduction of {record['run_id']}"}))
    same = {n: out["outputs"].get(n, {}).get("sha256") == info["sha256"] for n, info in record["outputs"].items()}
    report.update(reproduced=all(same.values()) and out["outcome"] == record["outcome"], outputs=same,
                  new_run_id=out["run_id"], engine_version_then=record["engine"]["version"],
                  engine_version_now=out["engine"]["version"],
                  reason="match" if all(same.values()) else "outputs_differ")
    return report
