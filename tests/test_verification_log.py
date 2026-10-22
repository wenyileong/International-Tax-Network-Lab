"""Verification log for legal rows (plan s 5.4, A37)."""

import copy

from taxnetlab.datasets import Dataset
from taxnetlab.fixtures import vtrl_fixture


def with_log(rows, mutate=None):
    tables = copy.deepcopy(vtrl_fixture().tables)
    if mutate:
        mutate(tables)
    tables["rule_verifications"] = rows
    return Dataset.from_rows("log", tables)


def entry(key, table="tax_domestic", outcome="confirmed", date="2026-10-01"):
    return {"table_name": table, "row_key": key, "verified_on": date, "verified_by": "WYL", "outcome": outcome,
            "source_id": None, "pinpoint": "s 1", "note": None}


def test_log_refers_to_existing_rows():
    ds, rep = with_log([entry("FIC_H|2025"), entry("FIC_H|FIC_C|2025", table="tax_treaty_dividends")])
    assert ds is not None, rep.format_text()
    ds, rep = with_log([entry("FIC_Z|2025")])
    assert ds is None and "verification_unknown_row" in {i.code for i in rep.errors}


def test_confirmed_but_unverified_is_warned():
    _, rep = with_log([entry("FIC_H|2025")])
    assert "logged_but_unverified" in {i.code for i in rep.issues}
    _, rep = with_log([entry("FIC_H|2025", outcome="corrected", date="2026-09-01"), entry("FIC_H|2025", date="2026-10-02",
                                                                                       outcome="rejected")])
    assert "logged_but_unverified" not in {i.code for i in rep.issues}  # the latest entry decides


def test_empty_log_keeps_dataset_ids():
    assert with_log([])[0].dataset_id == vtrl_fixture().dataset_id


def test_iso_registry():
    from taxnetlab.registry import iso3_names, is_assigned

    names = iso3_names()
    assert len(names) >= 249 and names["MYS"] == "Malaysia" and is_assigned("NLD") and not is_assigned("XKX")


def test_unassigned_code_is_a_warning():
    from taxnetlab import coding

    assert "Malaysia" in coding.read_template_zip(coding.template_zip("real_sample", ["MYS"]))["jurisdictions"]
    tables = copy.deepcopy(vtrl_fixture().tables)
    tables["jurisdictions"].append({"jurisdiction_id": "XKX", "display_name": "Kosovo", "iso3": "XKX", "fictional": False,
                                    "parent_jurisdiction_id": None})
    ds, rep = Dataset.from_rows("x", tables)
    assert ds is not None and any(i.code == "iso3_not_assigned" and i.level == "warning" for i in rep.issues)
