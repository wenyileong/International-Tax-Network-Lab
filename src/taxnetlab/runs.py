"""Runs, immutable run records and replay (plan v2.1, s 7).

A run is one engine variant executed on one dataset version with one parameter set. Records are
written once, atomically (outputs and record are assembled in a temporary folder that is renamed
into place), and carry a hash of their own content so that later modification is detected.
Interface state is never recorded as a model parameter.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from taxnetlab import STORAGE_SCHEMA_VERSION
from taxnetlab.buildinfo import environment
from taxnetlab.canonical import canonical_csv, canonical_json, sha256_text
from taxnetlab.engines import get_engine
from taxnetlab.engines.base import OK
from taxnetlab.validation import ValidationError, ValidationReport
from taxnetlab.workspace import Workspace

RECORD_FILE = "record.json"


@dataclass
class RunSpec:
    engine_id: str
    dataset_id: str
    parameters: dict[str, Any] = field(default_factory=dict)
    research_question: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunSpec":
        unknown = set(data) - {"engine_id", "dataset_id", "parameters", "research_question"}
        if unknown:
            raise ValueError(f"unknown run specification field(s): {sorted(unknown)}")
        if not data.get("engine_id") or not data.get("dataset_id"):
            raise ValueError("engine_id and dataset_id are required")
        return cls(str(data["engine_id"]), str(data["dataset_id"]), dict(data.get("parameters") or {}),
                   str(data.get("research_question") or ""))

    @classmethod
    def from_file(cls, path: Path) -> "RunSpec":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def to_dict(self) -> dict[str, Any]:
        return {"engine_id": self.engine_id, "dataset_id": self.dataset_id, "parameters": self.parameters,
                "research_question": self.research_question}


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _new_run_id() -> str:
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{secrets.token_hex(3)}"


def _record_hash(record: dict[str, Any]) -> str:
    body = {k: v for k, v in record.items() if k != "record_sha256"}
    return sha256_text(canonical_json(body))


def _serialise_outputs(spec, outputs: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    texts = {}
    for name, rows in outputs.items():
        columns = spec.outputs.get(name)
        if columns is None:
            raise ValueError(f"engine produced undeclared output '{name}'")
        key = spec.output_keys.get(name, columns[:1])
        texts[name] = canonical_csv(rows, columns, key)
    return texts


def execute(workspace: Workspace, run_spec: RunSpec) -> dict[str, Any]:
    """Execute a run and store its record. Returns the record.

    Blocking validation errors raise :class:`ValidationError` and store nothing. Engine failures
    that the engine reports as an outcome state (for example ``not_converged``) are stored, so that
    failed attempts are part of the record.
    """
    engine = get_engine(run_spec.engine_id)
    spec = engine.spec
    dataset = workspace.load_dataset(run_spec.dataset_id)
    report = ValidationReport()
    report.extend(dataset.validate())
    params, prep = engine.resolve_parameters(run_spec.parameters)
    report.extend(prep)
    if not spec.runnable:
        report.error("engine_not_runnable", f"{spec.engine_id} is at '{spec.status}' status: {spec.next_step}",
                     params={"engine": spec.engine_id, "status": spec.status})
    if report.ok:
        report.extend(engine.validate(dataset, params))
    if not report.ok:
        raise ValidationError(report, "run blocked")

    started = _utc_now()
    result = engine.run(dataset, params)
    finished = _utc_now()
    texts = _serialise_outputs(spec, result.outputs) if result.outcome == OK else {}

    run_id = _new_run_id()
    record: dict[str, Any] = {
        "record_type": "taxnetlab.run",
        "storage_schema_version": STORAGE_SCHEMA_VERSION,
        "run_id": run_id,
        "research_question": run_spec.research_question,
        "started_utc": started,
        "finished_utc": finished,
        "engine": {"engine_id": spec.engine_id, "display_name": spec.display_name, "track": spec.track,
                   "variant": spec.variant, "version": spec.version, "status": spec.status,
                   "spec_ref": spec.spec_ref, "boundary": spec.boundary},
        "dataset": {"dataset_id": dataset.dataset_id, "name": dataset.name, "content_hash": dataset.content_hash,
                    "data_status": dataset.data_status, "table_hashes": dataset.table_hashes(),
                    "sources": [{"source_id": s["source_id"], "title": s["title"],
                                 "licence_class": s["licence_class"]} for s in dataset.tables["sources"]]},
        "parameters": params,
        "run_spec": run_spec.to_dict(),
        "validation": report.to_dict(),
        "outcome": result.outcome,
        "warnings": result.warnings,
        "assumptions": result.assumptions,
        "trace": result.trace,
        "measures": [m.to_dict() for m in spec.measures],
        "outputs": {name: {"file": f"{name}.csv", "rows": len(result.outputs[name]), "sha256": sha256_text(text)}
                    for name, text in texts.items()},
        "environment": environment(),
    }
    record["record_sha256"] = _record_hash(record)

    workspace.runs_dir.mkdir(parents=True, exist_ok=True)
    tmp = workspace.runs_dir / f".tmp-{run_id}"
    tmp.mkdir()
    try:
        for name, text in texts.items():
            (tmp / f"{name}.csv").write_text(text, encoding="utf-8", newline="")
        (tmp / RECORD_FILE).write_text(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False),
                                       encoding="utf-8")
        target = workspace.runs_dir / run_id
        if target.exists():
            raise FileExistsError(f"run {run_id} already exists; records are immutable")
        os.replace(tmp, target)
    except BaseException:
        for f in tmp.glob("*"):
            f.unlink()
        tmp.rmdir()
        raise
    return record


def _run_dir(workspace: Workspace, run_id: str) -> Path:
    if not run_id or "/" in run_id or "\\" in run_id or run_id.startswith("."):
        raise KeyError(f"invalid run id '{run_id}'")
    path = workspace.runs_dir / run_id
    if not (path / RECORD_FILE).exists():
        raise KeyError(f"unknown run '{run_id}'")
    return path


def load_record(workspace: Workspace, run_id: str) -> dict[str, Any]:
    record = json.loads((_run_dir(workspace, run_id) / RECORD_FILE).read_text(encoding="utf-8"))
    record["_integrity"] = "ok" if _record_hash(record) == record.get("record_sha256") else "modified"
    return record


def output_text(workspace: Workspace, run_id: str, name: str) -> str:
    record = load_record(workspace, run_id)
    if name not in record["outputs"]:
        raise KeyError(f"run {run_id} has no output '{name}'")
    return (_run_dir(workspace, run_id) / record["outputs"][name]["file"]).read_text(encoding="utf-8")


def list_runs(workspace: Workspace) -> list[dict[str, Any]]:
    if not workspace.runs_dir.exists():
        return []
    rows = []
    for path in sorted(workspace.runs_dir.iterdir(), reverse=True):
        if not path.is_dir() or path.name.startswith(".") or not (path / RECORD_FILE).exists():
            continue
        try:
            rec = load_record(workspace, path.name)
        except (OSError, ValueError):
            rows.append({"run_id": path.name, "integrity": "unreadable"})
            continue
        rows.append(summarise(rec))
    return rows


def summarise(rec: dict[str, Any]) -> dict[str, Any]:
    stale = False
    try:
        current = get_engine(rec["engine"]["engine_id"]).spec
        stale = current.version != rec["engine"]["version"] or current.status != rec["engine"]["status"]
    except KeyError:
        stale = True
    return {
        "run_id": rec["run_id"], "started_utc": rec["started_utc"], "engine_id": rec["engine"]["engine_id"],
        "engine_name": rec["engine"]["display_name"], "track": rec["engine"]["track"],
        "status": rec["engine"]["status"], "dataset_id": rec["dataset"]["dataset_id"],
        "dataset_name": rec["dataset"]["name"], "data_status": rec["dataset"]["data_status"],
        "outcome": rec["outcome"], "research_question": rec.get("research_question", ""),
        "integrity": rec.get("_integrity", "ok"), "stale": stale,
    }


def replay(workspace: Workspace, run_id: str) -> dict[str, Any]:
    """Re-execute a stored run in memory and compare output hashes. Stores nothing."""
    record = load_record(workspace, run_id)
    report: dict[str, Any] = {"run_id": run_id, "integrity": record["_integrity"], "outputs": {}, "notes": []}
    try:
        dataset = workspace.load_dataset(record["dataset"]["dataset_id"])
    except KeyError:
        report.update(match=False, reason="dataset_missing")
        return report
    if dataset.content_hash != record["dataset"]["content_hash"]:
        report.update(match=False, reason="dataset_changed")
        return report
    engine = get_engine(record["engine"]["engine_id"])
    if engine.spec.version != record["engine"]["version"]:
        report["notes"].append(f"engine version now {engine.spec.version}; recorded {record['engine']['version']}")
    params, prep = engine.resolve_parameters(record["parameters"])
    if not prep.ok:
        report.update(match=False, reason="parameters_no_longer_valid")
        return report
    result = engine.run(dataset, params)
    texts = _serialise_outputs(engine.spec, result.outputs) if result.outcome == OK else {}
    match = result.outcome == record["outcome"] and set(texts) == set(record["outputs"])
    for name, info in record["outputs"].items():
        now = sha256_text(texts[name]) if name in texts else None
        same = now == info["sha256"]
        match = match and same
        report["outputs"][name] = {"recorded": info["sha256"], "replayed": now, "match": same}
    report.update(match=match and record["_integrity"] == "ok", outcome=result.outcome,
                  reason="match" if match else "outputs_differ")
    if record["_integrity"] != "ok":
        report["reason"] = "record_modified"
    return report
