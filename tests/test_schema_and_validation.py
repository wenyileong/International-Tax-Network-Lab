"""Schema parsing and cross-table integrity rules (plan v2.1, s 5.1 to 5.3)."""

from conftest import codes, rebuild

from taxnetlab.datasets import Dataset
from taxnetlab.schema import SCHEMAS, parse_table
from taxnetlab.validation import ValidationReport


def test_columns_found_by_header_case_insensitive_and_any_order():
    r = ValidationReport()
    rows = parse_table(SCHEMAS["sources"], [{"LICENCE_CLASS": "public", "Title": "T", " source_id ": "S1"}],
                       ["LICENCE_CLASS", "Title", " source_id "], r)
    assert r.ok
    assert rows[0]["source_id"] == "S1" and rows[0]["licence_class"] == "public"
    assert "optional_column_absent" in codes(r, "info")


def test_missing_required_column_blocks_and_extra_column_warns():
    r = ValidationReport()
    parse_table(SCHEMAS["sources"], [{"title": "T", "junk": 1}], ["title", "junk"], r)
    assert "missing_column" in codes(r, "error")
    assert "extra_column_ignored" in codes(r, "warning")


def test_cell_type_and_range_errors():
    r = ValidationReport()
    header = ["relation_id", "holder_id", "held_id", "relation_type", "fraction", "direct", "valid_from", "source_id"]
    row = {"relation_id": "R1", "holder_id": "A", "held_id": "B", "relation_type": "shares", "fraction": "1.5",
           "direct": "maybe", "valid_from": "31/12/2025", "source_id": "S"}
    parse_table(SCHEMAS["ownership"], [row], header, r)
    assert {"bad_choice", "out_of_range", "bad_bool", "bad_date"} <= codes(r, "error")


def test_nan_and_infinity_rejected():
    r = ValidationReport()
    header = ["jurisdiction_id", "attribute", "period", "value", "unit", "source_id"]
    parse_table(SCHEMAS["jurisdiction_attributes"],
                [dict(zip(header, ["FIC_A", "gdp", "2025", "inf", "m", "S"]))], header, r)
    assert "bad_number" in codes(r, "error")


def test_valid_fixture_has_no_errors(fixture01, world):
    assert fixture01.validate().ok
    assert world.validate().ok


def test_referential_integrity_blocks(fixture01):
    ds, rep = rebuild(fixture01, lambda t: t["ownership"][0].update(held_id="CO_999"))
    assert ds is None and "unknown_entity" in codes(rep, "error")


def test_natural_persons_and_indirect_relations_block(fixture01):
    ds, rep = rebuild(fixture01, lambda t: t["entities"][0].update(is_natural_person=True))
    assert ds is None and "natural_person" in codes(rep, "error")
    ds, rep = rebuild(fixture01, lambda t: t["ownership"][0].update(direct=False))
    assert ds is None and "indirect_stored" in codes(rep, "error")


def test_invented_data_never_attributed_to_real_states(fixture01):
    def make_real(t):
        t["jurisdictions"][0].update(jurisdiction_id="GBR", fictional=False, iso3="GBR")
        for e in t["entities"]:
            if e["jurisdiction_id"] == "FIC_A":
                e["jurisdiction_id"] = "GBR"
        for a in t["jurisdiction_attributes"]:
            if a["jurisdiction_id"] == "FIC_A":
                a["jurisdiction_id"] = "GBR"
        for x in t["illustrative_tax_edges"]:
            for k in ("source_jurisdiction", "target_jurisdiction"):
                if x[k] == "FIC_A":
                    x[k] = "GBR"
    ds, rep = rebuild(fixture01, make_real)
    assert ds is None and "synthetic_on_real_jurisdiction" in codes(rep, "error")


def test_jurisdiction_identifier_rules(fixture01):
    ds, rep = rebuild(fixture01, lambda t: t["jurisdictions"][0].update(jurisdiction_id="A_LAND"))
    assert ds is None and "fictional_prefix" in codes(rep, "error")
    ds, rep = rebuild(fixture01, lambda t: t["jurisdictions"].append(
        {"jurisdiction_id": "Britain", "display_name": "x", "iso3": None, "fictional": False, "parent_jurisdiction_id": None}))
    assert ds is None and "bad_iso3" in codes(rep, "error")


def test_parallel_relations_kept_and_reported(fixture01):
    def add_parallel(t):
        extra = dict(t["ownership"][0], relation_id="R99999", share_class="B", fraction=0.1)
        t["ownership"].append(extra)
    ds, rep = rebuild(fixture01, add_parallel)
    assert ds is not None
    assert "parallel_relation" in codes(rep, "warning")
    assert len(ds.tables["ownership"]) == 7  # nothing merged or dropped


def test_equity_over_one_cycle_and_currency_checks(fixture01):
    def bad(t):
        t["ownership"].append(dict(t["ownership"][0], relation_id="R90001", holder_id="CO_006", fraction=0.5))
        t["ownership"].append(dict(t["ownership"][0], relation_id="R90002", holder_id="CO_004", held_id="CO_001",
                                   fraction=0.01))
    ds, rep = rebuild(fixture01, bad)
    assert {"equity_over_one", "ownership_cycle"} <= codes(rep, "warning")
    ds, rep = rebuild(fixture01, lambda t: t["ownership"][0].update(value_currency=None))
    assert "amount_without_currency" in codes(rep, "error")
    ds, rep = rebuild(fixture01, lambda t: t["ownership"][0].update(valid_to="2020-01-01"))
    assert "bad_period" in codes(rep, "error")


def test_missing_fraction_is_never_imputed(fixture01):
    ds, rep = rebuild(fixture01, lambda t: t["ownership"][0].update(fraction=None))
    assert ds is not None and ds.tables["ownership"][0]["fraction"] is None
    assert "fraction_missing" in codes(rep, "warning")


def test_csv_import_with_bom_and_missing_tables():
    ds, rep = Dataset.from_csv_texts("x", {"sources": "﻿source_id,title,licence_class\nS,T,public\n"})
    assert ds is None
    assert "missing_table" in codes(rep, "error")
    assert not any(i.code == "missing_column" for i in rep.issues)  # BOM tolerated
