"""Reference data (plan docs/PLAN_1_0_RC3_SCAFFOLD.md, F1): GDP read from the World Bank's own CSV download.

A reference set is content-addressed and never edited: ``workspace/reference/<id>/`` holds the original file,
``values.json`` (jurisdiction -> period -> value) and ``meta.json``. The Lab never downloads anything; the
researcher downloads the file (data.worldbank.org, indicator NY.GDP.MKTP.CD, "Download CSV") and records the
date it was retrieved. Values are kept exactly as written in the file; regional and income-group aggregates,
which carry codes that are not assigned ISO 3166-1 alpha-3 codes, are left out.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re
from pathlib import Path
from typing import Any

from taxnetlab.canonical import sha256_bytes

WDI_GDP = "NY.GDP.MKTP.CD"
INDICATORS = {WDI_GDP: {"attribute": "gdp", "unit": "currency_units", "currency": "USD",
                        "title": "World Bank, World Development Indicators: GDP (current US$) (NY.GDP.MKTP.CD)"}}
MAX_BYTES = 32 * 1024 * 1024
YEAR = re.compile(r"^\d{4}$")


class ReferenceError(ValueError):
    pass


def parse_wdi_csv(data: bytes, known_codes: set[str]) -> dict[str, Any]:
    """Values by jurisdiction and year from a World Bank indicator CSV; aggregates and empty cells dropped."""
    if len(data) > MAX_BYTES:
        raise ReferenceError("the file is larger than a World Bank indicator file can be")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ReferenceError("the file is not UTF-8 text; use the World Bank's CSV download unchanged") from None
    rows = list(csv.reader(io.StringIO(text)))
    head = next((i for i, r in enumerate(rows) if r[:4] == ["Country Name", "Country Code", "Indicator Name",
                                                             "Indicator Code"]), None)
    if head is None:
        raise ReferenceError("not a World Bank indicator CSV: no header 'Country Name, Country Code, Indicator Name, "
                             "Indicator Code'")
    header = rows[head]
    years = [(i, h.strip()) for i, h in enumerate(header) if YEAR.match(h.strip())]
    if not years:
        raise ReferenceError("the file has no year columns")
    values: dict[str, dict[str, float]] = {}
    indicators = set()
    dropped = 0
    for r in rows[head + 1:]:
        if len(r) < 4 or not r[1].strip():
            continue
        code, indicator = r[1].strip().upper(), r[3].strip()
        indicators.add(indicator)
        if code not in known_codes:
            dropped += 1
            continue
        for i, year in years:
            cell = r[i].strip() if i < len(r) else ""
            if not cell:
                continue
            try:
                v = float(cell)
            except ValueError:
                raise ReferenceError(f"{code} {year}: '{cell}' is not a number") from None
            if v == v and v not in (float("inf"), float("-inf")):
                values.setdefault(code, {})[year] = v
    if len(indicators) != 1:
        raise ReferenceError(f"the file must hold one indicator; it holds {sorted(indicators) or 'none'}")
    indicator = indicators.pop()
    if indicator not in INDICATORS:
        raise ReferenceError(f"indicator {indicator} is not supported; supported: {', '.join(INDICATORS)}")
    return {"indicator": indicator, "values": values, "aggregates_dropped": dropped,
            "periods": sorted({y for v in values.values() for y in v})}


class ReferenceStore:
    def __init__(self, folder: Path):
        self.folder = Path(folder)

    def add(self, data: bytes, retrieved: str, filename: str = "") -> dict[str, Any]:
        from taxnetlab.registry import iso3_names

        try:
            if dt.date.fromisoformat(str(retrieved)) > dt.date.today():
                raise ReferenceError("the retrieval date is in the future")
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ReferenceError):
                raise
            raise ReferenceError("the retrieval date must be YYYY-MM-DD") from None
        parsed = parse_wdi_csv(data, set(iso3_names()))
        file_hash = sha256_bytes(data)
        rid = file_hash[:12]
        target = self.folder / rid
        meta = {"reference_id": rid, "indicator": parsed["indicator"], **INDICATORS[parsed["indicator"]],
                "file_sha256": file_hash, "filename": Path(filename or "worldbank.csv").name, "retrieved": retrieved,
                "jurisdictions": len(parsed["values"]), "periods": parsed["periods"],
                "aggregates_dropped": parsed["aggregates_dropped"]}
        if (target / "meta.json").is_file():
            return json.loads((target / "meta.json").read_text(encoding="utf-8"))
        target.mkdir(parents=True, exist_ok=True)
        (target / "original.csv").write_bytes(data)
        (target / "values.json").write_text(json.dumps(parsed["values"], sort_keys=True), encoding="utf-8")
        tmp = target / "meta.json.tmp"
        tmp.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(target / "meta.json")  # written last: a set without meta.json is incomplete and ignored
        return meta

    def _dir(self, reference_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{12}", reference_id or ""):
            raise KeyError(f"unknown reference set '{reference_id}'")
        d = self.folder / reference_id
        if not (d / "meta.json").is_file():
            raise KeyError(f"unknown reference set '{reference_id}'")
        return d

    def meta(self, reference_id: str) -> dict[str, Any]:
        return json.loads((self._dir(reference_id) / "meta.json").read_text(encoding="utf-8"))

    def list(self) -> list[dict[str, Any]]:
        if not self.folder.is_dir():
            return []
        out = []
        for d in sorted(self.folder.iterdir()):
            try:
                out.append(self.meta(d.name))
            except (KeyError, ValueError, OSError):
                continue
        return out

    def values(self, reference_id: str) -> dict[str, dict[str, float]]:
        d = self._dir(reference_id)
        meta = self.meta(reference_id)
        if sha256_bytes((d / "original.csv").read_bytes()) != meta["file_sha256"]:
            raise ReferenceError(f"reference set {reference_id} has been modified since it was added")
        return json.loads((d / "values.json").read_text(encoding="utf-8"))
