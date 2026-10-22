"""Tri-state eligibility (docs/specs/eligibility.md) and its use by the tax routing engine."""

import pytest

from taxnetlab.datasets import Dataset
from taxnetlab.eligibility import ELIGIBLE, INDETERMINATE, INELIGIBLE, Facts, evaluate
from taxnetlab.engines import get_engine
from taxnetlab.fixtures import PERIOD, vtrl_fixture
from taxnetlab.synthetic import SYNTHETIC_SOURCE, generate

ENGINE = "vtrl2018.tax_routing"


def cond(condition, threshold=None, payer="FIC_H", recipient="FIC_X", verified=False):
    return {"payer_jurisdiction": payer, "recipient_jurisdiction": recipient, "period": PERIOD, "condition": condition,
            "threshold": threshold, "pinpoint": None, "rule_status": "synthetic_assumption", "verified": verified,
            "source_id": SYNTHETIC_SOURCE["source_id"], "note": "test"}


# ------------------------------------------------------------------ evaluator
def test_no_conditions_is_eligible():
    assert evaluate([], Facts(), 0.2).status == ELIGIBLE


@pytest.mark.parametrize("holding,expected", [(0.10, ELIGIBLE), (0.0999, INELIGIBLE), (1.0, ELIGIBLE)])
def test_min_holding(holding, expected):
    assert evaluate([cond("min_holding", 0.10)], Facts(holding_fraction=holding), 0.2).status == expected


def test_min_holding_days_and_subject_to_tax():
    rows = [cond("min_holding_days", 365), cond("subject_to_tax", 0.0)]
    assert evaluate(rows, Facts(holding_days=365), 0.2).status == ELIGIBLE
    out = evaluate(rows, Facts(holding_days=364), 0.0)
    assert out.status == INELIGIBLE and out.failed == ["min_holding_days", "subject_to_tax"]


def test_judgement_conditions_never_resolved_by_default():
    rows = [cond("ppt"), cond("beneficial_ownership"), cond("lob")]
    out = evaluate(rows, Facts(), 0.2)
    assert out.status == INDETERMINATE and out.unresolved == ["beneficial_ownership", "lob", "ppt"]
    met = Facts(assumptions={"ppt": "met", "beneficial_ownership": "met", "lob": "met"})
    assert evaluate(rows, met, 0.2).status == ELIGIBLE
    assert evaluate(rows, Facts(assumptions={"ppt": "not_met"}), 0.2).status == INELIGIBLE


def test_failure_takes_precedence_over_indeterminate():
    out = evaluate([cond("ppt"), cond("min_holding", 0.5)], Facts(holding_fraction=0.1), 0.2)
    assert out.status == INELIGIBLE and out.unresolved == ["ppt"]


# ------------------------------------------------------------------ engine
def run(ds, **params):
    eng = get_engine(ENGINE)
    resolved, rep = eng.resolve_parameters(params)
    assert rep.ok, rep.format_text()
    v = eng.validate(ds, resolved)
    assert v.ok, v.format_text()
    res = eng.run(ds, resolved)
    assert res.outcome == "ok"
    return res


def leg(res, a, b):
    """The direct leg from a to b, as reported on the pair."""
    pair = next(r for r in res.outputs["pairs"] if r["host"] == a and r["home"] == b)
    return {"wht_rate": pair["direct_wht"], "wht_basis": pair["direct_wht_basis"]}


@pytest.fixture
def ppt_world():
    # H pays to X at the treaty rate 0 only if the principal purpose test is met.
    return vtrl_fixture({"tax_treaty_conditions": [cond("ppt")]})


def test_reproduction_mode_ignores_conditions(ppt_world):
    plain, with_conditions = run(vtrl_fixture()), run(ppt_world)
    assert plain.outputs == with_conditions.outputs  # nothing changes in the source's mode


def test_strict_withholds_indeterminate_benefit(ppt_world):
    res = run(ppt_world, eligibility="strict")
    hx = leg(res, "FIC_H", "FIC_X")
    assert hx["wht_rate"] == 0.15 and hx["wht_basis"] == "general_indeterminate"
    summary = {r["measure"]: r["value"] for r in res.outputs["summary"]}
    assert summary["treaties_indeterminate"] == 1 and summary["indeterminate_treaties"] == "FIC_H>FIC_X (ppt)"


def test_contingent_grants_and_flags(ppt_world):
    res = run(ppt_world, eligibility="contingent")
    hx = leg(res, "FIC_H", "FIC_X")
    assert hx["wht_rate"] == 0.0 and hx["wht_basis"] == "treaty_contingent"
    summary = {r["measure"]: r["value"] for r in res.outputs["summary"]}
    assert summary["pairs_relying_on_assumptions"] >= 1
    assert any("indeterminate" in w for w in res.warnings)


def test_neutral_assumptions_reproduce_the_source(ppt_world):
    """'Nothing changes' (plan s 6.3): with every condition met, the extension equals the reproduction."""
    base = run(vtrl_fixture())
    ext = run(ppt_world, eligibility="strict", assume_ppt="met")
    for name in ("pairs", "legs", "centrality"):
        assert ext.outputs[name] == base.outputs[name], name


def test_ppt_not_met_is_ineligible(ppt_world):
    res = run(ppt_world, eligibility="contingent", assume_ppt="not_met")
    assert leg(res, "FIC_H", "FIC_X")["wht_basis"] == "general_ineligible"


def test_withdrawing_benefits_never_lowers_tax():
    ds = generate(seed=11, n_jurisdictions=10)
    assert ds.tables["tax_treaty_conditions"]
    assume = {(r["host"], r["home"]): r["best_te"] for r in run(ds).outputs["pairs"]}
    contingent = {(r["host"], r["home"]): r["best_te"] for r in run(ds, eligibility="contingent").outputs["pairs"]}
    strict = {(r["host"], r["home"]): r["best_te"] for r in run(ds, eligibility="strict", holding_fraction=0.05).outputs["pairs"]}
    for pair, te in assume.items():
        assert contingent[pair] >= te - 1e-12
        assert strict[pair] >= contingent[pair] - 1e-12


def test_validation_of_conditions():
    rows = [cond("min_holding"), cond("ppt", 0.3), cond("min_holding", 0.1, payer="FIC_C", recipient="FIC_P")]
    tables = {t: list(r) for t, r in vtrl_fixture().tables.items()}
    tables["tax_treaty_conditions"] = rows
    ds, report = Dataset.from_rows("bad", tables)
    codes = {i.code for i in report.issues}
    assert ds is None and "threshold_required" in codes
    assert {"threshold_ignored", "condition_without_treaty"} <= codes
