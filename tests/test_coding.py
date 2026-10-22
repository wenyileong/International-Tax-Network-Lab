"""Legal coding templates and data dictionary (plan s 5.4)."""

import csv
import io
import zipfile

import pytest

from taxnetlab import coding
from taxnetlab.api import Api
from taxnetlab.cli import main
from taxnetlab.datasets import Dataset
from taxnetlab.schema import SCHEMAS


def test_every_template_column_is_described_with_a_layer():
    for table in coding.TEMPLATE_TABLES:
        if table in coding.REFERENCE_TABLES:
            continue
        for c in SCHEMAS[table].columns:
            layer, desc = coding.DICTIONARY[(table, c.name)]
            assert layer in coding.LAYERS and desc, (table, c.name)
    assert set(coding.DICTIONARY) <= {(t, c.name) for t in SCHEMAS for c in SCHEMAS[t].columns}
    legal_layers = {coding.DICTIONARY[(t, c.name)][0] for t in coding.LEGAL_TABLES for c in SCHEMAS[t].columns}
    assert {"liability", "collection", "provenance", "key"} <= legal_layers


def test_illustrative_template_round_trip():
    """A template written and read back is identical (plan s 5.4)."""
    data = coding.template_zip("illustrative")
    texts = coding.read_template_zip(data)
    ds, report = Dataset.from_csv_texts("Illustrative", texts)
    assert ds is not None, report.format_text()
    assert all(j["fictional"] for j in ds.tables["jurisdictions"])
    assert coding.tables_to_csv(ds.tables) == texts
    assert data == coding.template_zip("illustrative")  # byte-identical on every build
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert "README.txt" in names and "data_dictionary.csv" in names
    assert len(ds.tables["tax_treaty_conditions"]) == 6


def test_real_sample_template_blank_and_unverified_until_coded():
    texts = coding.read_template_zip(coding.template_zip("real_sample", ["lux", "NLD"]))
    rows = list(csv.DictReader(io.StringIO(texts["tax_domestic"])))
    assert [r["jurisdiction_id"] for r in rows] == ["LUX", "NLD"]
    assert all(r["cit_rate"] == "" and r["relief_method"] == "" and r["verified"] == "false" for r in rows)
    ds, report = Dataset.from_csv_texts("blank", texts)
    assert ds is None and not report.ok  # blank legal fields block the import

    # Coding the blanks makes it load, with every row still flagged as unverified.
    def fill(table, values):
        rdr = list(csv.DictReader(io.StringIO(texts[table])))
        for r in rdr:
            r.update({k: v for k, v in values.items() if r.get(k, "") == ""})
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(rdr[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rdr)
        texts[table] = buf.getvalue()

    fill("sources", {"title": "Test statutes", "licence_class": "public"})
    fill("jurisdictions", {"display_name": "X"})
    fill("jurisdiction_attributes", {"value": "100", "unit": "million", "currency": "EUR", "source_id": "SRC_01"})
    fill("tax_domestic", {"cit_rate": "0.25", "dividend_wht_rate": "0.15", "relief_method": "exemption",
                          "rule_status": "source_backed", "source_id": "SRC_01"})
    ds, report = Dataset.from_csv_texts("coded", texts)
    assert ds is not None, report.format_text()
    assert sum(i.code == "unverified_legal_row" for i in report.issues) == 2


def test_real_sample_rejects_bad_codes():
    with pytest.raises(ValueError):
        coding.template_zip("real_sample", ["Netherlands"])
    with pytest.raises(ValueError):
        coding.template_zip("other")


def test_zip_reader_ignores_other_files_and_rejects_empty():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("notes.txt", "x")
        z.writestr("folder/unknown.csv", "a\n1\n")
    with pytest.raises(ValueError):
        coding.read_template_zip(buf.getvalue())


def test_api_and_cli_import(tmp_path, workspace, capsys):
    out = Api(workspace).import_zip("Illustrative", coding.template_zip("illustrative"))
    assert out["saved"]
    path = tmp_path / "t.zip"
    assert main(["template", "illustrative", "--out", str(path)]) == 0
    assert main(["import", str(path), "--workspace", str(tmp_path / "ws2")]) == 0
    assert main(["template", "real-sample", "--jurisdictions", "IRL", "--out", str(tmp_path / "r.zip")]) == 0
    assert main(["import", str(tmp_path / "r.zip"), "--workspace", str(tmp_path / "ws2")]) == 2


def test_server_template_and_zip_import(server_url_token):
    import base64
    import json
    import urllib.request

    url, token = server_url_token
    data = urllib.request.urlopen(url + "api/templates/illustrative.zip", timeout=10).read()
    assert data[:2] == b"PK"
    body = json.dumps({"name": "via server", "zip_base64": base64.b64encode(data).decode()}).encode()
    req = urllib.request.Request(url + "api/datasets/import_zip", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "X-TaxNetLab-Token": token})
    assert json.loads(urllib.request.urlopen(req, timeout=10).read())["saved"]
    real = urllib.request.urlopen(url + "api/templates/real_sample.zip?jurisdictions=MYS,SGP", timeout=10).read()
    assert "MYS" in coding.read_template_zip(real)["tax_domestic"]
