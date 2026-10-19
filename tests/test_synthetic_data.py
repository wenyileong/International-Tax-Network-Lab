from taxnetlab.data.synthetic import make_synthetic_dataset

def test_schema_and_sizes():
    d = make_synthetic_dataset()
    assert set(d) == {"jurisdictions", "companies", "ownership", "tax_edges"}
    assert len(d["jurisdictions"]) == 5
    assert len(d["companies"]) == 7
    assert len(d["ownership"]) == 6
    assert d["jurisdictions"]["fictional"].all()

def test_ownership_percentages_in_range():
    assert make_synthetic_dataset()["ownership"]["ownership_pct"].between(0, 100).all()
