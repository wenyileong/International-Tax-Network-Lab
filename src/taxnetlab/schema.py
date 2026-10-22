"""Table schemas and row parsing.

Conventions (project plan v2.1, s 5.1):

* shares, rates and percentages are fractions in [0, 1];
* money is an amount plus an ISO 4217 currency code (``XTS`` is the ISO code reserved for testing,
  used by synthetic data);
* real jurisdictions use ISO 3166-1 alpha-3 codes; fictional jurisdictions use the reserved ``FIC_``
  prefix;
* dates are ISO 8601 calendar dates (``YYYY-MM-DD``).

Columns are located by header (case-insensitive), never by position. Absent optional columns
default to empty with a notice; absent required columns block the import.
"""

from __future__ import annotations

import datetime as _dt
import math
import re
from dataclasses import dataclass
from typing import Any, Iterable

from taxnetlab.validation import ValidationReport

FICTIONAL_PREFIX = "FIC_"
ISO3_RE = re.compile(r"^[A-Z]{3}$")
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
ID_RE = re.compile(r"^[A-Za-z0-9_.:\-]{1,64}$")

RELATION_TYPES = ("equity", "voting", "control", "economic_interest")
LICENCE_CLASSES = ("public", "public_attribution", "licensed_no_redistribution", "synthetic")
RULE_STATUSES = ("source_backed", "derived", "synthetic_assumption")
RELIEF_METHODS = ("exemption", "credit", "deduction")
CONSOLIDATION = ("unconsolidated", "deconsolidated", "consolidated")
#: Conditions on treaty benefits (plan s 5.2). Mechanical conditions are evaluated against scenario facts;
#: judgement-based or unmodelled conditions are ``indeterminate`` unless a scenario assumption resolves them.
MECHANICAL_CONDITIONS = ("min_holding", "min_holding_days", "subject_to_tax")
ASSUMPTION_CONDITIONS = ("beneficial_ownership", "ppt", "lob")
TREATY_CONDITIONS = MECHANICAL_CONDITIONS + ASSUMPTION_CONDITIONS
RATE_MAX = 0.9999  # a rate of 100% would make every later formula degenerate

STR, FLOAT, BOOL, DATE = "str", "float", "bool", "date"


@dataclass(frozen=True)
class Column:
    name: str
    type: str = STR
    required: bool = False  # column must be present
    nullable: bool = True   # value may be empty
    choices: tuple[str, ...] | None = None
    minimum: float | None = None
    maximum: float | None = None
    identifier: bool = False
    description: str = ""


@dataclass(frozen=True)
class TableSchema:
    name: str
    columns: tuple[Column, ...]
    primary_key: tuple[str, ...]
    description: str = ""
    #: Schema generation in which the table was introduced. Tables added after generation 1 enter the
    #: dataset hash only when they have rows, so that adding a table never changes existing dataset ids.
    added_in: int = 1

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def column(self, name: str) -> Column:
        for c in self.columns:
            if c.name == name:
                return c
        raise KeyError(name)


def _c(name: str, type: str = STR, *, req: bool = False, null: bool = True, **kw: Any) -> Column:
    return Column(name=name, type=type, required=req, nullable=null, **kw)


