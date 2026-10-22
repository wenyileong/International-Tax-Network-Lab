"""Legal coding templates and data dictionary (plan v2.4, s 5.4).

Two templates, each a ZIP of CSV files (one per table, columns located by header) with a data dictionary
and a read-me:

* the **illustrative template**: fictional jurisdictions only, every row filled, valid as it stands;
* the **real-sample template**: the candidate jurisdictions the researcher names, with every legal field
  blank and ``verified`` set to false. It does not load until the legal fields have been coded.

Every column of the legal tables is assigned to one of the three coding layers adopted from the JAF Rule
Bench (liability, collection, observation), or to the key or provenance columns that every legal row carries.
The observation layer is not used by the corporate-dividend methods; it is named so that the shared schema
can carry it later.
"""

from __future__ import annotations

import csv
import io
import zipfile
from typing import Any

from taxnetlab import __version__
from taxnetlab.canonical import canonical_csv
from taxnetlab.fixtures import PERIOD, vtrl_fixture
from taxnetlab.schema import ISO3_RE, SCHEMAS
from taxnetlab.synthetic import SYNTHETIC_SOURCE

TEMPLATE_TABLES = ("sources", "jurisdictions", "jurisdiction_attributes", "entities", "ownership", "tax_domestic",
                   "tax_treaty_dividends", "tax_relief_overrides", "tax_treaty_conditions")
LEGAL_TABLES = ("tax_domestic", "tax_treaty_dividends", "tax_relief_overrides", "tax_treaty_conditions")
LAYERS = ("key", "liability", "collection", "observation", "provenance", "reference")
DEFAULT_CANDIDATES = ("NLD", "LUX", "IRL", "GBR", "USA", "DEU", "FRA", "CHE", "SGP", "HKG", "MYS", "CHN", "CYP", "MLT", "BEL")

# (table, column) -> (layer, description)
DICTIONARY: dict[tuple[str, str], tuple[str, str]] = {
    ("sources", "source_id"): ("key", "Identifier of the source, cited by every row that relies on it."),
    ("sources", "title"): ("reference", "Title of the source (statute, treaty, database, report)."),
    ("sources", "custodian"): ("reference", "Publisher or custodian of the source."),
    ("sources", "url"): ("reference", "Where the source can be consulted."),
    ("sources", "retrieval_date"): ("reference", "Date the source was consulted (YYYY-MM-DD)."),
    ("sources", "licence_class"): ("reference", "public, public_attribution, licensed_no_redistribution or synthetic."),
    ("sources", "licence_terms"): ("reference", "Licence or terms of use."),
    ("sources", "permitted_uses"): ("reference", "Uses the licence permits."),
    ("sources", "redistribution"): ("reference", "Whether and how the data may be redistributed."),
    ("sources", "coverage"): ("reference", "Jurisdictions and periods the source covers."),
    ("sources", "limitations"): ("reference", "Known limitations."),
    ("sources", "oscola_citation"): ("reference", "Full citation in OSCOLA form, for legal sources."),
    ("jurisdictions", "jurisdiction_id"): ("key", "ISO 3166-1 alpha-3 code for a real jurisdiction; FIC_ prefix for a fictional one."),
    ("jurisdictions", "display_name"): ("reference", "Name shown in the interface."),
    ("jurisdictions", "iso3"): ("reference", "ISO 3166-1 alpha-3 code (empty for fictional jurisdictions)."),
    ("jurisdictions", "fictional"): ("reference", "true for fictional jurisdictions; synthetic rules may only refer to these."),
    ("jurisdictions", "parent_jurisdiction_id"): ("reference", "Sovereign of a dependent territory, where relevant."),
    ("jurisdiction_attributes", "jurisdiction_id"): ("key", "Jurisdiction the attribute describes."),
    ("jurisdiction_attributes", "attribute"): ("key", "Attribute name; 'gdp' is used for weights."),
    ("jurisdiction_attributes", "period"): ("key", "Period of the value (for example 2025)."),
    ("jurisdiction_attributes", "value"): ("reference", "Value of the attribute."),
    ("jurisdiction_attributes", "unit"): ("reference", "Unit (for example million)."),
    ("jurisdiction_attributes", "currency"): ("reference", "ISO 4217 currency of a monetary value."),
    ("jurisdiction_attributes", "source_id"): ("provenance", "Source of the value."),
    ("tax_domestic", "jurisdiction_id"): ("key", "Jurisdiction whose domestic rules the row states."),
    ("tax_domestic", "period"): ("key", "Tax period in which the rules apply."),
    ("tax_domestic", "cit_rate"): ("liability", "Statutory corporate income tax rate, as a fraction (0.25 for 25%)."),
    ("tax_domestic", "dividend_wht_rate"): ("collection", "General (non-treaty) withholding rate on outbound dividends, as a fraction."),
    ("tax_domestic", "relief_method"): ("liability", "Relief for foreign dividends received: exemption, credit or deduction."),
    ("tax_domestic", "rule_status"): ("provenance", "source_backed, derived, or synthetic_assumption (fictional jurisdictions only)."),
    ("tax_domestic", "verified"): ("provenance", "true once checked against the source; unverified rows are flagged on every result."),
    ("tax_domestic", "source_id"): ("provenance", "Source of the row (sources table)."),
    ("tax_domestic", "note"): ("provenance", "Pinpoint, verifier and date, or other notes."),
    ("tax_treaty_dividends", "payer_jurisdiction"): ("key", "State of the paying company (the source state)."),
    ("tax_treaty_dividends", "recipient_jurisdiction"): ("key", "State of residence of the recipient."),
    ("tax_treaty_dividends", "period"): ("key", "Tax period in which the rate applies."),
    ("tax_treaty_dividends", "dividend_wht_rate"): ("collection", "Rate the payer state may levy under the treaty, as a fraction."),
    ("tax_treaty_dividends", "rule_status"): ("provenance", "As for tax_domestic."),
    ("tax_treaty_dividends", "verified"): ("provenance", "As for tax_domestic."),
    ("tax_treaty_dividends", "source_id"): ("provenance", "Treaty or other source."),
    ("tax_treaty_dividends", "note"): ("provenance", "Article and paragraph, verifier and date."),
    ("tax_relief_overrides", "relieving_jurisdiction"): ("key", "State of residence that grants relief."),
    ("tax_relief_overrides", "taxing_jurisdiction"): ("key", "State whose tax is relieved."),
    ("tax_relief_overrides", "period"): ("key", "Tax period."),
    ("tax_relief_overrides", "relief_method"): ("liability", "Relief method for this direction, where it differs from the general method."),
    ("tax_relief_overrides", "rule_status"): ("provenance", "As for tax_domestic."),
    ("tax_relief_overrides", "verified"): ("provenance", "As for tax_domestic."),
    ("tax_relief_overrides", "source_id"): ("provenance", "Treaty or domestic source."),
    ("tax_relief_overrides", "note"): ("provenance", "Legal basis (treaty, domestic unilateral, regional), pinpoint, verifier and date."),
    ("tax_treaty_conditions", "payer_jurisdiction"): ("key", "As for tax_treaty_dividends."),
    ("tax_treaty_conditions", "recipient_jurisdiction"): ("key", "As for tax_treaty_dividends."),
    ("tax_treaty_conditions", "period"): ("key", "As for tax_treaty_dividends."),
    ("tax_treaty_conditions", "condition"): ("liability", "min_holding, min_holding_days, subject_to_tax, beneficial_ownership, ppt or lob."),
    ("tax_treaty_conditions", "threshold"): ("liability", "Fraction for min_holding and subject_to_tax; days for min_holding_days; empty otherwise."),
    ("tax_treaty_conditions", "pinpoint"): ("provenance", "Article and paragraph of the condition."),
    ("tax_treaty_conditions", "rule_status"): ("provenance", "As for tax_domestic."),
    ("tax_treaty_conditions", "verified"): ("provenance", "As for tax_domestic."),
    ("tax_treaty_conditions", "source_id"): ("provenance", "Treaty, Multilateral Instrument or other source."),
    ("tax_treaty_conditions", "note"): ("provenance", "Verifier, date and notes."),
}
REFERENCE_TABLES = ("entities", "ownership")  # included header-only; described in the schema documentation

