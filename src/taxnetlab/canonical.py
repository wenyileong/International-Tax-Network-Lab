"""Canonical serialisation and hashing (plan v2.1, s 7.2).

Rows are sorted by primary key, columns follow schema order, floats use Python's shortest
round-trip representation and integers their decimal form (dataset parsing always yields floats
for numeric columns, so a value has one serialisation per column), booleans are
``true``/``false``, empty values are empty strings, text is UTF-8 and lines end with ``\\n``.
The result is a valid CSV file, so the hash of an exported table equals the hash recorded in
the run record.

Hashes detect change. They do not establish that the data are authentic or correct.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from typing import Any, Iterable, Sequence


def format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    return str(value)


def _sort_key(row: dict[str, Any], key: Sequence[str]) -> tuple:
    return tuple(format_cell(row.get(k)) for k in key)


def canonical_csv(rows: Iterable[dict[str, Any]], columns: Sequence[str], primary_key: Sequence[str]) -> str:
    ordered = sorted(rows, key=lambda r: _sort_key(r, primary_key))
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(list(columns))
    for row in ordered:
        writer.writerow([format_cell(row.get(c)) for c in columns])
    return buf.getvalue()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(obj: Any) -> str:
    """Deterministic JSON for hashing records (sorted keys, no insignificant whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def combine_hashes(named: dict[str, str]) -> str:
    """Hash of several named hashes, independent of insertion order."""
    text = "".join(f"{name}:{named[name]}\n" for name in sorted(named))
    return sha256_text(text)
