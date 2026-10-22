"""Datasets: typed, validated, content-addressed collections of tables (plan v2.1, s 5)."""

from __future__ import annotations

import csv
import io
import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from taxnetlab import STORAGE_SCHEMA_VERSION
from taxnetlab.canonical import canonical_csv, combine_hashes, sha256_text
from taxnetlab.schema import (
    CURRENCY_RE,
    FICTIONAL_PREFIX,
    ISO3_RE,
    REQUIRED_TABLES,
    SCHEMAS,
    TABLE_ORDER,
    parse_table,
)
from taxnetlab.validation import ValidationError, ValidationReport

EQUITY_TOLERANCE = 1e-6


@dataclass
class Dataset:
    name: str
    tables: dict[str, list[dict[str, Any]]]
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ construction
    @classmethod
    def from_rows(
        cls, name: str, tables: dict[str, list[dict[str, Any]]], metadata: dict[str, Any] | None = None
    ) -> tuple["Dataset | None", ValidationReport]:
        """Build from rows keyed by schema column names (for generated data and notebooks)."""
        return cls._build(name, {t: (None, rows) for t, rows in tables.items()}, metadata)

    @classmethod
    def from_csv_texts(
        cls, name: str, texts: dict[str, str], metadata: dict[str, Any] | None = None
    ) -> tuple["Dataset | None", ValidationReport]:
        """Build from CSV text per table (for imports). Columns are matched by header."""
        raw: dict[str, tuple[list[str] | None, list[dict[str, Any]]]] = {}
        report = ValidationReport()
        for table, text in texts.items():
            if text is None:
                continue
            text = text.lstrip("﻿")  # tolerate a UTF-8 byte-order mark (common from spreadsheet tools)
            reader = csv.DictReader(io.StringIO(text))
            header = list(reader.fieldnames or [])
            raw[table] = (header, list(reader))
        dataset, rep = cls._build(name, raw, metadata)
        report.extend(rep)
        return dataset, report

    @classmethod
    def _build(cls, name, raw, metadata):
        report = ValidationReport()
        if not (name or "").strip():
            report.error("missing_name", "dataset name is required")
        for table in raw:
            if table not in SCHEMAS:
                report.warning("unknown_table", f"table '{table}' is not part of the schema and is ignored",
                               table=table, params={"table": table})
        for table in REQUIRED_TABLES:
            if table not in raw:
                report.error("missing_table", f"required table '{table}' is missing", table=table,
                             params={"table": table})
        parsed: dict[str, list[dict[str, Any]]] = {}
        for table in TABLE_ORDER:
            if table in raw:
                header, rows = raw[table]
                parsed[table] = parse_table(SCHEMAS[table], rows, header, report)
            else:
                parsed[table] = []
        if report.errors:
            return None, report
        dataset = cls(name=name.strip(), tables=parsed, metadata=dict(metadata or {}))
        report.extend(dataset.validate())
        if report.errors:
            return None, report
        return dataset, report

    # ------------------------------------------------------------------ validation
    def validate(self) -> ValidationReport:
        """Cross-table checks. Never repairs data silently (plan s 2)."""
        r = ValidationReport()
        t = self.tables

        for table in TABLE_ORDER:
            schema = SCHEMAS[table]
            seen: dict[tuple, int] = {}
            for n, row in enumerate(t[table], start=1):
                key = tuple(row.get(k) for k in schema.primary_key)
                if key in seen:
                    r.error("duplicate_key", f"duplicate key {key} (first at row {seen[key]})", table=table,
                            row=n, params={"key": "/".join(map(str, key)), "first_row": seen[key]})
                else:
                    seen[key] = n

        sources = {s["source_id"]: s for s in t["sources"]}
        jurisdictions = {j["jurisdiction_id"]: j for j in t["jurisdictions"]}
        entities = {e["entity_id"]: e for e in t["entities"]}

        def check_source(table: str, n: int, sid: str | None) -> None:
            if sid is not None and sid not in sources:
                r.error("unknown_source", f"source '{sid}' is not in the sources table", table=table, row=n,
                        column="source_id", params={"source_id": sid})

        def is_synthetic_source(sid: str | None) -> bool:
            return sid in sources and sources[sid]["licence_class"] == "synthetic"

        # jurisdictions
        for n, j in enumerate(t["jurisdictions"], start=1):
            jid = j["jurisdiction_id"]
            if j["fictional"]:
                if not jid.startswith(FICTIONAL_PREFIX):
                    r.error("fictional_prefix", f"fictional jurisdiction '{jid}' must use the {FICTIONAL_PREFIX} prefix",
                            table="jurisdictions", row=n, params={"id": jid})
                if j.get("iso3"):
                    r.error("fictional_iso3", f"fictional jurisdiction '{jid}' must not carry an ISO code",
                            table="jurisdictions", row=n, params={"id": jid})
            else:
                if jid.startswith(FICTIONAL_PREFIX):
                    r.error("real_with_fictional_prefix", f"'{jid}' uses the reserved {FICTIONAL_PREFIX} prefix but is not marked fictional",
                            table="jurisdictions", row=n, params={"id": jid})
                elif not ISO3_RE.match(jid):
                    r.error("bad_iso3", f"real jurisdiction id '{jid}' must be an ISO 3166-1 alpha-3 code",
                            table="jurisdictions", row=n, params={"id": jid})
                if j.get("iso3") and j["iso3"] != jid:
                    r.error("iso3_mismatch", f"iso3 '{j['iso3']}' differs from id '{jid}'", table="jurisdictions",
                            row=n, params={"id": jid, "iso3": j["iso3"]})
            parent = j.get("parent_jurisdiction_id")
            if parent is not None and parent not in jurisdictions:
                r.error("unknown_jurisdiction", f"parent '{parent}' is not a known jurisdiction",
                        table="jurisdictions", row=n, column="parent_jurisdiction_id", params={"id": parent})
            if parent == jid:
                r.error("self_parent", f"'{jid}' cannot be its own parent", table="jurisdictions", row=n,
                        params={"id": jid})

        # attributes
        for n, a in enumerate(t["jurisdiction_attributes"], start=1):
            if a["jurisdiction_id"] not in jurisdictions:
                r.error("unknown_jurisdiction", f"jurisdiction '{a['jurisdiction_id']}' is not known",
                        table="jurisdiction_attributes", row=n, params={"id": a["jurisdiction_id"]})
            if a.get("currency") and not CURRENCY_RE.match(a["currency"]):
                r.error("bad_currency", f"currency '{a['currency']}' must be an ISO 4217 code",
                        table="jurisdiction_attributes", row=n, params={"currency": a["currency"]})
            check_source("jurisdiction_attributes", n, a["source_id"])

        # entities
        for n, e in enumerate(t["entities"], start=1):
            jid = e["jurisdiction_id"]
            if jid not in jurisdictions:
                r.error("unknown_jurisdiction", f"jurisdiction '{jid}' is not known", table="entities", row=n,
                        params={"id": jid})
            elif not jurisdictions[jid]["fictional"] and is_synthetic_source(e["source_id"]):
                r.error("synthetic_on_real_jurisdiction",
                        f"synthetic record attributed to real jurisdiction '{jid}'", table="entities", row=n,
                        params={"id": jid})
            if e["is_natural_person"]:
                r.error("natural_person", "natural persons must be excluded or pseudonymised before import",
                        table="entities", row=n, params={"id": e["entity_id"]})
            if e.get("valid_from") and e.get("valid_to") and e["valid_to"] < e["valid_from"]:
                r.error("bad_period", "valid_to is earlier than valid_from", table="entities", row=n, params={})
            check_source("entities", n, e["source_id"])

        # ownership
        parallel: dict[tuple, list[int]] = defaultdict(list)
        equity_current: dict[tuple, float] = defaultdict(float)
        for n, o in enumerate(t["ownership"], start=1):
            for col in ("holder_id", "held_id"):
                if o[col] not in entities:
                    r.error("unknown_entity", f"{col} '{o[col]}' is not in the entities table", table="ownership",
                            row=n, column=col, params={"id": o[col]})
            if not o["direct"]:
                r.error("indirect_stored", "only direct relations are stored; indirect holdings are derived",
                        table="ownership", row=n, params={})
            if o["holder_id"] == o["held_id"]:
                r.warning("self_holding", f"'{o['holder_id']}' holds itself (treasury shares?)", table="ownership",
                          row=n, params={"id": o["holder_id"]})
            if o.get("value_amount") is not None and not o.get("value_currency"):
                r.error("amount_without_currency", "value_amount requires value_currency", table="ownership",
                        row=n, params={})
            if o.get("value_currency") and not CURRENCY_RE.match(o["value_currency"]):
                r.error("bad_currency", f"currency '{o['value_currency']}' must be an ISO 4217 code",
                        table="ownership", row=n, params={"currency": o["value_currency"]})
            if o.get("fraction") is None:
                r.warning("fraction_missing", "fraction not reported; it is never imputed", table="ownership", row=n,
                          params={})
            if o.get("valid_to") and o["valid_to"] < o["valid_from"]:
                r.error("bad_period", "valid_to is earlier than valid_from", table="ownership", row=n, params={})
            check_source("ownership", n, o["source_id"])
            parallel[(o["holder_id"], o["held_id"], o["relation_type"])].append(n)
            if o["relation_type"] == "equity" and o.get("valid_to") is None and o.get("fraction") is not None:
                equity_current[(o["held_id"], o.get("share_class") or "")] += o["fraction"]
        for (holder, held, rtype), rows in parallel.items():
            if len(rows) > 1:
                r.warning("parallel_relation",
                          f"{len(rows)} '{rtype}' relations from '{holder}' to '{held}' (rows {rows}); kept distinct",
                          table="ownership", params={"holder": holder, "held": held, "count": len(rows)})
        for (held, share_class), total in equity_current.items():
            if total > 1 + EQUITY_TOLERANCE:
                r.warning("equity_over_one",
                          f"current equity fractions in '{held}'{(' class ' + share_class) if share_class else ''} sum to {total:.4f}",
                          table="ownership", params={"id": held, "total": round(total, 6)})
        cycle = _find_cycle(t["ownership"])
        if cycle:
            r.warning("ownership_cycle", "ownership cycle (cross-holding): " + " -> ".join(cycle), table="ownership",
                      params={"cycle": " -> ".join(cycle)})

        # illustrative tax edges
        for n, e in enumerate(t["illustrative_tax_edges"], start=1):
            for col in ("source_jurisdiction", "target_jurisdiction"):
                jid = e[col]
                if jid not in jurisdictions:
                    r.error("unknown_jurisdiction", f"{col} '{jid}' is not known", table="illustrative_tax_edges",
                            row=n, column=col, params={"id": jid})
                elif not jurisdictions[jid]["fictional"] and e["rule_status"] == "synthetic_assumption":
                    r.error("synthetic_on_real_jurisdiction",
                            f"synthetic tax assumption attributed to real jurisdiction '{jid}'",
                            table="illustrative_tax_edges", row=n, params={"id": jid})
            check_source("illustrative_tax_edges", n, e["source_id"])

        # tax rules (van 't Riet and Lejour reproduction tables)
        def check_rule_row(table: str, n: int, row: dict[str, Any], cols: tuple[str, ...]) -> None:
            for col in cols:
                jid = row[col]
                if jid not in jurisdictions:
                    r.error("unknown_jurisdiction", f"{col} '{jid}' is not known", table=table, row=n, column=col,
                            params={"id": jid})
                elif not jurisdictions[jid]["fictional"] and row["rule_status"] == "synthetic_assumption":
                    r.error("synthetic_on_real_jurisdiction",
                            f"synthetic tax assumption attributed to real jurisdiction '{jid}'", table=table, row=n,
                            params={"id": jid})
            if len(cols) == 2 and row[cols[0]] == row[cols[1]]:
                r.error("same_jurisdiction_pair", f"{cols[0]} and {cols[1]} are the same", table=table, row=n,
                        params={"id": row[cols[0]]})
            check_source(table, n, row["source_id"])
            if not row["verified"] and not is_synthetic_source(row["source_id"]):
                r.warning("unverified_legal_row", "legal row not yet verified; results relying on it are flagged",
                          table=table, row=n, params={})

        for n, row in enumerate(t["tax_domestic"], start=1):
            check_rule_row("tax_domestic", n, row, ("jurisdiction_id",))
        for n, row in enumerate(t["tax_treaty_dividends"], start=1):
            check_rule_row("tax_treaty_dividends", n, row, ("payer_jurisdiction", "recipient_jurisdiction"))
        for n, row in enumerate(t["tax_relief_overrides"], start=1):
            check_rule_row("tax_relief_overrides", n, row, ("relieving_jurisdiction", "taxing_jurisdiction"))

        if not t["entities"]:
            r.warning("empty_table", "no entities", table="entities", params={"table": "entities"})
        status = self.data_status
        if status == "mixed":
            r.warning("mixed_sources", "dataset mixes synthetic and non-synthetic sources", params={})
        return r

    # ------------------------------------------------------------------ properties
    @property
    def data_status(self) -> str:
        """``synthetic``, ``real`` or ``mixed``, derived from the sources table (never from the name)."""
        classes = {s["licence_class"] for s in self.tables["sources"]}
        if not classes:
            return "unknown"
        if classes == {"synthetic"}:
            return "synthetic" if all(j["fictional"] for j in self.tables["jurisdictions"]) else "mixed"
        if "synthetic" in classes:
            return "mixed"
        return "real"

    def csv_text(self, table: str) -> str:
        schema = SCHEMAS[table]
        return canonical_csv(self.tables[table], schema.column_names, schema.primary_key)

    def table_hashes(self) -> dict[str, str]:
        """Hashes of the tables that make up the content address. Tables introduced after schema
        generation 1 are included only when non-empty, so existing dataset ids never change."""
        return {table: sha256_text(self.csv_text(table)) for table in TABLE_ORDER
                if SCHEMAS[table].added_in == 1 or self.tables[table]}

    @property
    def content_hash(self) -> str:
        return combine_hashes(self.table_hashes())

    @property
    def dataset_id(self) -> str:
        """Content address. The same content always has the same id, whatever its name."""
        return self.content_hash[:16]

    def counts(self) -> dict[str, int]:
        return {table: len(self.tables[table]) for table in TABLE_ORDER}

    def describe(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "content_hash": self.content_hash,
            "name": self.name,
            "data_status": self.data_status,
            "counts": self.counts(),
            "table_hashes": self.table_hashes(),
            "metadata": self.metadata,
        }

    # ------------------------------------------------------------------ storage
    def save(self, directory: Path) -> Path:
        """Write to ``directory/<dataset_id>``. Writing is atomic; an existing identical dataset is reused."""
        target = directory / self.dataset_id
        if (target / "dataset.json").exists():
            return target
        tmp = directory / f".tmp-{self.dataset_id}-{os.getpid()}"
        tmp.mkdir(parents=True, exist_ok=True)
        for table in TABLE_ORDER:
            (tmp / f"{table}.csv").write_text(self.csv_text(table), encoding="utf-8", newline="")
        meta = {"storage_schema_version": STORAGE_SCHEMA_VERSION, **self.describe()}
        (tmp / "dataset.json").write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
        try:
            os.replace(tmp, target)
        except OSError:
            if (target / "dataset.json").exists():  # another process saved the same content
                _rmtree(tmp)
            else:
                raise
        return target

    @classmethod
    def load(cls, path: Path) -> "Dataset":
        meta = json.loads((path / "dataset.json").read_text(encoding="utf-8"))
        texts = {}
        for table in TABLE_ORDER:
            f = path / f"{table}.csv"
            if f.exists():
                texts[table] = f.read_text(encoding="utf-8")
        dataset, report = cls.from_csv_texts(meta["name"], texts, meta.get("metadata"))
        if dataset is None:
            raise ValidationError(report, f"stored dataset {path.name} no longer validates")
        if dataset.content_hash != meta["content_hash"]:
            raise ValueError(f"stored dataset {path.name} has been modified: hash mismatch")
        return dataset


def _find_cycle(relations: list[dict[str, Any]]) -> list[str] | None:
    graph: dict[str, list[str]] = defaultdict(list)
    for o in relations:
        if o["holder_id"] != o["held_id"]:
            graph[o["holder_id"]].append(o["held_id"])
    white, grey, black = 0, 1, 2
    colour: dict[str, int] = defaultdict(int)
    for start in sorted(graph):
        if colour[start] != white:
            continue
        stack = [(start, iter(sorted(graph[start])))]
        path = [start]
        colour[start] = grey
        while stack:
            node, children = stack[-1]
            nxt = next(children, None)
            if nxt is None:
                colour[node] = black
                stack.pop()
                path.pop()
            elif colour[nxt] == grey:
                return path[path.index(nxt):] + [nxt]
            elif colour[nxt] == white:
                colour[nxt] = grey
                stack.append((nxt, iter(sorted(graph[nxt]))))
                path.append(nxt)
    return None


def _rmtree(path: Path) -> None:
    for child in path.iterdir():
        if child.is_dir():
            _rmtree(child)
        else:
            child.unlink()
    path.rmdir()