README = """International Tax Network Lab: legal coding template ({kind})
Software version {version}; generated by the software, not edited by hand.

Files
  data_dictionary.csv   every column: coding layer, type, whether required, allowed values and meaning
  <table>.csv           one file per table; columns are matched by their header, in any order

Rules (project plan s 5.4)
  * Rates and shares are fractions: 0.25 means 25 per cent.
  * Every legal row needs a source (sources.csv), a rule_status and verified = true or false.
    Unverified rows can be used, but every result that relies on them is flagged.
  * Synthetic assumptions may refer only to fictional (FIC_) jurisdictions.
  * Treaty rates and conditions are directional: payer (source state) to recipient.
  * Optional columns may be left out; missing required columns block the import.

{extra}
Import: Data page, "Import a coding template (ZIP)", or import the CSV files one by one.
"""


def data_dictionary_csv() -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["table", "column", "layer", "type", "required", "may_be_empty", "allowed_values", "minimum", "maximum",
                "description"])
    for table in TEMPLATE_TABLES:
        if table in REFERENCE_TABLES:
            continue
        for c in SCHEMAS[table].columns:
            layer, desc = DICTIONARY[(table, c.name)]
            w.writerow([table, c.name, layer, c.type, "yes" if c.required else "no", "yes" if c.nullable else "no",
                        " | ".join(c.choices or ()), "" if c.minimum is None else c.minimum,
                        "" if c.maximum is None else c.maximum, desc])
    return buf.getvalue()


