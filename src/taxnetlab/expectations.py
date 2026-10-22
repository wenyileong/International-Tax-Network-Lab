"""Expectation register and replication reports (plan s 7.5; status `replicated` in s 3).

Before an engine is run on real data for replication, the researcher records, dated and hashed, the published
results to be matched, the comparison statistic, the tolerance and the decision rule. A frozen entry cannot be
edited: its hash is checked on every use, and a correction is a new entry that names the one it supersedes.
A replication report compares one stored run with one frozen entry; it is refused if the run started before
the entry was frozen, so that expectations always precede the results they judge.

Comparison kinds:

* ``set``: the set of keys in an output table where a column is true (for example the sink jurisdictions),
  compared with the expected set by recall, precision or Jaccard index;
* ``top_k``: the k keys with the highest values of a column, compared with the expected list by overlap share;
* ``value``: one numeric cell (row selected by key), compared with the expected value within an absolute or
  relative tolerance.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

from taxnetlab.canonical import canonical_json, sha256_text

KINDS = ("set", "top_k", "value")
STATISTICS = {"set": ("recall", "precision", "jaccard"), "top_k": ("overlap",), "value": ("absolute", "relative")}
ID_RE = re.compile(r"^[A-Za-z0-9_.\-]{3,64}$")
VERDICTS = ("replicated", "replicated_with_discrepancies", "not_replicated")


class ExpectationError(ValueError):
    pass


def entry_hash(entry: dict[str, Any]) -> str:
    return sha256_text(canonical_json({k: v for k, v in entry.items() if k != "entry_sha256"}))


def check_entry(entry: dict[str, Any], frozen: bool = False) -> None:
    """Structural checks; raises ExpectationError with every problem found."""
    problems = []
    for f in ("entry_id", "title", "engine_id", "source", "comparisons", "decision_rule"):
        if not entry.get(f):
            problems.append(f"missing '{f}'")
    if entry.get("entry_id") and not ID_RE.match(entry["entry_id"]):
        problems.append("entry_id: 3 to 64 letters, digits, '.', '_' or '-'")
    for n, c in enumerate(entry.get("comparisons") or [], 1):
        kind = c.get("kind")
        if kind not in KINDS:
            problems.append(f"comparison {n}: kind must be one of {KINDS}")
            continue
        if c.get("statistic") not in STATISTICS[kind]:
            problems.append(f"comparison {n}: statistic must be one of {STATISTICS[kind]}")
        for f in ("label", "output", "key"):
            if not c.get(f):
                problems.append(f"comparison {n}: missing '{f}'")
        if kind == "set" and (not c.get("flag") or not isinstance(c.get("expected"), list)):
            problems.append(f"comparison {n}: a set comparison needs 'flag' and a list 'expected'")
        if kind == "top_k" and (not c.get("column") or not isinstance(c.get("expected"), list) or not c["expected"]):
            problems.append(f"comparison {n}: a top_k comparison needs 'column' and a non-empty list 'expected'")
        if kind == "value" and (not c.get("column") or "row" not in c or not isinstance(c.get("expected"), (int, float))):
            problems.append(f"comparison {n}: a value comparison needs 'row', 'column' and a numeric 'expected'")
        thr = c.get("threshold")
        if not isinstance(thr, (int, float)) or thr < 0:
            problems.append(f"comparison {n}: 'threshold' must be a non-negative number")
    rule = entry.get("decision_rule") or {}
    share = rule.get("discrepancies_if_share_at_least")
    if not isinstance(share, (int, float)) or not 0 <= share <= 1:
        problems.append("decision_rule.discrepancies_if_share_at_least must lie in [0, 1]")
    if frozen:
        for f in ("frozen_utc", "frozen_by", "entry_sha256"):
            if not entry.get(f):
                problems.append(f"frozen entry lacks '{f}'")
        if entry.get("entry_sha256") and entry_hash(entry) != entry["entry_sha256"]:
            problems.append("the entry has been modified after freezing (hash mismatch)")
    if problems:
        raise ExpectationError("; ".join(problems))


class Register:
    """Frozen entries kept in a workspace folder, one JSON file per entry."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)

    def _path(self, entry_id: str) -> Path:
        if not ID_RE.match(entry_id or ""):
            raise KeyError(f"invalid expectation id '{entry_id}'")
        return self.folder / f"{entry_id}.json"

    def freeze(self, draft: dict[str, Any], frozen_by: str, now: str | None = None) -> dict[str, Any]:
        entry = {k: v for k, v in draft.items() if k not in ("frozen_utc", "frozen_by", "entry_sha256", "status")}
        check_entry(entry)
        if not (frozen_by or "").strip():
            raise ExpectationError("frozen_by is required")
        sup = entry.get("supersedes")
        if sup:
            self.load(sup)  # must exist and be intact
        path = self._path(entry["entry_id"])
        if path.exists():
            raise ExpectationError(f"entry '{entry['entry_id']}' is already frozen; record a correction as a new entry "
                                   "that supersedes it")
        entry["frozen_utc"] = now or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        entry["frozen_by"] = frozen_by.strip()
        entry["entry_sha256"] = entry_hash(entry)
        self.folder.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(entry, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
        return entry

    def load(self, entry_id: str) -> dict[str, Any]:
        path = self._path(entry_id)
        if not path.exists():
            raise KeyError(f"unknown expectation '{entry_id}'")
        entry = json.loads(path.read_text(encoding="utf-8"))
        check_entry(entry, frozen=True)
        return entry

    def list(self) -> list[dict[str, Any]]:
        out = []
        for path in sorted(self.folder.glob("*.json")) if self.folder.exists() else []:
            try:
                e = self.load(path.stem)
                state = "frozen"
            except (ExpectationError, KeyError, json.JSONDecodeError) as exc:
                e, state = {"entry_id": path.stem, "error": str(exc)}, "invalid"
            superseded = False
            out.append({"entry_id": e.get("entry_id"), "title": e.get("title"), "engine_id": e.get("engine_id"),
                        "frozen_utc": e.get("frozen_utc"), "frozen_by": e.get("frozen_by"), "state": state,
                        "supersedes": e.get("supersedes"), "superseded": superseded, "error": e.get("error")})
        replaced = {e["supersedes"] for e in out if e.get("supersedes")}
        for e in out:
            e["superseded"] = e["entry_id"] in replaced
        return out


# ------------------------------------------------------------------ comparison
def compare(entry: dict[str, Any], record: dict[str, Any], outputs: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Replication report for one run against one frozen entry."""
    check_entry(entry, frozen=True)
    problems = []
    if record["engine"]["engine_id"] != entry["engine_id"]:
        problems.append(f"the run is of {record['engine']['engine_id']}, the entry expects {entry['engine_id']}")
    if _when(record["started_utc"]) < _when(entry["frozen_utc"]):
        problems.append("the run started before the expectation was frozen; expectations must precede results")
    if record["outcome"] != "ok":
        problems.append(f"the run's outcome is '{record['outcome']}'")
    for name, value in (entry.get("parameters") or {}).items():
        if record["parameters"].get(name) != value:
            problems.append(f"parameter '{name}' is {record['parameters'].get(name)!r} in the run; the entry requires {value!r}")
    rows_out = []
    for c in entry["comparisons"]:
        rows = outputs.get(c["output"])
        if rows is None:
            rows_out.append({"label": c["label"], "pass": False, "observed": None, "statistic": None,
                             "note": f"output '{c['output']}' not in the run"})
            continue
        rows_out.append(_compare_one(c, rows))
    passed = sum(r["pass"] for r in rows_out)
    share = passed / len(rows_out) if rows_out else 0.0
    rule = entry["decision_rule"]
    if problems:
        verdict = "invalid"
    elif passed == len(rows_out):
        verdict = "replicated"
    elif share >= rule["discrepancies_if_share_at_least"]:
        verdict = "replicated_with_discrepancies"
    else:
        verdict = "not_replicated"
    return {"report_type": "taxnetlab.replication", "entry_id": entry["entry_id"], "entry_sha256": entry["entry_sha256"],
            "run_id": record["run_id"], "record_sha256": record.get("record_sha256"), "engine_id": entry["engine_id"],
            "dataset_id": record["dataset"]["dataset_id"], "data_status": record["dataset"]["data_status"],
            "comparisons": rows_out, "passed": passed, "total": len(rows_out), "share_passed": round(share, 6),
            "verdict": verdict, "problems": problems,
            "note": "A replication verdict on synthetic data tests the procedure only; it says nothing about the source."
            if record["dataset"]["data_status"] == "synthetic" else None}


def _compare_one(c: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    key, thr = c["key"], c["threshold"]
    if c["kind"] == "set":
        observed = sorted({str(r[key]) for r in rows if _truthy(r.get(c["flag"]))})
        exp, obs = set(map(str, c["expected"])), set(observed)
        inter = len(exp & obs)
        stat = {"recall": inter / len(exp) if exp else 1.0, "precision": inter / len(obs) if obs else (1.0 if not exp else 0.0),
                "jaccard": inter / len(exp | obs) if exp | obs else 1.0}[c["statistic"]]
        return {"label": c["label"], "pass": stat >= thr, "observed": observed, "statistic": round(stat, 6),
                "missing": sorted(exp - obs), "unexpected": sorted(obs - exp), "note": None}
    if c["kind"] == "top_k":
        k = len(c["expected"])
        ranked = sorted((r for r in rows if r.get(c["column"]) is not None),
                        key=lambda r: (-float(r[c["column"]]), str(r[key])))
        observed = [str(r[key]) for r in ranked[:k]]
        stat = len(set(observed) & set(map(str, c["expected"]))) / k
        return {"label": c["label"], "pass": stat >= thr, "observed": observed, "statistic": round(stat, 6), "note": None}
    match = [r for r in rows if str(r.get(key)) == str(c["row"])]
    if not match or match[0].get(c["column"]) is None:
        return {"label": c["label"], "pass": False, "observed": None, "statistic": None, "note": "value not found"}
    value = float(match[0][c["column"]])
    diff = abs(value - c["expected"])
    stat = diff if c["statistic"] == "absolute" else (diff / abs(c["expected"]) if c["expected"] else float("inf"))
    return {"label": c["label"], "pass": stat <= thr, "observed": value, "statistic": round(stat, 9) if stat != float("inf") else None,
            "note": None}


def _when(stamp: str) -> dt.datetime:
    return dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def _truthy(v: Any) -> bool:
    return v is True or (isinstance(v, str) and v.lower() == "true") or v == 1