SCHEMAS: dict[str, TableSchema] = {
    "sources": TableSchema(
        "sources",
        (
            _c("source_id", req=True, null=False, identifier=True),
            _c("title", req=True, null=False),
            _c("custodian"),
            _c("url"),
            _c("retrieval_date", DATE),
            _c("licence_class", req=True, null=False, choices=LICENCE_CLASSES),
            _c("licence_terms"),
            _c("permitted_uses"),
            _c("redistribution"),
            _c("coverage"),
            _c("limitations"),
            _c("oscola_citation"),
        ),
        ("source_id",),
        "Source registry: where every record came from and on what terms.",
    ),
    "jurisdictions": TableSchema(
        "jurisdictions",
        (
            _c("jurisdiction_id", req=True, null=False, identifier=True),
            _c("display_name", req=True, null=False),
            _c("iso3"),
            _c("fictional", BOOL, req=True, null=False),
            _c("parent_jurisdiction_id", identifier=True),
        ),
        ("jurisdiction_id",),
        "Jurisdictions. Real: ISO 3166-1 alpha-3. Fictional: FIC_ prefix.",
    ),
    "jurisdiction_attributes": TableSchema(
        "jurisdiction_attributes",
        (
            _c("jurisdiction_id", req=True, null=False, identifier=True),
            _c("attribute", req=True, null=False),
            _c("period", req=True, null=False),
            _c("value", FLOAT, req=True, null=False),
            _c("unit", req=True, null=False),
            _c("currency"),
            _c("source_id", req=True, null=False, identifier=True),
        ),
        ("jurisdiction_id", "attribute", "period"),
        "Time series of contextual values such as GDP.",
    ),
    "entities": TableSchema(
        "entities",
        (
            _c("entity_id", req=True, null=False, identifier=True),
            _c("reported_name", req=True, null=False),
            _c("jurisdiction_id", req=True, null=False, identifier=True),
            _c("entity_type", req=True, null=False),
            _c("entity_type_rule"),
            _c("is_natural_person", BOOL, req=True, null=False),
            _c("valid_from", DATE),
            _c("valid_to", DATE),
            _c("source_id", req=True, null=False, identifier=True),
        ),
        ("entity_id",),
        "Legal entities. Natural persons must be excluded or pseudonymised before import.",
    ),
    "ownership": TableSchema(
        "ownership",
        (
            _c("relation_id", req=True, null=False, identifier=True),
            _c("holder_id", req=True, null=False, identifier=True),
            _c("held_id", req=True, null=False, identifier=True),
            _c("relation_type", req=True, null=False, choices=RELATION_TYPES),
            _c("share_class"),
            _c("fraction", FLOAT, minimum=0.0, maximum=1.0),
            _c("value_amount", FLOAT, minimum=0.0),
            _c("value_currency"),
            _c("valuation_basis"),
            _c("direct", BOOL, req=True, null=False),
            _c("valid_from", DATE, req=True, null=False),
            _c("valid_to", DATE),
            _c("source_id", req=True, null=False, identifier=True),
        ),
        ("relation_id",),
        "Direct relations stored holder -> held. Indirect holdings are derived, never stored.",
    ),
    "illustrative_tax_edges": TableSchema(
        "illustrative_tax_edges",
        (
            _c("edge_id", req=True, null=False, identifier=True),
            _c("source_jurisdiction", req=True, null=False, identifier=True),
            _c("target_jurisdiction", req=True, null=False, identifier=True),
            _c("income_type", req=True, null=False),
            _c("illustrative_rate", FLOAT, req=True, null=False, minimum=0.0, maximum=1.0),
            _c("rule_status", req=True, null=False, choices=RULE_STATUSES),
            _c("source_id", req=True, null=False, identifier=True),
        ),
        ("edge_id",),
        "Interface-only scalar rates. Not a representation of tax law (plan s 5.2).",
    ),
    "tax_domestic": TableSchema(
        "tax_domestic",
        (
            _c("jurisdiction_id", req=True, null=False, identifier=True),
            _c("period", req=True, null=False),
            _c("cit_rate", FLOAT, req=True, null=False, minimum=0.0, maximum=RATE_MAX),
            _c("dividend_wht_rate", FLOAT, req=True, null=False, minimum=0.0, maximum=RATE_MAX),
            _c("relief_method", req=True, null=False, choices=RELIEF_METHODS),
            _c("rule_status", req=True, null=False, choices=RULE_STATUSES),
            _c("verified", BOOL, req=True, null=False),
            _c("source_id", req=True, null=False, identifier=True),
            _c("note"),
        ),
        ("jurisdiction_id", "period"),
        "Statutory corporate income tax, general dividend withholding rate and the relief method the "
        "jurisdiction applies to foreign dividends (van 't Riet and Lejour, s 4).",
        added_in=2,
    ),
    "tax_treaty_dividends": TableSchema(
        "tax_treaty_dividends",
        (
            _c("payer_jurisdiction", req=True, null=False, identifier=True),
            _c("recipient_jurisdiction", req=True, null=False, identifier=True),
            _c("period", req=True, null=False),
            _c("dividend_wht_rate", FLOAT, req=True, null=False, minimum=0.0, maximum=RATE_MAX),
            _c("rule_status", req=True, null=False, choices=RULE_STATUSES),
            _c("verified", BOOL, req=True, null=False),
            _c("source_id", req=True, null=False, identifier=True),
            _c("note"),
        ),
        ("payer_jurisdiction", "recipient_jurisdiction", "period"),
        "Directional treaty withholding: the rate the payer jurisdiction may levy on dividends to the recipient.",
        added_in=2,
    ),
    "tax_relief_overrides": TableSchema(
        "tax_relief_overrides",
        (
            _c("relieving_jurisdiction", req=True, null=False, identifier=True),
            _c("taxing_jurisdiction", req=True, null=False, identifier=True),
            _c("period", req=True, null=False),
            _c("relief_method", req=True, null=False, choices=RELIEF_METHODS),
            _c("rule_status", req=True, null=False, choices=RULE_STATUSES),
            _c("verified", BOOL, req=True, null=False),
            _c("source_id", req=True, null=False, identifier=True),
            _c("note"),
        ),
        ("relieving_jurisdiction", "taxing_jurisdiction", "period"),
        "Directional relief: the method the relieving (receiving) jurisdiction applies to dividends from the "
        "taxing jurisdiction, where it differs from its general method (plan s 5.2).",
        added_in=2,
    ),
    "tax_treaty_conditions": TableSchema(
        "tax_treaty_conditions",
        (
            _c("payer_jurisdiction", req=True, null=False, identifier=True),
            _c("recipient_jurisdiction", req=True, null=False, identifier=True),
            _c("period", req=True, null=False),
            _c("condition", req=True, null=False, choices=TREATY_CONDITIONS),
            _c("threshold", FLOAT, minimum=0.0),
            _c("pinpoint"),
            _c("rule_status", req=True, null=False, choices=RULE_STATUSES),
            _c("verified", BOOL, req=True, null=False),
            _c("source_id", req=True, null=False, identifier=True),
            _c("note"),
        ),
        ("payer_jurisdiction", "recipient_jurisdiction", "period", "condition"),
        "Conditions on the treaty rate in tax_treaty_dividends: minimum holding (fraction), minimum holding period "
        "(days), subject-to-tax (recipient rate above the threshold), and the beneficial ownership, principal purpose "
        "and limitation-on-benefits tests, which stay indeterminate unless a scenario assumption resolves them.",
        added_in=2,
    ),
    "entity_financials": TableSchema(
        "entity_financials",
        (
            _c("entity_id", req=True, null=False, identifier=True),
            _c("period", req=True, null=False),
            _c("operating_revenue", FLOAT, req=True, null=False, minimum=0.0),
            _c("currency", req=True, null=False),
            _c("consolidation", req=True, null=False, choices=CONSOLIDATION),
            _c("source_id", req=True, null=False, identifier=True),
        ),
        ("entity_id", "period"),
        "Operating revenue per entity and period (Garcia-Bernardo and others weight chains by the revenue of "
        "the owned firm). Consolidated figures should be deconsolidated before use.",
        added_in=2,
    ),
}

