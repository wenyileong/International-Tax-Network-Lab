"""Hand-calculated fixtures for method engines. Every number is fictional.

``vtrl_fixture`` is the worked example of ``docs/specs/vtrl2018_tax_routing.md`` s 13. The derivations are
written out in ``tests/test_vtrl2018.py``.
"""

from __future__ import annotations

from typing import Any

from taxnetlab.datasets import Dataset
from taxnetlab.synthetic import SYNTHETIC_SOURCE
from taxnetlab.validation import ValidationError

PERIOD = "2025"

# jurisdiction: (CIT, general dividend WHT, relief method for foreign dividends, GDP)
VTRL_DOMESTIC = {
    "FIC_H": (0.30, 0.15, "exemption", 100.0),  # host-like
    "FIC_P": (0.35, 0.10, "credit", 400.0),     # parent-like, credit relief
    "FIC_C": (0.25, 0.00, "exemption", 50.0),   # conduit-like: no outbound WHT, exemption
    "FIC_X": (0.20, 0.10, "deduction", 200.0),  # deduction relief
}
# (payer, recipient): treaty dividend WHT
VTRL_TREATIES = {
    ("FIC_H", "FIC_C"): 0.05,
    ("FIC_H", "FIC_X"): 0.00,
    ("FIC_X", "FIC_P"): 0.05,
    ("FIC_P", "FIC_H"): 0.05,
}


def vtrl_fixture(extra_tables: dict[str, list[dict[str, Any]]] | None = None) -> Dataset:
    src = SYNTHETIC_SOURCE["source_id"]
    jurisdictions = [{"jurisdiction_id": j, "display_name": f"Fixture {j[4:]}", "iso3": None, "fictional": True,
                      "parent_jurisdiction_id": None} for j in VTRL_DOMESTIC]
    attributes = [{"jurisdiction_id": j, "attribute": "gdp", "period": PERIOD, "value": v[3], "unit": "million",
                   "currency": "XTS", "source_id": src} for j, v in VTRL_DOMESTIC.items()]
    domestic = [{"jurisdiction_id": j, "period": PERIOD, "cit_rate": v[0], "dividend_wht_rate": v[1],
                 "relief_method": v[2], "rule_status": "synthetic_assumption", "verified": False, "source_id": src,
                 "note": "fixture"} for j, v in VTRL_DOMESTIC.items()]
    treaties = [{"payer_jurisdiction": a, "recipient_jurisdiction": b, "period": PERIOD, "dividend_wht_rate": r,
                 "rule_status": "synthetic_assumption", "verified": False, "source_id": src, "note": "fixture"}
                for (a, b), r in VTRL_TREATIES.items()]
    tables = {"sources": [dict(SYNTHETIC_SOURCE)], "jurisdictions": jurisdictions,
              "jurisdiction_attributes": attributes, "entities": [], "ownership": [],
              "tax_domestic": domestic, "tax_treaty_dividends": treaties}
    for k, v in (extra_tables or {}).items():
        tables[k] = v
    dataset, report = Dataset.from_rows("Tax routing fixture", tables, {"origin": "fixture"})
    if dataset is None:
        raise ValidationError(report, "fixture invalid")
    return dataset
