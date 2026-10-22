"""Hand-calculated fixtures for method engines. Every number is fictional.

``vtrl_fixture`` is the worked example of ``docs/specs/vtrl2018_tax_routing.md`` s 13; ``gb_fixture`` is the
worked example for ``docs/specs/gb2017_conduits_sinks.md``. The derivations are written out in
``tests/test_vtrl2018.py`` and ``tests/test_gb2017.py``.
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


# ---------------------------------------------------------------------- conduits and sinks
GB_GDP = {"FIC_A": 100.0, "FIC_B": 100.0, "FIC_N": 50.0, "FIC_L": 10.0}
# entity: (jurisdiction, operating revenue)
GB_ENTITIES = {"a1": ("FIC_A", 100.0), "a0": ("FIC_A", 0.0), "b1": ("FIC_B", 50.0), "b0": ("FIC_B", 0.0),
               "n1": ("FIC_N", 0.0), "l1": ("FIC_L", 0.0), "m1": ("FIC_L", 20.0)}
# (holder, held, fraction): n1 owns a1; l1 owns n1; a0 owns l1; l1 and b0 own b1; n1 owns m1
GB_OWNERSHIP = [("n1", "a1", 1.0), ("l1", "n1", 1.0), ("a0", "l1", 1.0), ("l1", "b1", 0.6), ("b0", "b1", 0.4),
                ("n1", "m1", 1.0)]


def gb_fixture(ownership: list[tuple[str, str, float]] | None = None) -> Dataset:
    src = SYNTHETIC_SOURCE["source_id"]
    jurisdictions = [{"jurisdiction_id": j, "display_name": f"Fixture {j[4:]}", "iso3": None, "fictional": True,
                      "parent_jurisdiction_id": None} for j in GB_GDP]
    attributes = [{"jurisdiction_id": j, "attribute": "gdp", "period": PERIOD, "value": v, "unit": "million",
                   "currency": "XTS", "source_id": src} for j, v in GB_GDP.items()]
    entities = [{"entity_id": e, "reported_name": f"Fixture {e}", "jurisdiction_id": j, "entity_type": "operating",
                 "entity_type_rule": "fixture", "is_natural_person": False, "valid_from": None, "valid_to": None,
                 "source_id": src} for e, (j, _) in GB_ENTITIES.items()]
    financials = [{"entity_id": e, "period": PERIOD, "operating_revenue": r, "currency": "XTS",
                   "consolidation": "unconsolidated", "source_id": src} for e, (_, r) in GB_ENTITIES.items()]
    links = GB_OWNERSHIP if ownership is None else ownership
    rels = [{"relation_id": f"R{k:03d}", "holder_id": h, "held_id": d, "relation_type": "equity", "share_class": None,
             "fraction": f, "value_amount": None, "value_currency": None, "valuation_basis": None, "direct": True,
             "valid_from": "2025-01-01", "valid_to": None, "source_id": src} for k, (h, d, f) in enumerate(links, 1)]
    tables = {"sources": [dict(SYNTHETIC_SOURCE)], "jurisdictions": jurisdictions,
              "jurisdiction_attributes": attributes, "entities": entities, "ownership": rels,
              "entity_financials": financials}
    dataset, report = Dataset.from_rows("Conduits and sinks fixture", tables, {"origin": "fixture"})
    if dataset is None:
        raise ValidationError(report, "fixture invalid")
    return dataset