#: Tables in dependency order (referenced tables first).
TABLE_ORDER = ("sources", "jurisdictions", "jurisdiction_attributes", "entities", "ownership", "illustrative_tax_edges",
               "tax_domestic", "tax_treaty_dividends", "tax_relief_overrides", "entity_financials",
               "tax_treaty_conditions")
TAX_TABLES = ("tax_domestic", "tax_treaty_dividends", "tax_relief_overrides", "tax_treaty_conditions")
REQUIRED_TABLES = ("sources", "jurisdictions", "entities", "ownership")

_TRUE = {"true", "1", "yes", "y", "t"}
_FALSE = {"false", "0", "no", "n", "f"}


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return isinstance(value, str) and value.strip() == ""


def parse_value(col: Column, raw: Any) -> tuple[Any, str | None]:
    """Parse one cell. Returns (value, error_code)."""
    if _is_empty(raw):
        return None, None
    if col.type == STR:
        value = str(raw).strip()
        if col.identifier and not ID_RE.match(value):
            return value, "bad_identifier"
        if col.choices and value not in col.choices:
            return value, "bad_choice"
        return value, None
    if col.type == BOOL:
        if isinstance(raw, bool):
            return raw, None
        text = str(raw).strip().lower()
        if text in _TRUE:
            return True, None
        if text in _FALSE:
            return False, None
        return raw, "bad_bool"
    if col.type == FLOAT:
        if isinstance(raw, bool):
            return raw, "bad_number"
        try:
            value = float(str(raw).strip()) if not isinstance(raw, (int, float)) else float(raw)
        except ValueError:
            return raw, "bad_number"
        if math.isnan(value) or math.isinf(value):
            return raw, "bad_number"
        if col.minimum is not None and value < col.minimum:
            return value, "out_of_range"
        if col.maximum is not None and value > col.maximum:
            return value, "out_of_range"
        return value, None
    if col.type == DATE:
        if isinstance(raw, _dt.date):
            return raw.isoformat(), None
        text = str(raw).strip()
        try:
            return _dt.date.fromisoformat(text).isoformat(), None
        except ValueError:
            return text, "bad_date"
    raise ValueError(f"unknown column type {col.type}")


