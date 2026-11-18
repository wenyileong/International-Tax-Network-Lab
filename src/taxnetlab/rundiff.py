"""Compare two runs (plan F9): what differs in method, data, parameters, assumptions, warnings and outputs.

Output rows are matched by the engine's declared output keys; a table without declared keys is compared by
its whole rows. Values are compared exactly as stored (records keep numbers to 12 decimal places).
"""

from __future__ import annotations

from typing import Any

MAX_ROWS = 200  # changed rows listed per table; the counts are always complete


def _rows_by_key(table: dict[str, Any], key: tuple[str, ...]) -> dict[tuple, dict[str, Any]]:
    cols = list(table.get("columns") or [])
    keys = key or tuple(cols)
    return {tuple(r.get(k) for k in keys): r for r in table.get("rows") or []}


def diff(a: dict[str, Any], b: dict[str, Any], outputs_a: dict[str, dict[str, Any]],
         outputs_b: dict[str, dict[str, Any]], output_keys: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    same_engine = a["engine"]["engine_id"] == b["engine"]["engine_id"]
    method = [{"field": f, "a": a["engine"].get(f), "b": b["engine"].get(f)}
              for f in ("engine_id", "version", "status", "variant") if a["engine"].get(f) != b["engine"].get(f)]
    data = [{"field": f, "a": a["dataset"].get(f), "b": b["dataset"].get(f)}
            for f in ("dataset_id", "name", "content_hash", "data_status") if a["dataset"].get(f) != b["dataset"].get(f)]
    pa, pb = a.get("parameters") or {}, b.get("parameters") or {}
    params = [{"name": k, "a": pa.get(k), "b": pb.get(k)} for k in sorted(set(pa) | set(pb)) if pa.get(k) != pb.get(k)]
    lists = {}
    for field in ("assumptions", "warnings"):
        la, lb = list(a.get(field) or []), list(b.get(field) or [])
        lists[field] = {"only_a": [x for x in la if x not in lb], "only_b": [x for x in lb if x not in la]}
    outputs: dict[str, Any] = {}
    for name in sorted(set(outputs_a) | set(outputs_b)):
        ta, tb = outputs_a.get(name), outputs_b.get(name)
        ha = (a.get("outputs") or {}).get(name, {}).get("sha256")
        hb = (b.get("outputs") or {}).get(name, {}).get("sha256")
        if ta is None or tb is None:
            outputs[name] = {"present": "a" if tb is None else "b", "identical": False, "added": 0, "removed": 0,
                             "changed": 0, "rows": []}
            continue
        key = tuple(output_keys.get(name) or ()) if same_engine else ()
        ra, rb = _rows_by_key(ta, key), _rows_by_key(tb, key)
        changed_rows = []
        for k in sorted(set(ra) & set(rb), key=str):
            cols = [c for c in sorted(set(ra[k]) | set(rb[k])) if ra[k].get(c) != rb[k].get(c)]
            if cols:
                changed_rows.append({"key": dict(zip(key, k)) if key else None, "columns": cols,
                                     "a": {c: ra[k].get(c) for c in cols}, "b": {c: rb[k].get(c) for c in cols}})
        outputs[name] = {"present": "both", "identical": ha == hb and ha is not None, "added": len(set(rb) - set(ra)),
                         "removed": len(set(ra) - set(rb)), "changed": len(changed_rows), "key": list(key),
                         "rows": changed_rows[:MAX_ROWS], "truncated": len(changed_rows) > MAX_ROWS}
    identical = (not method and not data and not params and all(o["identical"] for o in outputs.values())
                 and a.get("outcome") == b.get("outcome"))
    return {"run_a": a["run_id"], "run_b": b["run_id"], "identical": identical, "same_engine": same_engine,
            "outcome": {"a": a.get("outcome"), "b": b.get("outcome")}, "method": method, "data": data,
            "parameters": params, **lists, "outputs": outputs}