def illustrative_tables() -> dict[str, list[dict[str, Any]]]:
    """Fictional jurisdictions only, every row filled (the tax routing fixture plus examples of a directional
    relief override and of each kind of treaty condition)."""
    base = vtrl_fixture()
    src = SYNTHETIC_SOURCE["source_id"]

    def cond(payer: str, recipient: str, condition: str, threshold: float | None, pin: str) -> dict[str, Any]:
        return {"payer_jurisdiction": payer, "recipient_jurisdiction": recipient, "period": PERIOD, "condition": condition,
                "threshold": threshold, "pinpoint": pin, "rule_status": "synthetic_assumption", "verified": False,
                "source_id": src, "note": "illustrative"}

    tables = {t: [dict(r) for r in base.tables[t]] for t in TEMPLATE_TABLES}
    tables["tax_relief_overrides"] = [{"relieving_jurisdiction": "FIC_P", "taxing_jurisdiction": "FIC_X", "period": PERIOD,
                                       "relief_method": "exemption", "rule_status": "synthetic_assumption", "verified": False,
                                       "source_id": src, "note": "illustrative: treaty exemption in one direction only"}]
    tables["tax_treaty_conditions"] = [
        cond("FIC_H", "FIC_C", "min_holding", 0.10, "art 10(2)(a)"),
        cond("FIC_H", "FIC_C", "beneficial_ownership", None, "art 10(2)"),
        cond("FIC_H", "FIC_C", "ppt", None, "art 29(9)"),
        cond("FIC_H", "FIC_X", "min_holding_days", 365.0, "art 10(2)(a)"),
        cond("FIC_X", "FIC_P", "subject_to_tax", 0.0, "art 22"),
        cond("FIC_X", "FIC_P", "lob", None, "art 28"),
    ]
    return tables


def real_sample_tables(candidates: list[str], period: str = PERIOD) -> dict[str, list[dict[str, Any]]]:
    """Candidate jurisdictions with every legal field blank and verified = false (plan s 5.4)."""
    codes = sorted({c.strip().upper() for c in candidates if c.strip()})
    bad = [c for c in codes if not ISO3_RE.match(c)]
    if bad or not codes:
        raise ValueError(f"candidate jurisdictions must be ISO 3166-1 alpha-3 codes; not valid: {bad or 'none given'}")
    return {
        "sources": [{"source_id": "SRC_01", "title": None, "licence_class": None}],
        "jurisdictions": [{"jurisdiction_id": c, "display_name": None, "iso3": c, "fictional": False,
                           "parent_jurisdiction_id": None} for c in codes],
        "jurisdiction_attributes": [{"jurisdiction_id": c, "attribute": "gdp", "period": period, "value": None,
                                     "unit": None, "currency": None, "source_id": None} for c in codes],
        "entities": [], "ownership": [],
        "tax_domestic": [{"jurisdiction_id": c, "period": period, "cit_rate": None, "dividend_wht_rate": None,
                          "relief_method": None, "rule_status": None, "verified": False, "source_id": None, "note": None}
                         for c in codes],
        "tax_treaty_dividends": [], "tax_relief_overrides": [], "tax_treaty_conditions": [],
    }


def tables_to_csv(tables: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    return {t: canonical_csv(tables.get(t, []), SCHEMAS[t].column_names, SCHEMAS[t].primary_key) for t in TEMPLATE_TABLES}


def template_zip(kind: str, candidates: list[str] | None = None) -> bytes:
    if kind == "illustrative":
        texts = tables_to_csv(illustrative_tables())
        extra = "This template uses fictional jurisdictions only and loads as it stands."
    elif kind == "real_sample":
        cands = list(candidates or DEFAULT_CANDIDATES)
        texts = tables_to_csv(real_sample_tables(cands))
        extra = ("This template lists the candidate jurisdictions with every legal field blank and verified = false.\n"
                 "It will not load until the blank required fields have been coded from the sources.\n"
                 "Add treaty rates, relief overrides and treaty conditions as rows; delete the GDP rows you do not need.")
    else:
        raise ValueError("template kind must be 'illustrative' or 'real_sample'")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in [("README.txt", README.format(kind=kind.replace("_", "-"), version=__version__, extra=extra)),
                           ("data_dictionary.csv", data_dictionary_csv()),
                           *((f"{t}.csv", texts[t]) for t in TEMPLATE_TABLES)]:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))  # fixed time: identical bytes on each build
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, text.encode("utf-8"))
    return buf.getvalue()


MAX_UNZIPPED = 64 * 1024 * 1024


def read_template_zip(data: bytes) -> dict[str, str]:
    """CSV text per table from a template ZIP. Only ``<table>.csv`` files (at any folder depth) are read;
    other files are ignored. Guarded against oversized archives."""
    texts: dict[str, str] = {}
    total = 0
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            name = info.filename.replace("\\", "/").rsplit("/", 1)[-1]
            if info.is_dir() or not name.lower().endswith(".csv"):
                continue
            table = name[:-4].lower()
            if table not in SCHEMAS:
                continue
            with z.open(info) as f:  # read with a cap: the size in the header is not trusted
                raw = f.read(MAX_UNZIPPED - total + 1)
            total += len(raw)
            if total > MAX_UNZIPPED:
                raise ValueError("the archive is too large once unpacked")
            texts[table] = raw.decode("utf-8-sig")
    if not texts:
        raise ValueError("no table CSV files found in the archive")
    return texts
