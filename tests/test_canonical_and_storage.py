"""Canonical serialisation, hashing and storage (plan v2.1, s 7.2; Appendix B, B1 and B2)."""

import hashlib
import json
import random

import pytest
from conftest import tables_of

from taxnetlab.canonical import canonical_csv, format_cell
from taxnetlab.datasets import Dataset


def test_b1_canonical_csv_has_real_newlines_and_hash_matches_file(tmp_path, fixture01):
    text = fixture01.csv_text("ownership")
    assert "\\n" not in text and text.count("\n") == len(fixture01.tables["ownership"]) + 1
    path = fixture01.save(tmp_path)
    data = (path / "ownership.csv").read_bytes()
    assert hashlib.sha256(data).hexdigest() == fixture01.table_hashes()["ownership"]


def test_hash_independent_of_row_order(fixture01):
    tables = tables_of(fixture01)
    for rows in tables.values():
        random.Random(3).shuffle(rows)
    shuffled, _ = Dataset.from_rows(fixture01.name, tables)
    assert shuffled.content_hash == fixture01.content_hash


def test_hash_changes_with_content_and_not_with_name(fixture01):
    tables = tables_of(fixture01)
    renamed, _ = Dataset.from_rows("another name", tables)
    assert renamed.dataset_id == fixture01.dataset_id
    tables["ownership"][0]["fraction"] = 0.81
    changed, _ = Dataset.from_rows(fixture01.name, tables)
    assert changed.dataset_id != fixture01.dataset_id


def test_numbers_have_one_serialisation_per_column():
    assert format_cell(1.0) == "1.0" and format_cell(0.1) == "0.1" and format_cell(True) == "true"
    assert format_cell(None) == "" and format_cell(3) == "3"
    assert canonical_csv([{"a": 'x,"y"'}], ["a"], ["a"]) == 'a\n"x,""y"""\n'


def test_b2_data_status_comes_from_sources_not_label(fixture01):
    assert fixture01.data_status == "synthetic"
    tables = tables_of(fixture01)
    tables["sources"][0]["licence_class"] = "public"
    ds, _ = Dataset.from_rows("synthetic", tables)  # the label says synthetic; the sources do not
    assert ds.data_status == "real"


def test_save_load_round_trip_and_tamper_detection(tmp_path, world):
    path = world.save(tmp_path)
    again = Dataset.load(path)
    assert again.content_hash == world.content_hash and again.name == world.name
    assert world.save(tmp_path) == path  # identical content is stored once
    f = path / "ownership.csv"
    f.write_text(f.read_text(encoding="utf-8").replace("0.6", "0.7", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        Dataset.load(path)


def test_metadata_file_is_json(tmp_path, world):
    meta = json.loads((world.save(tmp_path) / "dataset.json").read_text(encoding="utf-8"))
    assert meta["dataset_id"] == world.dataset_id and meta["data_status"] == "synthetic"
