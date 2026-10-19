from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st
from taxnetlab.data.synthetic import make_synthetic_dataset
from taxnetlab.graph_utils import build_ownership_graph, ownership_figure
from taxnetlab.provenance import make_run_manifest, manifest_as_json
from taxnetlab.models import MODEL_REGISTRY

st.set_page_config(page_title="International Tax Network Lab", layout="wide")
st.title("International Tax Network Lab")
st.caption("Academic prototype · local-first · synthetic data by default")
st.warning("Build 0.1 uses fabricated data. The model engines are separate research modules and are not yet validated reproductions.")

with st.sidebar:
    st.header("Research session")
    question = st.text_input("Research question", "How do illustrative ownership relationships shape a jurisdiction network?")
    seed = st.number_input("Synthetic-data seed (recorded)", min_value=0, max_value=999999, value=17)

data = make_synthetic_dataset(int(seed))
tabs = st.tabs(["Overview", "Network Explorer", "Data & Provenance", "Model Register", "Research Notes"])

with tabs[0]:
    st.subheader("Workspace overview")
    a, b, c = st.columns(3)
    a.metric("Illustrative jurisdictions", len(data["jurisdictions"]))
    b.metric("Illustrative companies", len(data["companies"]))
    c.metric("Ownership links", len(data["ownership"]))
    st.markdown("**Current scope:** data contracts, interactive graph, run manifest, and independently labelled model interfaces.")
    st.markdown("**Not yet implemented:** the published tax-routing equations, full conduit/sink measures, or patent-specific scalable TDA procedure.")
    st.dataframe(data["jurisdictions"], use_container_width=True, hide_index=True)

with tabs[1]:
    graph = build_ownership_graph(data["companies"], data["ownership"])
    choice = st.selectbox("Highlight jurisdiction", ["All"] + data["jurisdictions"]["jurisdiction_id"].tolist())
    st.plotly_chart(ownership_figure(graph, data["companies"], data["ownership"], choice), use_container_width=True)
    st.caption("Illustrative edges point from shareholder company to investee company. This is a UI convention, not a claim about the direction used in a particular paper.")
    st.dataframe(data["ownership"], use_container_width=True, hide_index=True)

with tabs[2]:
    table_name = st.selectbox("Table", list(data.keys()))
    st.dataframe(data[table_name], use_container_width=True, hide_index=True)
    st.download_button("Download selected CSV", data[table_name].to_csv(index=False).encode(), f"synthetic_{table_name}.csv", "text/csv")
    manifest = make_run_manifest(question, "synthetic", int(seed), "application_shell", "0.1.0",
                                 {"highlight_jurisdiction": choice if "choice" in locals() else "not_selected"}, data)
    st.subheader("Run manifest")
    st.json(manifest)
    st.download_button("Download run_manifest.json", manifest_as_json(manifest), "run_manifest.json", "application/json")

with tabs[3]:
    for model in MODEL_REGISTRY.values():
        with st.expander(model["display_name"], expanded=True):
            st.write(model["purpose"])
            st.write("**Status:** " + model["status"])
            st.write("**Next step:** " + model["next_step"])
            st.write("**Boundary:** " + model["validation_boundary"])

with tabs[4]:
    st.markdown("""
- Preserve the research question and estimand.
- Record source, access date, licence/terms, data transformations and limitations.
- Define unit of analysis and edge direction.
- Record missing-data and entity-resolution decisions.
- Separate observed, modelled and exploratory structures.
- Do not infer causation or illegality from visual proximity or centrality alone.
""")