_CELL_MESSAGES = {
    "bad_identifier": "identifier must be 1 to 64 characters: letters, digits, _ . : -",
    "bad_choice": "value is not one of the permitted choices",
    "bad_bool": "expected true or false",
    "bad_number": "expected a finite number",
    "out_of_range": "number outside the permitted range",
    "bad_date": "expected an ISO date (YYYY-MM-DD)",
}


def parse_table(
    schema: TableSchema, rows: Iterable[dict[str, Any]], header: list[str] | None, report: ValidationReport
) -> list[dict[str, Any]]:
    """Parse and type-check one table. Structural problems are added to ``report``.

    ``header`` is the list of incoming column names (for CSV input) or ``None`` when the rows are
    already keyed by schema column names (for generated data).
    """
    rows = list(rows)
    mapping: dict[str, str] = {}  # schema column -> incoming key
    if header is None:
        present = set().union(*(r.keys() for r in rows)) if rows else set(schema.column_names)
        header = list(present)
    lookup = {}
    for h in header:
        key = (h or "").strip().lower()
        if key in lookup:
            report.error("duplicate_column", f"column '{h}' appears more than once", table=schema.name,
                         column=h, params={"column": h})
        lookup[key] = h
    for col in schema.columns:
        if col.name.lower() in lookup:
            mapping[col.name] = lookup[col.name.lower()]
        elif col.required:
            report.error("missing_column", f"required column '{col.name}' is missing", table=schema.name,
                         column=col.name, params={"column": col.name})
        else:
            report.info("optional_column_absent", f"optional column '{col.name}' is absent; left empty",
                        table=schema.name, column=col.name, params={"column": col.name})
    known = {c.name.lower() for c in schema.columns}
    for key, original in lookup.items():
        if key not in known:
            report.warning("extra_column_ignored", f"column '{original}' is not in the schema and is ignored",
                           table=schema.name, column=original, params={"column": original})
    if any(i.code in ("missing_column", "duplicate_column") and i.table == schema.name for i in report.errors):
        return []

    parsed: list[dict[str, Any]] = []
    for n, raw_row in enumerate(rows, start=1):
        out: dict[str, Any] = {}
        for col in schema.columns:
            raw = raw_row.get(mapping[col.name]) if col.name in mapping else None
            value, err = parse_value(col, raw)
            if err:
                report.error(err, f"{col.name}: {_CELL_MESSAGES[err]} (got {raw!r})", table=schema.name, row=n,
                             column=col.name, params={"column": col.name, "value": str(raw)})
            elif value is None and not col.nullable:
                report.error("missing_value", f"{col.name}: value required", table=schema.name, row=n,
                             column=col.name, params={"column": col.name})
            out[col.name] = value
        parsed.append(out)
    return parsed
