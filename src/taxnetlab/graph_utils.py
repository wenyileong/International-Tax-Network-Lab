import networkx as nx
import pandas as pd
import plotly.graph_objects as go

def build_ownership_graph(companies: pd.DataFrame, ownership: pd.DataFrame) -> nx.DiGraph:
    # UI convention: shareholder -> investee.
    graph = nx.DiGraph()
    for row in companies.to_dict("records"):
        graph.add_node(row["company_id"], label=row["company_name"],
                       jurisdiction_id=row["jurisdiction_id"], entity_type=row["entity_type"])
    for row in ownership.to_dict("records"):
        graph.add_edge(row["shareholder_id"], row["investee_id"],
                       ownership_pct=float(row["ownership_pct"]),
                       capital_value_usd_mn=float(row["capital_value_usd_mn"]),
                       source_id=row["source_id"])
    return graph

def ownership_figure(graph: nx.DiGraph, companies: pd.DataFrame, ownership: pd.DataFrame,
                     selected_jurisdiction: str = "All") -> go.Figure:
    pos = nx.spring_layout(graph, seed=17)
    ex, ey = [], []
    for u, v in graph.edges():
        x0,y0 = pos[u]; x1,y1 = pos[v]
        ex += [x0,x1,None]; ey += [y0,y1,None]
    edge_trace = go.Scatter(x=ex,y=ey,mode="lines",line=dict(width=1.2),hoverinfo="none",name="Ownership link")
    lookup = companies.set_index("company_id").to_dict("index")
    nx_, ny_, texts, jurisdictions, ids = [], [], [], [], []
    for node in graph.nodes():
        x,y = pos[node]; row = lookup[node]
        nx_.append(x); ny_.append(y); jurisdictions.append(row["jurisdiction_id"]); ids.append(node)
        texts.append(f'{row["company_name"]}<br>{row["jurisdiction_id"]}<br>{row["entity_type"]}')
    sizes = [24 if selected_jurisdiction == "All" or j == selected_jurisdiction else 12 for j in jurisdictions]
    node_trace = go.Scatter(x=nx_,y=ny_,mode="markers+text",text=ids,textposition="bottom center",
                            hovertext=texts,hoverinfo="text",customdata=jurisdictions,
                            marker=dict(size=sizes,line=dict(width=1)),name="Company")
    fig = go.Figure(data=[edge_trace,node_trace])
    fig.update_layout(showlegend=False,margin=dict(l=10,r=10,t=20,b=10),
                      xaxis=dict(visible=False),yaxis=dict(visible=False),height=560)
    return fig
