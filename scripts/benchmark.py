"""Reference benchmarks (plan s 11, performance and scale). Prints timings for stated reference sizes.

    python scripts/benchmark.py            # all
The budgets checked in tests/test_performance.py are deliberately generous for CI machines; this script
reports the actual figures for the release notes.
"""

from __future__ import annotations

import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from taxnetlab.datasets import Dataset  # noqa: E402
from taxnetlab.engines import get_engine  # noqa: E402
from taxnetlab.synthetic import SYNTHETIC_SOURCE, generate  # noqa: E402


def tax_world(n: int, seed: int = 1, treaty_density: float = 0.4) -> Dataset:
    rng = random.Random(seed)
    src = SYNTHETIC_SOURCE["source_id"]
    codes = [f"FIC_{i:03d}" for i in range(n)]
    tables = {
        "sources": [dict(SYNTHETIC_SOURCE)],
        "jurisdictions": [{"jurisdiction_id": c, "display_name": c, "iso3": None, "fictional": True,
                           "parent_jurisdiction_id": None} for c in codes],
        "jurisdiction_attributes": [{"jurisdiction_id": c, "attribute": "gdp", "period": "2025", "value": rng.uniform(1, 1000),
                                     "unit": "m", "currency": "XTS", "source_id": src} for c in codes],
        "entities": [], "ownership": [],
        "tax_domestic": [{"jurisdiction_id": c, "period": "2025", "cit_rate": rng.choice([.1, .15, .2, .25, .3]),
                          "dividend_wht_rate": rng.choice([0, .05, .1, .15, .25]),
                          "relief_method": rng.choice(["exemption", "exemption", "credit", "deduction"]),
                          "rule_status": "synthetic_assumption", "verified": False, "source_id": src, "note": None} for c in codes],
        "tax_treaty_dividends": [{"payer_jurisdiction": a, "recipient_jurisdiction": b, "period": "2025",
                                  "dividend_wht_rate": rng.choice([0, 0, .05, .1]), "rule_status": "synthetic_assumption",
                                  "verified": False, "source_id": src, "note": None}
                                 for a in codes for b in codes if a != b and rng.random() < treaty_density],
    }
    ds, rep = Dataset.from_rows(f"benchmark {n}", tables)
    assert ds is not None, rep.format_text()
    return ds


def timed(engine_id: str, ds: Dataset, **params) -> tuple[float, str]:
    e = get_engine(engine_id)
    p, rep = e.resolve_parameters(params)
    rep.extend(e.validate(ds, p))
    assert rep.ok, rep.format_text()
    t = time.perf_counter()
    r = e.run(ds, p)
    return time.perf_counter() - t, r.outcome


CASES = [
    ("vtrl2018.tax_routing", "108 jurisdictions (the source's sample size)", lambda: tax_world(108), {}),
    ("gb2017.conduits_sinks", "26 jurisdictions, 1,600 entities", lambda: generate(seed=3, n_jurisdictions=26, n_groups=40, entities_per_group=40, cross_holdings=50), {}),
    ("ph.vietoris_rips", "routing cost, 108 jurisdictions", lambda: tax_world(108), {"input": "routing_cost", "influence": False}),
    ("compare.models", "20 jurisdictions", lambda: generate(seed=7, n_jurisdictions=20, n_groups=12), {}),
]



def ownership_world(n_entities: int, n_jur: int = 60, seed: int = 2) -> Dataset:
    """A random corporate forest: each firm has one to three owners chosen among earlier firms."""
    rng = random.Random(seed)
    src = SYNTHETIC_SOURCE["source_id"]
    codes = [f"FIC_{i:03d}" for i in range(n_jur)]
    ents = [{"entity_id": f"E{i:06d}", "reported_name": f"Firm {i}", "jurisdiction_id": rng.choice(codes),
             "entity_type": "operating", "entity_type_rule": None, "is_natural_person": False, "valid_from": None,
             "valid_to": None, "source_id": src} for i in range(n_entities)]
    own, k = [], 0
    for i in range(50, n_entities):
        owners = rng.sample(range(i), rng.choice([1, 1, 2, 3]))
        shares = [rng.random() for _ in owners]
        tot = sum(shares)
        for o, s in zip(owners, shares):
            k += 1
            own.append({"relation_id": f"R{k:07d}", "holder_id": f"E{o:06d}", "held_id": f"E{i:06d}", "relation_type": "equity",
                        "share_class": None, "fraction": round(s / tot, 4), "value_amount": None, "value_currency": None,
                        "valuation_basis": None, "direct": True, "valid_from": "2025-01-01", "valid_to": None, "source_id": src})
    tables = {"sources": [dict(SYNTHETIC_SOURCE)],
              "jurisdictions": [{"jurisdiction_id": c, "display_name": c, "iso3": None, "fictional": True,
                                 "parent_jurisdiction_id": None} for c in codes],
              "jurisdiction_attributes": [{"jurisdiction_id": c, "attribute": "gdp", "period": "2025", "value": rng.uniform(1, 1000),
                                           "unit": "m", "currency": "XTS", "source_id": src} for c in codes],
              "entities": ents, "ownership": own,
              "entity_financials": [{"entity_id": e["entity_id"], "period": "2025", "operating_revenue": rng.uniform(0, 100),
                                     "currency": "XTS", "consolidation": "unconsolidated", "source_id": src} for e in ents]}
    ds, rep = Dataset.from_rows(f"ownership {n_entities}", tables)
    assert ds is not None, rep.format_text()
    return ds


CASES.append(("gb2017.conduits_sinks", "60 jurisdictions, 50,000 entities", lambda: ownership_world(50_000), {}))


if __name__ == "__main__":
    for engine_id, label, make, params in CASES:
        secs, outcome = timed(engine_id, make(), **params)
        print(f"{engine_id:24} {label:45} {secs:7.2f} s  {outcome}")
