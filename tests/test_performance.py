"""Performance budgets (plan s 11). Generous, so that slow CI machines pass; scripts/benchmark.py reports
the actual figures. A budget failure means an algorithmic regression, not a slow machine."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import benchmark  # noqa: E402


def _budget(engine_id, ds, seconds, **params):
    secs, outcome = benchmark.timed(engine_id, ds, **params)
    assert outcome == "ok"
    assert secs < seconds, f"{engine_id} took {secs:.1f} s (budget {seconds} s)"


def test_tax_routing_60_jurisdictions():
    _budget("vtrl2018.tax_routing", benchmark.tax_world(60), 60)


def test_conduits_10000_entities():
    _budget("gb2017.conduits_sinks", benchmark.ownership_world(10_000), 30)


def test_persistent_homology_100_points():
    _budget("ph.vietoris_rips", benchmark.tax_world(100), 60, input="routing_cost", influence=False)
