"""Synthetic data. Every record is fictional and labelled as such.

* :func:`generate` builds a seeded random world. The seed changes the data, and the same seed
  and parameters always produce the same dataset (and therefore the same dataset id).
* :func:`build_0_1_fixture` is the fixed toy network of Build 0.1, converted to the 0.2 schema
  (fractions instead of percentages). It is kept as a regression fixture.

Amounts use ISO 4217 code ``XTS``, reserved for testing. Names are invented; jurisdictions use
the ``FIC_`` prefix and never correspond to real states.
"""

from __future__ import annotations

import random
import string
from typing import Any

from taxnetlab.datasets import Dataset
from taxnetlab.validation import ValidationError

SYNTHETIC_SOURCE = {
    "source_id": "SYN_GENERATOR",
    "title": "International Tax Network Lab synthetic generator",
    "custodian": "International Tax Network Lab",
    "url": None,
    "retrieval_date": None,
    "licence_class": "synthetic",
    "licence_terms": "Generated data; no third-party rights.",
    "permitted_uses": "Software testing and demonstration only.",
    "redistribution": "Unrestricted.",
    "coverage": "Fictional world.",
    "limitations": "Fictional. Not evidence about any real jurisdiction, company or tax rule.",
    "oscola_citation": None,
}

ENTITY_TYPES = ("parent", "holding", "finance", "operating")
DEFAULT_PARAMS = {"seed": 17, "n_jurisdictions": 6, "n_groups": 4, "entities_per_group": 6, "cross_holdings": 2}
LIMITS = {"n_jurisdictions": (2, 26), "n_groups": (1, 40), "entities_per_group": (2, 40), "cross_holdings": (0, 50)}
OBSERVATION_DATE = "2025-12-31"


def _letters(n: int) -> list[str]:
    return list(string.ascii_uppercase[:n])


def generate(
    seed: int = 17,
    n_jurisdictions: int = 6,
    n_groups: int = 4,
    entities_per_group: int = 6,
    cross_holdings: int = 2,
    name: str | None = None,
) -> Dataset:
    params = {"seed": int(seed), "n_jurisdictions": int(n_jurisdictions), "n_groups": int(n_groups),
              "entities_per_group": int(entities_per_group), "cross_holdings": int(cross_holdings)}
    for key, (lo, hi) in LIMITS.items():
        if not lo <= params[key] <= hi:
            raise ValueError(f"{key} must be between {lo} and {hi}")
    rng = random.Random(params["seed"])
    codes = _letters(params["n_jurisdictions"])

    jurisdictions = [
        {"jurisdiction_id": f"FIC_{c}", "display_name": f"Fictional Jurisdiction {c}", "iso3": None,
         "fictional": True, "parent_jurisdiction_id": None}
        for c in codes
    ]
    # One "hub-like" jurisdiction is chosen so that worlds have visible structure to explore.
    hub = rng.choice(codes)
    attributes = [
        {"jurisdiction_id": f"FIC_{c}", "attribute": "gdp", "period": "2025",
         "value": float(rng.randrange(20, 900) * 1000), "unit": "million", "currency": "XTS",
         "source_id": SYNTHETIC_SOURCE["source_id"]}
        for c in codes
    ]

    entities: list[dict[str, Any]] = []
    ownership: list[dict[str, Any]] = []
    rel = 0

    def add_relation(holder: str, held: str, fraction: float, value: float, share_class: str | None = None) -> None:
        nonlocal rel
        rel += 1
        ownership.append({
            "relation_id": f"R{rel:05d}", "holder_id": holder, "held_id": held, "relation_type": "equity",
            "share_class": share_class, "fraction": round(fraction, 4), "value_amount": round(value, 2),
            "value_currency": "XTS", "valuation_basis": "book value (synthetic)", "direct": True,
            "valid_from": OBSERVATION_DATE, "valid_to": None, "source_id": SYNTHETIC_SOURCE["source_id"],
        })

    for g in range(1, params["n_groups"] + 1):
        home = rng.choice(codes)
        members: list[str] = []
        for k in range(params["entities_per_group"]):
            if k == 0:
                etype, jur = "parent", home
            else:
                etype = rng.choices(ENTITY_TYPES[1:], weights=(3, 2, 5))[0]
                if etype in ("holding", "finance") and rng.random() < 0.55:
                    jur = hub
                else:
                    jur = rng.choice(codes)
            eid = f"E{g:02d}{k:02d}"
            entities.append({
                "entity_id": eid, "reported_name": f"Example Group {g} {etype.title()} {k}",
                "jurisdiction_id": f"FIC_{jur}", "entity_type": etype,
                "entity_type_rule": "assigned by generator", "is_natural_person": False,
                "valid_from": None, "valid_to": None, "source_id": SYNTHETIC_SOURCE["source_id"],
            })
            if members:
                # Prefer holding companies as intermediate owners, producing chains.
                holders = [m for m in members if m != eid]
                weights = [3 if any(e["entity_id"] == m and e["entity_type"] == "holding" for e in entities) else 1
                           for m in holders]
                holder = rng.choices(holders, weights=weights)[0]
                fraction = rng.choice([1.0, 1.0, 0.9, 0.75, 0.6, 0.51])
                add_relation(holder, eid, fraction, rng.uniform(5, 250) * fraction)
                if fraction < 1.0 and rng.random() < 0.25:
                    # Minority stake held elsewhere in the group: exercises parallel ownership of one entity.
                    others = [m for m in holders if m != holder]
                    if others:
                        add_relation(rng.choice(others), eid, round(1.0 - fraction, 4), rng.uniform(1, 40))
            members.append(eid)

    # Cross-group minority holdings (portfolio-style links).
    ids = [e["entity_id"] for e in entities]
    for _ in range(params["cross_holdings"]):
        holder, held = rng.sample(ids, 2)
        if holder[:3] != held[:3]:
            add_relation(holder, held, rng.choice([0.05, 0.1, 0.15]), rng.uniform(1, 20), share_class="B")

    tax_edges = []
    edge = 0
    for c in codes:
        for d in codes:
            if c != d and rng.random() < 0.35:
                edge += 1
                tax_edges.append({
                    "edge_id": f"T{edge:04d}", "source_jurisdiction": f"FIC_{c}", "target_jurisdiction": f"FIC_{d}",
                    "income_type": "dividend", "illustrative_rate": rng.choice([0.0, 0.05, 0.1, 0.15]),
                    "rule_status": "synthetic_assumption", "source_id": SYNTHETIC_SOURCE["source_id"],
                })

    tables = {"sources": [dict(SYNTHETIC_SOURCE)], "jurisdictions": jurisdictions,
              "jurisdiction_attributes": attributes, "entities": entities, "ownership": ownership,
              "illustrative_tax_edges": tax_edges}
    label = name or f"Synthetic world (seed {params['seed']})"
    dataset, report = Dataset.from_rows(label, tables, {"origin": "synthetic_generator", "generator": params})
    if dataset is None:  # a generator bug, not a user error
        raise ValidationError(report, "synthetic generator produced an invalid dataset")
    return dataset


