from taxnetlab.data.synthetic import make_synthetic_dataset
from taxnetlab.provenance import dataframe_sha256, make_run_manifest

def test_hash_stable():
    df = make_synthetic_dataset()["companies"]
    assert dataframe_sha256(df) == dataframe_sha256(df.copy())

def test_manifest():
    d = make_synthetic_dataset()
    m = make_run_manifest("question", "synthetic", 17, "test", "0.1", {}, d)
    assert m["dataset"]["synthetic"] is True
    assert m["dataset"]["seed"] == 17
    assert "sha256_csv" in m["dataset"]["tables"]["companies"]
