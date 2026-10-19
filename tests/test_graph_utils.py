from taxnetlab.data.synthetic import make_synthetic_dataset
from taxnetlab.graph_utils import build_ownership_graph, ownership_figure

def test_graph_counts():
    d = make_synthetic_dataset()
    g = build_ownership_graph(d["companies"], d["ownership"])
    assert g.number_of_nodes() == len(d["companies"])
    assert g.number_of_edges() == len(d["ownership"])
    assert g.has_edge("CO_001", "CO_002")

def test_figure_traces():
    d = make_synthetic_dataset()
    g = build_ownership_graph(d["companies"], d["ownership"])
    assert len(ownership_figure(g, d["companies"], d["ownership"]).data) == 2