def build_0_1_fixture() -> Dataset:
    """The Build 0.1 toy network, with percentages converted to fractions (plan Appendix B, B9)."""
    j = ["A", "B", "C", "D", "E"]
    gdp = {"A": 500000, "B": 180000, "C": 90000, "D": 250000, "E": 120000}
    source = dict(SYNTHETIC_SOURCE, source_id="SYNTHETIC_001", title="Build 0.1 fixture")
    jurisdictions = [{"jurisdiction_id": f"FIC_{c}", "display_name": f"Illustrative Jurisdiction {c}", "iso3": None,
                      "fictional": True, "parent_jurisdiction_id": None} for c in j]
    attributes = [{"jurisdiction_id": f"FIC_{c}", "attribute": "gdp", "period": "2025", "value": float(gdp[c]),
                   "unit": "million", "currency": "XTS", "source_id": "SYNTHETIC_001"} for c in j]
    ents = [("CO_001", "Example Parent A", "A", "parent"), ("CO_002", "Example Holdings B", "B", "holding"),
            ("CO_003", "Example Finance C", "C", "finance"), ("CO_004", "Example Operating D", "D", "operating"),
            ("CO_005", "Example Subsidiary E", "E", "operating"), ("CO_006", "Example Local Op A", "A", "operating"),
            ("CO_007", "Example Intermediate D", "D", "holding")]
    entities = [{"entity_id": i, "reported_name": n, "jurisdiction_id": f"FIC_{c}", "entity_type": t,
                 "entity_type_rule": "Build 0.1 fixture", "is_natural_person": False, "valid_from": None,
                 "valid_to": None, "source_id": "SYNTHETIC_001"} for i, n, c, t in ents]
    links = [("CO_001", "CO_002", 0.80, 120.0), ("CO_002", "CO_003", 0.70, 85.0), ("CO_003", "CO_004", 0.60, 55.0),
             ("CO_001", "CO_007", 0.25, 40.0), ("CO_007", "CO_005", 0.51, 32.0), ("CO_001", "CO_006", 1.00, 65.0)]
    ownership = [{"relation_id": f"R{k:05d}", "holder_id": h, "held_id": d, "relation_type": "equity",
                  "share_class": None, "fraction": f, "value_amount": v, "value_currency": "XTS",
                  "valuation_basis": "capital value (illustrative)", "direct": True, "valid_from": "2025-12-31",
                  "valid_to": None, "source_id": "SYNTHETIC_001"} for k, (h, d, f, v) in enumerate(links, start=1)]
    tax = [("A", "B", 0.08), ("B", "C", 0.04), ("C", "D", 0.12), ("A", "D", 0.18), ("D", "E", 0.06), ("B", "E", 0.10)]
    tax_edges = [{"edge_id": f"T{k:04d}", "source_jurisdiction": f"FIC_{a}", "target_jurisdiction": f"FIC_{b}",
                  "income_type": "dividend", "illustrative_rate": r, "rule_status": "synthetic_assumption",
                  "source_id": "SYNTHETIC_001"} for k, (a, b, r) in enumerate(tax, start=1)]
    tables = {"sources": [source], "jurisdictions": jurisdictions, "jurisdiction_attributes": attributes,
              "entities": entities, "ownership": ownership, "illustrative_tax_edges": tax_edges}
    dataset, report = Dataset.from_rows("Build 0.1 fixture", tables, {"origin": "fixture"})
    if dataset is None:
        raise ValidationError(report, "fixture invalid")
    return dataset
