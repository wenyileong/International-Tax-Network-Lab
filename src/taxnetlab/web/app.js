/* International Tax Network Lab: offline interface.
 * Plain JavaScript, no build step. All visible text goes through t() so that languages can be added
 * by dropping a locale file into web/locales (see taxnetlab/i18n.py).
 */
(function () {
  "use strict";

  // ------------------------------------------------------------------ state
  const TOKEN = document.querySelector('meta[name="taxnetlab-token"]').content;
  const PALETTE = ["#2563eb", "#f97316", "#14b8a6", "#f59e0b", "#d946ef", "#8b5cf6", "#ef4444", "#22c55e",
    "#0ea5e9", "#ec4899", "#84cc16", "#6366f1", "#eab308", "#06b6d4", "#f43f5e", "#a855f7"];
  // Plasma-like ramp, truncated before its palest yellow so that lines stay visible on light backgrounds.
  const RAMP = ["#0d0887", "#4c02a1", "#7e03a8", "#a92395", "#cc4778", "#e66c5c", "#f89540", "#f9b625"];
  const SCALE = RAMP.map((c, i) => [i / (RAMP.length - 1), c]);
  const STATUS_COLOURS = { interface: "#94a3b8", specified: "#0ea5e9", implemented: "#6366f1", verified: "#059669",
    replicated: "#16a34a", replicated_with_discrepancies: "#ca8a04", robust: "#0d9488", empirically_tested: "#15803d" };
  const S = { strings: {}, locale: "en-GB", locales: [], datasets: [], datasetId: null, dataset: null, engines: [],
    page: "overview", jurColour: {} };

  // ------------------------------------------------------------------ i18n
  function t(key, params) {
    let s = Object.prototype.hasOwnProperty.call(S.strings, key) ? S.strings[key] : key;
    if (params) s = s.replace(/\{(\w+)\}/g, (m, k) => (params[k] === undefined || params[k] === null ? m : String(params[k])));
    return s;
  }
  function tOr(key, fallback, params) { return Object.prototype.hasOwnProperty.call(S.strings, key) ? t(key, params) : fallback; }
  function fmt(n, digits) {
    if (n === null || n === undefined || n === "") return "";
    const x = Number(n);
    if (!Number.isFinite(x)) return String(n);
    return new Intl.NumberFormat(S.locale, { maximumFractionDigits: digits === undefined ? 2 : digits }).format(x);
  }
  function pct(x) { return x === null || x === undefined ? "" : new Intl.NumberFormat(S.locale, { style: "percent", maximumFractionDigits: 1 }).format(x); }
  function applyI18n(root) {
    (root || document).querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    (root || document).querySelectorAll("[data-i18n-title]").forEach((el) => { el.title = t(el.dataset.i18nTitle); });
    (root || document).querySelectorAll("[data-i18n-placeholder]").forEach((el) => { el.placeholder = t(el.dataset.i18nPlaceholder); });
  }
  function store(key, value) { try { localStorage.setItem("taxnetlab." + key, value); } catch (e) { /* storage unavailable */ } }
  function recall(key) { try { return localStorage.getItem("taxnetlab." + key); } catch (e) { return null; } }

  async function loadLocale(tag) {
    const data = await api("GET", "locales/" + encodeURIComponent(tag));
    S.strings = data.strings; S.locale = tag;
    document.documentElement.lang = tag;
    document.documentElement.dir = (data.meta && data.meta.dir) || "ltr";
    store("locale", tag);
    applyI18n();
  }

  // ------------------------------------------------------------------ helpers
  async function api(method, path, body) {
    const opts = { method, headers: {} };
    if (method !== "GET") { opts.headers["Content-Type"] = "application/json"; opts.headers["X-TaxNetLab-Token"] = TOKEN; opts.body = JSON.stringify(body || {}); }
    const res = await fetch("/api/" + path, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { const err = new Error((data.error && data.error.message) || res.statusText); err.data = data; err.status = res.status; throw err; }
    return data;
  }
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === undefined || v === null || v === false) continue;
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k === "i18n") { node.dataset.i18n = v; node.textContent = t(v); }
      else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else if (k === "style") node.setAttribute("style", v);
      else node.setAttribute(k, v === true ? "" : v);
    }
    for (const c of [].concat(children || [])) { if (c !== null && c !== undefined) node.append(c instanceof Node ? c : document.createTextNode(String(c))); }
    return node;
  }
  function toast(msg) {
    const box = document.getElementById("toast");
    box.textContent = msg; box.hidden = false;
    clearTimeout(toast._t); toast._t = setTimeout(() => { box.hidden = true; }, 4200);
  }
  function fail(e) { console.error(e); toast(t("msg.error", { message: e.message })); }
  function download(filename, text, type) {
    const blob = new Blob([text], { type: type || "text/csv;charset=utf-8" });
    const a = el("a", { href: URL.createObjectURL(blob), download: filename });
    document.body.append(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }
  function csvOf(columns, rows) {
    const q = (v) => { const s = v === null || v === undefined ? "" : String(v); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
    return [columns.map(q).join(",")].concat(rows.map((r) => columns.map((c) => q(Array.isArray(r) ? r[columns.indexOf(c)] : r[c])).join(","))).join("\n") + "\n";
  }
  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function jurColour(id) {
    if (!(id in S.jurColour)) S.jurColour[id] = PALETTE[Object.keys(S.jurColour).length % PALETTE.length];
    return S.jurColour[id];
  }
  function resetColours() {
    S.jurColour = {};
    if (S.dataset) S.dataset.jurisdictions.forEach((j) => jurColour(j));
  }
  function issueText(i) { return tOr("issue." + i.code, i.message, i.params); }
  function issuesList(validation) {
    if (!validation || !validation.issues.length) return el("p", { class: "ok-text", text: t("data.no_issues") });
    const shown = validation.issues.filter((i) => i.level !== "info").concat(validation.issues.filter((i) => i.level === "info"));
    return el("ul", { class: "issues" }, shown.slice(0, 300).map((i) => el("li", {}, [
      el("span", { class: "lvl " + i.level, text: t("level." + i.level) }),
      el("span", {}, [issueText(i), i.table ? el("span", { class: "muted", text: "  " + t("issue.where", { table: i.table, row: i.row === null ? "" : i.row }) }) : null]),
    ])));
  }

  // ------------------------------------------------------------------ charts
  function baseLayout(extra) {
    const text = cssVar("--text"), line = cssVar("--line");
    const base = {
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: cssVar("--font") || "Segoe UI, system-ui, sans-serif", size: 12.5, color: text },
      margin: { l: 56, r: 24, t: 34, b: 52 }, hoverlabel: { font: { size: 12.5 } },
      xaxis: { gridcolor: line, zerolinecolor: line, automargin: true }, yaxis: { gridcolor: line, zerolinecolor: line, automargin: true },
      legend: { orientation: "h", y: -0.18 },
    };
    const out = Object.assign({}, base, extra || {});
    for (const k of ["xaxis", "yaxis", "legend", "font"]) if (extra && extra[k]) out[k] = Object.assign({}, base[k], extra[k]);
    return out;
  }
  function watermark(labels) {
    // Several labels are stacked rather than joined, so that narrow charts never clip them.
    const items = labels.filter(Boolean);
    return items.length ? [{ text: items.join("<br>"), xref: "paper", yref: "paper", x: 1, y: 1, xanchor: "right", yanchor: "bottom",
      yshift: 4, align: "right", showarrow: false, font: { size: 10.5, color: "rgba(234,88,12,0.9)" }, _wm: items.length }] : [];
  }
  function statusWatermark() {
    const st = S.dataset && S.dataset.data_status;
    return st === "synthetic" ? t("wm.synthetic") : st === "mixed" ? t("wm.mixed") : null;
  }
  function plot(node, traces, layout, csv) {
    const svgIcon = { width: 1000, height: 1000, path: "M200 100h400l200 200v600H200z M600 100v200h200 M330 520h340M330 640h340M330 760h220" };
    const buttons = [{ name: t("chart.download_svg"), icon: svgIcon, click: (gd) => Plotly.downloadImage(gd, { format: "svg", filename: csv ? csv.name : "chart" }) }];
    if (csv) buttons.push({ name: t("chart.download_csv"), icon: Plotly.Icons.disk, click: () => download(csv.name + ".csv", csvOf(csv.columns, csv.rows)) });
    const full = baseLayout(layout);
    const wm = (full.annotations || []).find((a) => a._wm);
    if (wm) full.margin = Object.assign({}, full.margin, { t: Math.max((full.margin || {}).t || 0, 12 + 14 * wm._wm) });
    full.annotations = (full.annotations || []).map((a) => { const c = Object.assign({}, a); delete c._wm; return c; });
    return Plotly.react(node, traces, full, {
      responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"],
      modeBarButtonsToAdd: buttons, toImageButtonOptions: { format: "png", scale: 2, filename: csv ? csv.name : "chart" },
    });
  }

  // ------------------------------------------------------------------ app shell
  async function loadDatasets(selectId) {
    S.datasets = await api("GET", "datasets");
    const sel = document.getElementById("dataset-select");
    sel.replaceChildren(...S.datasets.map((d) => el("option", { value: d.dataset_id, text: d.name + "  ·  " + d.dataset_id.slice(0, 8) })));
    const wanted = selectId || S.datasetId || recall("dataset");
    S.datasetId = S.datasets.some((d) => d.dataset_id === wanted) ? wanted : (S.datasets[0] && S.datasets[0].dataset_id) || null;
    sel.value = S.datasetId || "";
    await loadDataset();
  }
  async function loadDataset() {
    S.dataset = null;
    if (S.datasetId) {
      const info = await api("GET", "datasets/" + S.datasetId);
      const jt = await api("GET", "datasets/" + S.datasetId + "/tables/jurisdictions");
      info.jurisdictions = jt.rows.map((r) => r.jurisdiction_id);
      info.jurisdictionNames = Object.fromEntries(jt.rows.map((r) => [r.jurisdiction_id, r.display_name]));
      const at = await api("GET", "datasets/" + S.datasetId + "/tables/jurisdiction_attributes");
      info.gdp = at.rows.filter((r) => String(r.attribute).toLowerCase() === "gdp");
      S.dataset = info;
      store("dataset", S.datasetId);
    }
    resetColours();
    const chip = document.getElementById("status-chip");
    const banner = document.getElementById("banner");
    if (S.dataset) {
      const st = S.dataset.data_status;
      chip.hidden = false; chip.className = "chip " + st; chip.textContent = t("status." + st);
      banner.hidden = st === "real"; banner.textContent = st === "real" ? "" : t("banner." + st);
    } else { chip.hidden = true; banner.hidden = true; }
  }

  const PAGES = {};
  async function route() {
    const page = (location.hash.replace(/^#\//, "") || "overview").split("?")[0];
    S.page = PAGES[page] ? page : "overview";
    document.querySelectorAll(".sidenav a").forEach((a) => a.classList.toggle("active", a.dataset.page === S.page));
    const root = document.getElementById("page");
    root.replaceChildren();
    try { await PAGES[S.page](root); } catch (e) { fail(e); root.append(el("p", { class: "err-text", text: t("msg.error", { message: e.message }) })); }
    applyI18n(root);
  }
  function header(root, titleKey, ledeKey) {
    root.append(el("h1", { i18n: titleKey }), el("p", { class: "lede", i18n: ledeKey }));
  }
  function needDataset(root) {
    if (S.dataset) return false;
    root.append(el("div", { class: "card empty" }, [el("p", { i18n: "msg.no_dataset" }), el("a", { href: "#/data", i18n: "nav.data" })]));
    return true;
  }

  // ------------------------------------------------------------------ overview
  PAGES.overview = async function (root) {
    header(root, "overview.title", "overview.lede");
    if (needDataset(root)) return;
    const d = S.dataset, c = d.counts;
    const view = await api("GET", `datasets/${d.dataset_id}/view?view=ownership`);
    const where = Object.fromEntries(view.nodes.map((n) => [n.id, n.jurisdiction_id]));
    const cross = view.edges.filter((e) => where[e.source] !== where[e.target]).length;
    const kpis = [
      ["overview.kpi.jurisdictions", fmt(c.jurisdictions, 0), "#2563eb"], ["overview.kpi.entities", fmt(c.entities, 0), "#f97316"],
      ["overview.kpi.relations", fmt(c.ownership, 0), "#14b8a6"],
      ["overview.kpi.cross_border", view.edges.length ? pct(cross / view.edges.length) : "", "#d946ef"],
    ];
    root.append(el("div", { class: "grid grid-4" }, kpis.map(([k, v, col]) => el("div", { class: "card kpi", style: "--c:" + col }, [
      el("div", { class: "value", text: v }), el("div", { class: "label", i18n: k })]))));
    root.append(el("div", { class: "spacer" }));

    const byJur = {};
    view.nodes.forEach((n) => { byJur[n.jurisdiction_id] = byJur[n.jurisdiction_id] || {}; byJur[n.jurisdiction_id][n.entity_type] = (byJur[n.jurisdiction_id][n.entity_type] || 0) + 1; });
    const types = [...new Set(view.nodes.map((n) => n.entity_type))].sort();
    const jurs = d.jurisdictions;
    const p1 = el("div", { class: "plot" }), p2 = el("div", { class: "plot" });
    root.append(el("div", { class: "grid grid-2" }, [
      el("div", { class: "card" }, [el("h2", { i18n: "overview.chart.entities" }), p1]),
      el("div", { class: "card" }, [el("h2", { i18n: "overview.chart.fractions" }), p2]),
    ]));
    plot(p1, types.map((ty, k) => ({ type: "bar", name: tOr("entity_type." + ty, ty), x: jurs, y: jurs.map((j) => (byJur[j] || {})[ty] || 0),
      marker: { color: PALETTE[k % PALETTE.length] }, hovertemplate: "%{x}<br>%{fullData.name}: %{y}<extra></extra>" })),
    { barmode: "stack", annotations: watermark([statusWatermark()]), yaxis: { title: { text: t("overview.axis.entities") } } },
    { name: "entities_by_jurisdiction", columns: ["jurisdiction_id"].concat(types), rows: jurs.map((j) => [j].concat(types.map((ty) => (byJur[j] || {})[ty] || 0))) });

    const fr = view.edges.map((e) => e.fraction).filter((x) => x !== null && x !== undefined);
    const bins = [0, 0.1, 0.25, 0.5, 0.75, 0.9999, 1.0001];
    const labels = ["b1", "b2", "b3", "b4", "b5", "b6"].map((k) => t("overview.band." + k));
    const counts = labels.map((_, i) => fr.filter((x) => x >= bins[i] && x < bins[i + 1]).length);
    const colours = labels.map((_, i) => `hsl(${265 - i * 42}, 85%, ${52 + (i % 2) * 4}%)`);
    plot(p2, [{ type: "bar", x: labels, y: counts, marker: { color: colours }, hovertemplate: "%{x}: %{y}<extra></extra>" }],
      { annotations: watermark([statusWatermark()]), yaxis: { title: { text: t("overview.axis.relations") } }, showlegend: false },
      { name: "relations_by_fraction_band", columns: ["band", "relations"], rows: labels.map((l, i) => [l, counts[i]]) });

    root.append(el("div", { class: "spacer" }), el("div", { class: "card" }, [el("h2", { i18n: "data.validation" }), issuesList(d.validation)]));
  };

  // ------------------------------------------------------------------ network
  PAGES.network = async function (root) {
    header(root, "network.title", "network.lede");
    if (needDataset(root)) return;
    const st = { view: recall("net.view") || "ownership", colour: recall("net.colour") || "fraction", rule: recall("net.rule") || "count", as_of: "", domestic: false };
    const viewSel = el("select", { class: "select" }, ["ownership", "value_flow", "jurisdiction"].map((v) => el("option", { value: v, text: t("view." + v) })));
    const colourSel = el("select", { class: "select" }, ["fraction", "value"].map((v) => el("option", { value: v, text: t("network.colour." + v) })));
    const ruleSel = el("select", { class: "select" }, ["count", "fraction_sum", "value_sum"].map((v) => el("option", { value: v, text: t("rule." + v) })));
    const asOf = el("input", { type: "date" });
    const dom = el("input", { type: "checkbox" });
    viewSel.value = st.view; colourSel.value = st.colour; ruleSel.value = st.rule;
    const colourField = el("label", { class: "field" }, [el("span", { i18n: "network.colour_by" }), colourSel]);
    const ruleField = el("label", { class: "field" }, [el("span", { i18n: "network.rule" }), ruleSel]);
    const domField = el("label", { class: "field inline" }, [dom, el("span", { i18n: "network.include_domestic" })]);
    root.append(el("div", { class: "controls" }, [
      el("label", { class: "field" }, [el("span", { i18n: "network.view" }), viewSel]), colourField, ruleField,
      el("label", { class: "field" }, [el("span", { i18n: "network.as_of" }), asOf]), domField]));
    const plotNode = el("div", { class: "plot tall" });
    const note = el("p", { class: "legend-note" });
    const panel = el("div", { class: "side-panel" }, [el("p", { class: "muted", i18n: "network.click_hint" })]);
    root.append(el("div", { class: "grid", style: "grid-template-columns: minmax(0,3fr) minmax(240px,1fr)" }, [
      el("div", { class: "card" }, [plotNode, note]), el("div", { class: "card" }, [el("h2", { i18n: "network.details" }), panel])]));

    async function draw() {
      st.view = viewSel.value; st.colour = colourSel.value; st.rule = ruleSel.value; st.as_of = asOf.value; st.domestic = dom.checked;
      store("net.view", st.view); store("net.colour", st.colour); store("net.rule", st.rule);
      const isJ = st.view === "jurisdiction";
      colourField.hidden = isJ; ruleField.hidden = !isJ; domField.hidden = !isJ;
      const q = new URLSearchParams({ view: st.view, rule: st.rule, include_domestic: st.domestic });
      if (st.as_of) q.set("as_of", st.as_of);
      const v = await api("GET", `datasets/${S.datasetId}/view?${q}`);
      drawNetwork(plotNode, v, st, panel);
      note.replaceChildren(el("strong", { text: t("network.direction") + ": " }), t("dir." + v.meta.direction.replace(/[^a-z]+/g, "_")),
        "  ·  ", t("network.as_of") + ": " + (st.as_of || t("network.current")),
        v.excluded.length ? "  ·  " + t("network.excluded", { n: v.excluded.length }) : "");
    }
    [viewSel, colourSel, ruleSel, asOf, dom].forEach((c) => c.addEventListener("change", () => draw().catch(fail)));
    await draw();
  };

  function drawNetwork(node, v, st, panel) {
    const isJ = v.meta.view === "jurisdiction";
    const pos = Object.fromEntries(v.nodes.map((n) => [n.id, n]));
    const metric = (e) => (isJ ? e.weight : st.colour === "value" ? e.value_amount : e.fraction);
    const vals = v.edges.map(metric).filter((x) => x !== null && x !== undefined);
    const lo = vals.length ? Math.min(...vals) : 0, hi = vals.length ? Math.max(...vals) : 1;
    const norm = (x) => (hi > lo ? (x - lo) / (hi - lo) : 1);
    const colourAt = (x) => (x === null || x === undefined ? "#9ca3af" : RAMP[Math.min(RAMP.length - 1, Math.floor(norm(x) * (RAMP.length - 1) + 0.5))]);
    // Reciprocal edges (u -> v and v -> u) are offset sideways so that both stay visible.
    const keys = new Set(v.edges.map((e) => e.source + "\u0000" + e.target));
    const ends = (e) => {
      const a = pos[e.source], b = pos[e.target];
      if (!keys.has(e.target + "\u0000" + e.source)) return [a.x, a.y, b.x, b.y];
      const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1, k = isJ ? 0.035 : 0.018;
      return [a.x - (dy / len) * k, a.y + (dx / len) * k, b.x - (dy / len) * k, b.y + (dx / len) * k];
    };
    const traces = [];
    // Edges, grouped by colour bin so that thousands of edges stay fast.
    const groups = {};
    v.edges.forEach((e) => {
      const m = metric(e), c = colourAt(m);
      (groups[c] = groups[c] || { x: [], y: [], w: [] });
      const [ax, ay, bx, by] = ends(e);
      groups[c].x.push(ax, bx, null); groups[c].y.push(ay, by, null);
      groups[c].w.push(m === null || m === undefined ? 0.2 : norm(m));
    });
    Object.entries(groups).forEach(([c, g]) => {
      const avg = g.w.reduce((s, x) => s + x, 0) / g.w.length;
      traces.push({ type: "scatter", mode: "lines", x: g.x, y: g.y, hoverinfo: "skip", showlegend: false,
        line: { color: c, width: isJ ? 1.5 + 6 * avg : 1 + 2.5 * avg }, opacity: 0.85 });
    });
    // Edge midpoints carry hover text.
    traces.push({ type: "scatter", mode: "markers", showlegend: false, hoverinfo: "text",
      x: v.edges.map((e) => { const q = ends(e); return q[0] * 0.4 + q[2] * 0.6; }), y: v.edges.map((e) => { const q = ends(e); return q[1] * 0.4 + q[3] * 0.6; }),
      marker: { size: 7, color: v.edges.map((e) => colourAt(metric(e))), opacity: 0.01 },
      text: v.edges.map((e) => isJ
        ? `${e.source} → ${e.target}<br>${t("rule." + v.meta.rule)}: ${fmt(e.weight)}<br>${t("network.relations")}: ${e.relations}`
        : `${e.source} → ${e.target}<br>${t("col.fraction")}: ${e.fraction === null ? t("network.not_reported") : pct(e.fraction)}<br>${t("col.value_amount")}: ${e.value_amount === null ? t("network.not_reported") : fmt(e.value_amount) + " " + (e.value_currency || "")}<br>${e.relation_id}${e.share_class ? " · " + t("col.share_class") + " " + e.share_class : ""}`) });
    // Colour scale (invisible markers with a colour bar).
    if (vals.length) {
      traces.push({ type: "scatter", mode: "markers", x: [null], y: [null], hoverinfo: "skip", showlegend: false,
        marker: { colorscale: SCALE, cmin: lo, cmax: hi, color: [lo], showscale: true,
          colorbar: { title: { text: isJ ? t("rule." + v.meta.rule) : t("network.colour." + st.colour), side: "right" }, thickness: 12, len: 0.6,
            tickformat: !isJ && st.colour === "fraction" ? ".0%" : undefined } } });
    }
    // Nodes, one trace per jurisdiction so that the legend explains colours.
    const byJur = {};
    v.nodes.forEach((n) => { (byJur[n.jurisdiction_id] = byJur[n.jurisdiction_id] || []).push(n); });
    v.jurisdiction_order.forEach((j) => {
      const ns = byJur[j] || [];
      if (!ns.length) return;
      traces.push({ type: "scatter", mode: "markers", name: j, legendgroup: j, x: [null], y: [null], hoverinfo: "skip",
        marker: { size: 10, color: jurColour(j), symbol: "circle" } });
      traces.push({ type: "scatter", mode: isJ ? "markers+text" : "markers", name: j, legendgroup: j, showlegend: false,
        x: ns.map((n) => n.x), y: ns.map((n) => n.y),
        text: ns.map((n) => (isJ ? n.id : n.label)), textposition: ns.map((n) => (n.y < -0.2 ? "bottom center" : "top center")), customdata: ns.map((n) => n.id),
        hovertemplate: ns.map((n) => `<b>${escapeHtml(n.label || n.id)}</b><br>${n.id} · ${n.jurisdiction_id}${n.entity_type ? " · " + tOr("entity_type." + n.entity_type, n.entity_type) : ""}<br>${t("network.in_out", { i: n.in_degree, o: n.out_degree })}<extra></extra>`),
        marker: { size: ns.map((n) => (isJ ? 26 : 9 + Math.min(16, 2.2 * (n.in_degree + n.out_degree)))), color: jurColour(j),
          line: { width: 1.5, color: cssVar("--surface") || "#fff" }, symbol: ns.map((n) => (n.entity_type === "parent" ? "diamond" : "circle")) } });
    });
    // Arrowheads (capped for readability and speed).
    const arrows = v.edges.slice(0, 600).map((e) => {
      const [ax, ay, bx, by] = ends(e), f = isJ ? 0.9 : 0.88;
      return { x: ax * (1 - f) + bx * f, y: ay * (1 - f) + by * f, ax: ax * 0.3 + bx * 0.7, ay: ay * 0.3 + by * 0.7,
        xref: "x", yref: "y", axref: "x", ayref: "y", showarrow: true, arrowhead: 2, arrowsize: 1.1, arrowwidth: 1.4,
        arrowcolor: colourAt(metric(e)), text: "" };
    });
    const layout = { showlegend: true, hovermode: "closest", margin: { l: 10, r: 10, t: 30, b: 10 },
      xaxis: { visible: false, scaleanchor: "y" }, yaxis: { visible: false },
      legend: { orientation: "h", y: -0.02, title: { text: t("network.legend_jurisdictions") + "  " } },
      annotations: arrows.concat(watermark([statusWatermark()])) };
    plot(node, traces, layout, isJ
      ? { name: `jurisdiction_view_${v.meta.rule}`, columns: ["source", "target", "weight", "relations"], rows: v.edges }
      : { name: `${v.meta.view}_view_edges`, columns: ["relation_id", "source", "target", "fraction", "value_amount", "value_currency", "share_class", "source_id"], rows: v.edges });
    // One listener per chart; it always dispatches to the handler of the latest drawing.
    if (!node._tnlBound) { node.on("plotly_click", (ev) => node._tnlClick && node._tnlClick(ev)); node._tnlBound = true; }
    node._tnlClick = (ev) => {
      const p = ev.points && ev.points[0];
      if (!p || p.customdata === undefined) return;
      const n = pos[p.customdata];
      if (!n) return;
      const out = v.edges.filter((e) => e.source === n.id), inn = v.edges.filter((e) => e.target === n.id);
      const rows = Object.entries(n.attributes).filter(([, val]) => val !== null && val !== "" && val !== undefined);
      panel.replaceChildren(
        el("p", {}, [el("span", { class: "badge", style: "--c:" + jurColour(n.jurisdiction_id), text: n.jurisdiction_id }), "  ", el("strong", { text: n.label || n.id })]),
        el("dl", {}, rows.flatMap(([k, val]) => [el("dt", { text: tOr("col." + k, k) }), el("dd", { text: typeof val === "boolean" ? t(val ? "common.yes" : "common.no") : String(val) })])),
        el("p", { class: "muted small", text: t("network.edges_summary", { o: out.length, i: inn.length }) }),
        el("ul", { class: "small" }, out.concat(inn).slice(0, 30).map((e) => el("li", { text: `${e.source} → ${e.target}${e.fraction !== undefined && e.fraction !== null ? " · " + pct(e.fraction) : ""}${e.weight !== undefined ? " · " + fmt(e.weight) : ""}` }))));
    };
  }
  function escapeHtml(s) { return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

  // ------------------------------------------------------------------ matrix
  PAGES.matrix = async function (root) {
    header(root, "matrix.title", "matrix.lede");
    if (needDataset(root)) return;
    const ruleSel = el("select", { class: "select" }, ["count", "fraction_sum", "value_sum"].map((v) => el("option", { value: v, text: t("rule." + v) })));
    ruleSel.value = recall("matrix.rule") || "count";
    const dom = el("input", { type: "checkbox", checked: true });
    const plotNode = el("div", { class: "plot tall" });
    const note = el("p", { class: "legend-note" });
    root.append(el("div", { class: "controls" }, [el("label", { class: "field" }, [el("span", { i18n: "network.rule" }), ruleSel]),
      el("label", { class: "field inline" }, [dom, el("span", { i18n: "network.include_domestic" })])]),
    el("div", { class: "card" }, [plotNode, note]));
    async function draw() {
      store("matrix.rule", ruleSel.value);
      const m = await api("GET", `datasets/${S.datasetId}/matrix?rule=${ruleSel.value}&include_domestic=${dom.checked}`);
      const z = m.values.map((r) => r.map((x) => (x === 0 ? null : x)));
      plot(plotNode, [{ type: "heatmap", x: m.columns, y: m.rows, z, colorscale: SCALE, hoverongaps: false, xgap: 2, ygap: 2,
        texttemplate: ruleSel.value === "fraction_sum" ? "%{z:.2f}" : "%{z:,.0f}", textfont: { size: 11 },
        colorbar: { title: { text: t("rule." + m.meta.rule) }, thickness: 12 },
        hovertemplate: `${t("matrix.holder")}: %{y}<br>${t("matrix.held")}: %{x}<br>${t("rule." + m.meta.rule)}: %{z}<extra></extra>` }],
      { xaxis: { title: { text: t("matrix.held") }, side: "bottom", type: "category", showgrid: false }, yaxis: { title: { text: t("matrix.holder") }, type: "category", autorange: "reversed", showgrid: false },
        margin: { l: 90, r: 30, t: 34, b: 70 }, annotations: watermark([statusWatermark()]) },
      { name: `jurisdiction_matrix_${m.meta.rule}`, columns: ["holder"].concat(m.columns), rows: m.rows.map((r, i) => [r].concat(m.values[i])) });
      note.textContent = t("matrix.note", { rule: t("rule." + m.meta.rule) }) + (m.meta.currency ? "  ·  " + t("matrix.currency", { c: m.meta.currency }) : "")
        + (m.excluded.length ? "  ·  " + t("network.excluded", { n: m.excluded.length }) : "");
    }
    ruleSel.addEventListener("change", () => draw().catch(fail));
    dom.addEventListener("change", () => draw().catch(fail));
    await draw();
  };

  // ------------------------------------------------------------------ tax routes (live explorer, plan v2.2 s 8.1)
  const ROUTE_ENGINE = "vtrl2018.tax_routing";
  PAGES.routes = async function (root) {
    header(root, "routes.title", "routes.lede");
    if (needDataset(root)) return;
    const eng = S.engines.find((e) => e.engine_id === ROUTE_ENGINE);
    const dom = (await api("GET", `datasets/${S.datasetId}/tables/tax_domestic`)).rows;
    if (!eng || !dom.length) {
      root.append(el("div", { class: "card empty" }, [el("p", { i18n: "routes.no_tax_data" }), el("a", { href: "#/data", i18n: "nav.data" })]));
      return;
    }
    const treaties = (await api("GET", `datasets/${S.datasetId}/tables/tax_treaty_dividends`)).rows;
    const periods = [...new Set(dom.map((r) => r.period))].sort();
    const defaults = Object.fromEntries(eng.parameters.map((p) => [p.name, p.default]));
    const saved = (() => { try { return JSON.parse(recall("routes." + S.datasetId) || "null"); } catch (e) { return null; } })();
    const R = Object.assign({ period: periods[periods.length - 1], host: null, home: null, adjust: null, payer: null, recipient: null,
      settings: { penalty: defaults.penalty, tolerance: defaults.tolerance, max_intermediates: defaults.max_intermediates,
        world_average: defaults.world_average, centrality_weights: defaults.centrality_weights }, overrides: [] }, saved || {});
    if (!periods.includes(R.period)) R.period = periods[periods.length - 1];
    const codesFor = (per) => dom.filter((r) => r.period === per).map((r) => r.jurisdiction_id).sort();
    let codes = codesFor(R.period);
    const pick = (v, alt) => (codes.includes(v) ? v : alt);
    R.host = pick(R.host, codes[0]); R.home = pick(R.home, codes[codes.length - 1]);
    R.adjust = pick(R.adjust, codes[0]); R.payer = pick(R.payer, R.host); R.recipient = pick(R.recipient, codes.find((c) => c !== R.payer));
    let last = null, seq = 0, timer = null;
    const base = (j) => dom.find((r) => r.jurisdiction_id === j && r.period === R.period);
    const baseTreaty = (a, b) => treaties.find((r) => r.payer_jurisdiction === a && r.recipient_jurisdiction === b && r.period === R.period);
    const findOv = (o) => R.overrides.findIndex((x) => x.kind === o.kind && x.jurisdiction === o.jurisdiction && x.payer === o.payer && x.recipient === o.recipient);
    function setOverride(o, isBase) {
      const i = findOv(o);
      if (isBase) { if (i >= 0) R.overrides.splice(i, 1); } else if (i >= 0) R.overrides[i] = o; else R.overrides.push(o);
    }
    const ovValue = (o, fallback) => { const i = findOv(o); return i >= 0 ? R.overrides[i].value : fallback; };
    const effCit = (j) => ovValue({ kind: "cit", jurisdiction: j }, base(j).cit_rate);

    // ---- controls
    const sel = (opts, value, labeler) => { const x = el("select", { class: "select" }, opts.map((o) => el("option", { value: o, text: labeler ? labeler(o) : o }))); x.value = value; return x; };
    const nameOf = (j) => `${j} · ${(S.dataset.jurisdictionNames || {})[j] || ""}`;
    const hostSel = sel(codes, R.host, nameOf), homeSel = sel(codes, R.home, nameOf), periodSel = sel(periods, R.period);
    const swap = el("button", { class: "btn btn-ghost", text: "⇄", title: t("routes.swap"), onclick: () => { [hostSel.value, homeSel.value] = [homeSel.value, hostSel.value]; changed(); } });
    const adjustSel = sel(codes, R.adjust, nameOf);
    const slider = (min, max, step) => el("input", { type: "range", min, max, step, class: "slider" });
    const citS = slider(0, 0.6, 0.005), whtS = slider(0, 0.4, 0.005), treatyS = slider(0, 0.4, 0.005);
    const citV = el("output", { class: "mono" }), whtV = el("output", { class: "mono" }), treatyV = el("output", { class: "mono" });
    const reliefSel = sel(["exemption", "credit", "deduction"], "exemption", (m) => t("relief." + m));
    const payerSel = sel(codes, R.payer, nameOf), recipientSel = sel(codes, R.recipient, nameOf);
    const treatyOn = el("input", { type: "checkbox" });
    const chips = el("div", { class: "chips" });
    const status = el("p", { class: "muted small", style: "min-height:1.4em" });
    const settings = {
      penalty: el("input", { type: "number", min: 0, max: 0.01, step: 0.0001, value: R.settings.penalty }),
      tolerance: slider(0, 0.02, 0.0005), max_intermediates: sel(["1", "2", "3", "4", "5"], String(R.settings.max_intermediates)),
      world_average: sel(["unweighted", "gdp"], R.settings.world_average, (v) => t("routes.wa." + v)),
      centrality_weights: sel(["gdp_product", "unweighted"], R.settings.centrality_weights, (v) => t("routes.w." + v)),
    };
    settings.tolerance.value = R.settings.tolerance;
    const tolV = el("output", { class: "mono" });
    const question = el("textarea", { rows: 2, "data-i18n-placeholder": "runs.question_ph", placeholder: t("runs.question_ph") });
    const pinBtn = el("button", { class: "btn", i18n: "routes.pin", onclick: pin });
    const field = (key, ...kids) => el("label", { class: "field" }, [el("span", { i18n: key }), ...kids]);
    const row = (...kids) => el("div", { class: "slider-row" }, kids);

    const controls = el("div", { class: "card live-panel" }, [
      el("h2", { i18n: "routes.route" }),
      el("div", { class: "controls" }, [field("routes.host", hostSel), swap, field("routes.home", homeSel), periods.length > 1 ? field("routes.period", periodSel) : null]),
      el("h2", { i18n: "routes.adjust_title" }),
      field("routes.jurisdiction", adjustSel),
      field("routes.cit", row(citS, citV)), field("routes.wht", row(whtS, whtV)), field("routes.relief", reliefSel),
      el("h2", { style: "margin-top:14px", i18n: "routes.treaty_title" }),
      el("div", { class: "controls" }, [field("routes.payer", payerSel), field("routes.recipient", recipientSel)]),
      el("label", { class: "field inline" }, [treatyOn, el("span", { i18n: "routes.treaty_exists" })]),
      field("routes.treaty_rate", row(treatyS, treatyV)),
      el("h2", { style: "margin-top:14px", i18n: "routes.scenario" }), chips,
      el("details", {}, [el("summary", { i18n: "routes.settings" }),
        field("param.penalty", settings.penalty), field("param.tolerance", row(settings.tolerance, tolV)),
        field("param.max_intermediates", settings.max_intermediates), field("param.world_average", settings.world_average),
        field("param.centrality_weights", settings.centrality_weights)]),
      el("div", { class: "spacer" }), status,
      el("p", { class: "muted small", i18n: "routes.exploratory_note" }), question, el("div", { style: "height:8px" }), pinBtn,
    ]);
    const mapNode = el("div", { class: "plot tall" }), barNode = el("div", { class: "plot short" }), heatNode = el("div", { class: "plot" });
    const centNode = el("div", { class: "plot" }), sweepNode = el("div", { class: "plot short" });
    const legsBox = el("div"), headline = el("div", { class: "headline" });
    const sweepBtns = el("div", { class: "btn-row" }, [
      el("button", { class: "btn btn-ghost", i18n: "routes.sweep_cit", onclick: () => sweep("cit") }),
      el("button", { class: "btn btn-ghost", i18n: "routes.sweep_wht", onclick: () => sweep("wht") }),
      el("button", { class: "btn btn-ghost", i18n: "routes.sweep_treaty", onclick: () => sweep("treaty") })]);
    root.append(el("div", { class: "live-grid" }, [controls, el("div", { class: "grid" }, [
      el("div", { class: "card" }, [headline, mapNode, el("p", { class: "legend-note", i18n: "routes.map_note" })]),
      el("div", { class: "grid grid-2" }, [el("div", { class: "card" }, [el("h2", { i18n: "routes.decomposition" }), barNode]),
        el("div", { class: "card" }, [el("h2", { i18n: "routes.legs" }), legsBox])]),
      el("div", { class: "grid grid-2" }, [el("div", { class: "card" }, [el("h2", { i18n: "routes.shop_matrix" }), heatNode]),
        el("div", { class: "card" }, [el("h2", { i18n: "routes.centrality" }), centNode])]),
      el("div", { class: "card" }, [el("h2", { i18n: "routes.sweep" }), el("p", { class: "muted small", i18n: "routes.sweep_note" }), sweepBtns, sweepNode]),
    ])]));

    function syncControls() {
      const b = base(R.adjust);
      citS.value = effCit(R.adjust); citV.textContent = pct(Number(citS.value));
      whtS.value = ovValue({ kind: "wht", jurisdiction: R.adjust }, b.dividend_wht_rate); whtV.textContent = pct(Number(whtS.value));
      reliefSel.value = ovValue({ kind: "relief", jurisdiction: R.adjust }, b.relief_method);
      const bt = baseTreaty(R.payer, R.recipient);
      const tv = ovValue({ kind: "treaty", payer: R.payer, recipient: R.recipient }, bt ? bt.dividend_wht_rate : undefined);
      treatyOn.checked = tv !== null && tv !== undefined;
      treatyS.disabled = !treatyOn.checked;
      treatyS.value = treatyOn.checked ? tv : base(R.payer).dividend_wht_rate;
      treatyV.textContent = treatyOn.checked ? pct(Number(treatyS.value)) : t("routes.no_treaty");
      tolV.textContent = pct(Number(settings.tolerance.value));
      chips.replaceChildren(...(R.overrides.length ? R.overrides.map((o, i) => el("span", { class: "chip-ov" }, [describeOv(o),
        el("button", { class: "chip-x", title: t("routes.remove"), text: "×", onclick: () => { R.overrides.splice(i, 1); changed(true); } })])) : [el("span", { class: "muted small", i18n: "routes.no_overrides" })]),
      R.overrides.length ? el("button", { class: "btn btn-ghost", i18n: "routes.reset", onclick: () => { R.overrides = []; changed(true); } }) : "");
    }
    function describeOv(o) {
      const v = o.value === null ? t("routes.no_treaty") : typeof o.value === "number" ? pct(o.value) : t("relief." + o.value);
      if (o.kind === "treaty") return `${t("routes.ov.treaty")} ${o.payer} → ${o.recipient}: ${v}`;
      return `${t("routes.ov." + o.kind)} ${o.jurisdiction}: ${v}`;
    }
    function params(extra) {
      return Object.assign({ period: R.period, penalty: Number(settings.penalty.value), tolerance: Number(settings.tolerance.value),
        max_intermediates: Number(settings.max_intermediates.value), world_average: settings.world_average.value,
        centrality_weights: settings.centrality_weights.value, overrides: R.overrides.map((o) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== undefined))) }, extra || {});
    }
    function changed(immediate) {
      R.host = hostSel.value; R.home = homeSel.value; R.adjust = adjustSel.value; R.payer = payerSel.value; R.recipient = recipientSel.value;
      if (R.period !== periodSel.value) { R.period = periodSel.value; codes = codesFor(R.period); R.overrides = []; }
      R.settings = { penalty: Number(settings.penalty.value), tolerance: Number(settings.tolerance.value),
        max_intermediates: Number(settings.max_intermediates.value), world_average: settings.world_average.value, centrality_weights: settings.centrality_weights.value };
      store("routes." + S.datasetId, JSON.stringify(R));
      syncControls();
      clearTimeout(timer);
      timer = setTimeout(compute, immediate ? 0 : 160);
    }
    hostSel.addEventListener("change", () => changed(true)); homeSel.addEventListener("change", () => changed(true));
    periodSel.addEventListener("change", () => changed(true));
    adjustSel.addEventListener("change", () => changed(true));
    payerSel.addEventListener("change", () => changed(true)); recipientSel.addEventListener("change", () => changed(true));
    citS.addEventListener("input", () => { setOverride({ kind: "cit", jurisdiction: R.adjust, value: Number(citS.value) }, Math.abs(Number(citS.value) - base(R.adjust).cit_rate) < 1e-9); changed(); });
    whtS.addEventListener("input", () => { setOverride({ kind: "wht", jurisdiction: R.adjust, value: Number(whtS.value) }, Math.abs(Number(whtS.value) - base(R.adjust).dividend_wht_rate) < 1e-9); changed(); });
    reliefSel.addEventListener("change", () => { setOverride({ kind: "relief", jurisdiction: R.adjust, value: reliefSel.value }, reliefSel.value === base(R.adjust).relief_method); changed(true); });
    const treatyChanged = () => {
      if (R.payer === R.recipient) { toast(t("routes.same_pair")); return; }
      const bt = baseTreaty(R.payer, R.recipient);
      const value = treatyOn.checked ? Number(treatyS.value) : null;
      const isBase = bt ? value !== null && Math.abs(value - bt.dividend_wht_rate) < 1e-9 : value === null;
      setOverride({ kind: "treaty", payer: R.payer, recipient: R.recipient, value }, isBase);
      changed(!treatyOn.checked);
    };
    treatyOn.addEventListener("change", treatyChanged); treatyS.addEventListener("input", treatyChanged);
    Object.values(settings).forEach((c) => c.addEventListener(c.type === "range" ? "input" : "change", () => changed()));

    async function compute() {
      const my = ++seq;
      status.textContent = t("routes.computing");
      try {
        const res = await api("POST", `engines/${ROUTE_ENGINE}/preview`, { dataset_id: S.datasetId, parameters: params() });
        if (my !== seq) return; // a newer request superseded this one
        if (!res.executed) { status.replaceChildren(el("span", { class: "err-text", text: t("runs.blocked") })); legsBox.replaceChildren(issuesList(res.validation)); return; }
        last = res;
        status.textContent = t("routes.status", { ms: res.cached ? t("routes.cached") : fmt(res.elapsed_ms, 0) + " ms", status: t("status." + res.status) })
          + (res.warnings.length ? "  ·  " + res.warnings.join(" ") : "");
        draw(res);
      } catch (e) { if (my === seq) fail(e); }
    }

    function draw(res) {
      const pairs = res.outputs.pairs, cent = res.outputs.centrality;
      const pr = pairs.find((p) => p.host === R.host && p.home === R.home);
      const marks = watermark([t("wm.exploratory"), res.status !== "verified" ? t("wm.unverified") : null, statusWatermark()]);
      // headline
      if (R.host === R.home) headline.replaceChildren(el("p", { class: "muted", i18n: "routes.same_host_home" }));
      else if (!pr) headline.replaceChildren(el("p", { class: "err-text", i18n: "routes.no_route" }));
      else headline.replaceChildren(el("div", { class: "kpis" }, [
        kpi(t("routes.k.direct"), pct(pr.direct_te), "#94a3b8"), kpi(t("routes.k.best"), pct(pr.best_te), "#ef4444"),
        kpi(t("routes.k.gain"), pr.shop > 1e-12 ? pct(pr.shop) : "0", "#22c55e"),
        kpi(t("routes.k.route"), pr.best_route.split(">").join(" → "), "#8b5cf6")]));
      // route map
      const n = codes.length, pos = Object.fromEntries(codes.map((c, i) => [c, [Math.cos(Math.PI / 2 - 2 * Math.PI * i / n), Math.sin(Math.PI / 2 - 2 * Math.PI * i / n)]]));
      const gdp = Object.fromEntries((S.dataset.gdp || []).map((g) => [g.jurisdiction_id, g.value]));
      const gmax = Math.max(1, ...codes.map((c) => gdp[c] || 0));
      const cits = codes.map(effCit), cmin = Math.min(...cits), cmax = Math.max(...cits);
      const traces = [], ann = [];
      const legs = pr ? res.outputs.legs.filter((l) => l.host === R.host && l.home === R.home).sort((a, b) => a.leg - b.leg) : [];
      if (pr && pr.intermediates > 0) {
        const [ax, ay] = pos[R.host], [bx, by] = pos[R.home];
        traces.push({ type: "scatter", mode: "lines", x: [ax, bx], y: [ay, by], line: { color: "#94a3b8", width: 2, dash: "dash" }, hoverinfo: "skip", name: t("routes.direct_route") });
        ann.push({ x: (ax + bx) / 2, y: (ay + by) / 2, text: `${t("routes.direct")} ${pct(pr.direct_te)}`, showarrow: false, font: { size: 11, color: "#64748b" }, bgcolor: "rgba(255,255,255,0.7)" });
      }
      if (pr) {
        const dmax = Math.max(0.0001, ...legs.map((l) => l.d_leg));
        legs.forEach((l) => {
          const [x0, y0] = pos[l.from_jurisdiction], [x1, y1] = pos[l.to_jurisdiction];
          const c = RAMP[Math.min(RAMP.length - 1, Math.round((l.d_leg / dmax) * (RAMP.length - 1)))];
          traces.push({ type: "scatter", mode: "lines", x: [x0, x1], y: [y0, y1], line: { color: c, width: 6 }, hoverinfo: "text", showlegend: false,
            text: `${l.from_jurisdiction} → ${l.to_jurisdiction}<br>${t("relief." + l.relief_method)} · WHT ${pct(l.wht_rate)} (${t("routes.basis." + l.wht_basis)})<br>d = ${pct(l.d_leg)}` });
          ann.push({ x: x0 * 0.1 + x1 * 0.9, y: y0 * 0.1 + y1 * 0.9, ax: x0 * 0.35 + x1 * 0.65, ay: y0 * 0.35 + y1 * 0.65, xref: "x", yref: "y", axref: "x", ayref: "y",
            showarrow: true, arrowhead: 2, arrowsize: 1.3, arrowwidth: 2.5, arrowcolor: c, text: "" });
          ann.push({ x: (x0 + x1) / 2, y: (y0 + y1) / 2, text: `d ${pct(l.d_leg)}`, showarrow: false, font: { size: 12, color: c }, bgcolor: "rgba(255,255,255,0.8)", yshift: 12 });
        });
      }
      traces.push({ type: "scatter", mode: "markers+text", x: codes.map((c) => pos[c][0]), y: codes.map((c) => pos[c][1]), text: codes,
        textposition: codes.map((c) => (pos[c][1] < -0.2 ? "bottom center" : "top center")), showlegend: false, customdata: codes,
        hovertemplate: codes.map((c) => `<b>${escapeHtml(nameOf(c))}</b><br>CIT ${pct(effCit(c))} · WHT ${pct(ovValue({ kind: "wht", jurisdiction: c }, base(c).dividend_wht_rate))}<br>${t("relief." + ovValue({ kind: "relief", jurisdiction: c }, base(c).relief_method))}<extra></extra>`),
        marker: { size: codes.map((c) => 18 + 22 * Math.sqrt((gdp[c] || gmax / 4) / gmax)), color: cits, cmin, cmax: cmax > cmin ? cmax : cmin + 0.01, colorscale: SCALE,
          showscale: true, colorbar: { title: { text: t("routes.cit") }, tickformat: ".0%", thickness: 12, len: 0.6 },
          line: { width: codes.map((c) => (c === R.host || c === R.home ? 4 : 1.5)), color: codes.map((c) => (c === R.host ? "#ef4444" : c === R.home ? "#22c55e" : "#ffffff")) } } });
      plot(mapNode, traces, { showlegend: false, hovermode: "closest", margin: { l: 10, r: 10, t: 30, b: 10 }, xaxis: { visible: false, scaleanchor: "y", range: [-1.35, 1.35] },
        yaxis: { visible: false, range: [-1.3, 1.3] }, annotations: ann.concat(marks) }, { name: `route_${R.host}_${R.home}`, columns: LEGCOLS, rows: legs });
      mapNode._tnlClick = (ev) => { const p = ev.points && ev.points[0]; if (p && p.customdata && codes.includes(p.customdata)) { adjustSel.value = p.customdata; changed(true); } };
      if (!mapNode._tnlBound) { mapNode.on("plotly_click", (ev) => mapNode._tnlClick && mapNode._tnlClick(ev)); mapNode._tnlBound = true; }
      // decomposition: host CIT and repatriation tax, direct versus best
      if (pr) {
        const hostCit = effCit(R.host);
        const rows = [[t("routes.direct"), hostCit, (1 - hostCit) * pr.direct_d], [t("routes.best"), hostCit, (1 - hostCit) * pr.best_d]];
        plot(barNode, [
          { type: "bar", name: t("routes.part.host_cit"), x: rows.map((r) => r[0]), y: rows.map((r) => r[1]), marker: { color: "#6366f1" }, hovertemplate: "%{y:.2%}<extra>%{fullData.name}</extra>" },
          { type: "bar", name: t("routes.part.repatriation"), x: rows.map((r) => r[0]), y: rows.map((r) => r[2]), marker: { color: ["#f97316", "#ef4444"] }, hovertemplate: "%{y:.2%}<extra>%{fullData.name}</extra>" }],
        { barmode: "stack", yaxis: { tickformat: ".0%", title: { text: t("routes.axis.te") } }, annotations: marks },
        { name: `decomposition_${R.host}_${R.home}`, columns: ["route", "host_cit", "repatriation_tax"], rows: rows });
        legsBox.replaceChildren(renderTable(["leg", "from_jurisdiction", "to_jurisdiction", "relief_method", "wht_rate", "wht_basis", "payer_cit_used", "payer_cit_basis", "d_leg"],
          legs.map((l) => Object.assign({}, l, { relief_method: t("relief." + l.relief_method), wht_basis: t("routes.basis." + l.wht_basis), payer_cit_basis: t("routes.basis." + l.payer_cit_basis) }))),
        el("p", { class: "muted small", text: t("routes.pair_counts", { range: pr.routes_in_range, strict: pr.routes_strict }) }));
      }
      // treaty-shopping matrix
      const z = codes.map((h) => codes.map((m) => { const q = pairs.find((p) => p.host === h && p.home === m); return q ? q.shop : null; }));
      plot(heatNode, [{ type: "heatmap", x: codes, y: codes, z, colorscale: SCALE, zmin: 0, hoverongaps: false, xgap: 2, ygap: 2,
        colorbar: { title: { text: t("routes.shop") }, tickformat: ".1%", thickness: 12 }, texttemplate: codes.length <= 12 ? "%{z:.1%}" : "", textfont: { size: 10 },
        hovertemplate: `${t("routes.host")}: %{y}<br>${t("routes.home")}: %{x}<br>${t("routes.shop")}: %{z:.2%}<extra></extra>` }],
      { xaxis: { title: { text: t("routes.home") }, type: "category", showgrid: false }, yaxis: { title: { text: t("routes.host") }, type: "category", autorange: "reversed", showgrid: false },
        margin: { l: 80, r: 20, t: 34, b: 60 }, annotations: marks },
      { name: "treaty_shopping_gain", columns: ["host"].concat(codes), rows: codes.map((h, i) => [h].concat(z[i])) });
      heatNode._tnlClick = (ev) => { const p = ev.points && ev.points[0]; if (p && p.x !== p.y) { hostSel.value = p.y; homeSel.value = p.x; changed(true); } };
      if (!heatNode._tnlBound) { heatNode.on("plotly_click", (ev) => heatNode._tnlClick && heatNode._tnlClick(ev)); heatNode._tnlBound = true; }
      // centrality
      const order = cent.slice().sort((a, b) => b.btwns - a.btwns);
      plot(centNode, ["btwns", "strct", "occur"].map((m, k) => ({ type: "bar", name: t("routes.c." + m), x: order.map((r) => r.jurisdiction_id), y: order.map((r) => r[m]),
        marker: { color: ["#ef4444", "#8b5cf6", "#14b8a6"][k] } })), { barmode: "group", yaxis: { title: { text: t("routes.axis.centrality") } }, annotations: marks },
      { name: "conduit_centrality", columns: ["jurisdiction_id", "btwns", "strct", "occur", "unwtd"], rows: order });
    }
    const LEGCOLS = ["leg", "from_jurisdiction", "to_jurisdiction", "relief_method", "wht_rate", "wht_basis", "payer_cit_used", "payer_cit_basis", "recipient_cit", "d_leg"];

    async function sweep(kind) {
      if (R.host === R.home) return toast(t("routes.same_host_home"));
      const xs = [], direct = [], best = [], conduits = [];
      const target = kind === "treaty" ? { kind: "treaty", payer: R.payer, recipient: R.recipient } : { kind, jurisdiction: R.adjust };
      const hi = kind === "cit" ? 0.6 : 0.4;
      sweepNode.replaceChildren(el("p", { class: "muted small", text: t("routes.computing") }));
      try {
        for (let i = 0; i <= 24; i++) {
          const x = Math.round((hi * i / 24) * 10000) / 10000;
          const ov = R.overrides.filter((o) => !(o.kind === target.kind && o.jurisdiction === target.jurisdiction && o.payer === target.payer && o.recipient === target.recipient));
          ov.push(Object.assign({}, target, { value: x }));
          const res = await api("POST", `engines/${ROUTE_ENGINE}/preview`, { dataset_id: S.datasetId, parameters: params({ overrides: ov.map((o) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== undefined))) }) });
          if (!res.executed) { sweepNode.replaceChildren(issuesList(res.validation)); return; }
          const q = res.outputs.pairs.find((p) => p.host === R.host && p.home === R.home);
          xs.push(x); direct.push(q ? q.direct_te : null); best.push(q ? q.best_te : null); conduits.push(q ? q.best_route.split(">").slice(1, -1).join(" → ") || t("routes.direct") : "");
        }
      } catch (e) { fail(e); return; }
      sweepNode.replaceChildren();
      const label = kind === "treaty" ? `${t("routes.ov.treaty")} ${R.payer} → ${R.recipient}` : `${t("routes.ov." + kind)} ${R.adjust}`;
      plot(sweepNode, [
        { type: "scatter", mode: "lines", name: t("routes.direct"), x: xs, y: direct, line: { color: "#94a3b8", width: 2.5, dash: "dash" } },
        { type: "scatter", mode: "lines+markers", name: t("routes.best"), x: xs, y: best, text: conduits, line: { color: "#ef4444", width: 3 },
          marker: { size: 7, color: best, colorscale: SCALE }, hovertemplate: "%{x:.1%} → %{y:.2%}<br>%{text}<extra></extra>" }],
      { xaxis: { title: { text: label }, tickformat: ".0%" }, yaxis: { title: { text: t("routes.axis.te") }, tickformat: ".0%" },
        annotations: watermark([t("wm.exploratory"), t("wm.unverified"), statusWatermark()]) },
      { name: `sweep_${kind}`, columns: ["x", "direct_te", "best_te", "best_route_intermediates"], rows: xs.map((x, i) => [x, direct[i], best[i], conduits[i]]) });
    }

    async function pin() {
      pinBtn.disabled = true;
      try {
        const res = await api("POST", "runs", { engine_id: ROUTE_ENGINE, dataset_id: S.datasetId, parameters: params(), research_question: question.value });
        if (!res.executed) { toast(t("runs.blocked")); return; }
        toast(t("routes.pinned", { id: res.record.run_id }));
      } catch (e) { fail(e); } finally { pinBtn.disabled = false; }
    }
    function kpi(label, value, colour) { return el("div", { class: "card kpi", style: "--c:" + colour }, [el("div", { class: "value", text: value }), el("div", { class: "label", text: label })]); }
    syncControls();
    await compute();
  };

  // ------------------------------------------------------------------ data
  const TABLES = ["sources", "jurisdictions", "jurisdiction_attributes", "entities", "ownership", "illustrative_tax_edges",
    "tax_domestic", "tax_treaty_dividends", "tax_relief_overrides"];
  PAGES.data = async function (root) {
    header(root, "data.title", "data.lede");
    if (S.dataset) {
      let current = recall("data.table") || "ownership";
      const tabs = el("div", { class: "tabs" });
      const holder = el("div");
      const dl = el("button", { class: "btn btn-ghost", i18n: "data.download_csv", onclick: () => { location.href = `/api/datasets/${S.datasetId}/tables/${current}.csv`; } });
      async function show(name) {
        current = name; store("data.table", name);
        tabs.replaceChildren(...TABLES.map((tb) => el("button", { class: "tab" + (tb === name ? " active" : ""), text: `${t("table." + tb)} (${fmt(S.dataset.counts[tb], 0)})`, onclick: () => show(tb).catch(fail) })));
        const data = await api("GET", `datasets/${S.datasetId}/tables/${name}`);
        holder.replaceChildren(renderTable(data.columns, data.rows), data.truncated ? el("p", { class: "muted small", text: t("data.truncated", { shown: data.rows.length, total: data.total_rows }) }) : "");
      }
      root.append(el("div", { class: "card" }, [
        el("div", { class: "btn-row", style: "justify-content:space-between;align-items:center;margin-bottom:10px" }, [
          el("h2", { style: "margin:0", text: S.dataset.name }), dl]),
        el("p", { class: "muted small" }, [t("data.id") + ": ", el("code", { text: S.dataset.dataset_id }), "  ·  " + t("data.hash") + ": ", el("code", { text: S.dataset.content_hash.slice(0, 20) + "…" })]),
        tabs, holder]));
      await show(TABLES.includes(current) ? current : "ownership");
      root.append(el("div", { class: "spacer" }), el("div", { class: "card" }, [el("h2", { i18n: "data.validation" }), issuesList(S.dataset.validation)]));
    }
    root.append(el("div", { class: "spacer" }));
    root.append(el("div", { class: "grid grid-2" }, [synthForm(), importForm()]));
  };

  function renderTable(columns, rows, onRow) {
    if (!rows.length) return el("p", { class: "empty", i18n: "data.empty" });
    const isNum = (v) => typeof v === "number";
    return el("div", { class: "table-wrap" }, [el("table", {}, [
      el("thead", {}, [el("tr", {}, columns.map((c) => el("th", { text: tOr("col." + c, c) })))]),
      el("tbody", {}, rows.map((r) => el("tr", onRow ? { class: "clickable", onclick: () => onRow(r) } : {}, columns.map((c) => {
        const v = r[c];
        return el("td", { class: isNum(v) ? "num" : "", text: v === null || v === undefined ? "" : typeof v === "boolean" ? t(v ? "common.yes" : "common.no") : isNum(v) ? fmt(v, 4) : String(v) });
      })))),
    ])]);
  }

  function synthForm() {
    const f = { seed: el("input", { type: "number", value: 17, min: 0, step: 1 }), n_jurisdictions: el("input", { type: "number", value: 6, min: 2, max: 26 }),
      n_groups: el("input", { type: "number", value: 4, min: 1, max: 40 }), entities_per_group: el("input", { type: "number", value: 6, min: 2, max: 40 }),
      cross_holdings: el("input", { type: "number", value: 2, min: 0, max: 50 }) };
    const out = el("div");
    const btn = el("button", { class: "btn", i18n: "data.generate", onclick: async () => {
      btn.disabled = true;
      try {
        const params = Object.fromEntries(Object.entries(f).map(([k, inp]) => [k, Number(inp.value)]));
        const res = await api("POST", "datasets/synthetic", params);
        toast(t("data.generated", { name: res.name }));
        await loadDatasets(res.dataset_id); await route();
      } catch (e) { fail(e); } finally { btn.disabled = false; }
    } });
    return el("div", { class: "card" }, [el("h2", { i18n: "data.synthetic_title" }), el("p", { class: "muted small", i18n: "data.synthetic_lede" }),
      el("div", { class: "controls" }, Object.entries(f).map(([k, inp]) => el("label", { class: "field" }, [el("span", { i18n: "gen." + k }), inp]))), btn, out]);
  }

  function importForm() {
    const name = el("input", { type: "text", "data-i18n-placeholder": "data.import_name", placeholder: t("data.import_name") });
    const inputs = Object.fromEntries(TABLES.map((tb) => [tb, el("input", { type: "file", accept: ".csv,text/csv" })]));
    const out = el("div");
    const btn = el("button", { class: "btn", i18n: "data.import", onclick: async () => {
      btn.disabled = true; out.replaceChildren();
      try {
        const tables = {};
        for (const [tb, inp] of Object.entries(inputs)) if (inp.files[0]) tables[tb] = await inp.files[0].text();
        const res = await api("POST", "datasets/import", { name: name.value, tables });
        out.append(el("p", { class: res.saved ? "ok-text" : "err-text", text: res.saved ? t("data.import_ok", { id: res.dataset_id }) : t("data.import_blocked") }), issuesList(res.validation));
        if (res.saved) { await loadDatasets(res.dataset_id); toast(t("data.import_ok", { id: res.dataset_id })); }
      } catch (e) { fail(e); } finally { btn.disabled = false; }
    } });
    return el("div", { class: "card" }, [el("h2", { i18n: "data.import_title" }), el("p", { class: "muted small", i18n: "data.import_lede" }),
      el("div", { class: "controls" }, [el("label", { class: "field", style: "flex:1 1 100%" }, [el("span", { i18n: "data.import_name_label" }), name]),
        ...TABLES.map((tb) => el("label", { class: "field" }, [el("span", { text: t("table." + tb) + (["sources", "jurisdictions", "entities", "ownership"].includes(tb) ? " *" : "") }), inputs[tb]]))]),
      btn, out]);
  }

  // ------------------------------------------------------------------ runs
  PAGES.runs = async function (root) {
    header(root, "runs.title", "runs.lede");
    const runnable = S.engines.filter((e) => e.runnable);
    const engineSel = el("select", { class: "select" }, runnable.map((e) => el("option", { value: e.engine_id, text: e.display_name })));
    const question = el("textarea", { "data-i18n-placeholder": "runs.question_ph", placeholder: t("runs.question_ph") });
    const paramBox = el("div", { class: "controls" });
    const result = el("div");
    const history = el("div");
    let inputs = {};
    function renderParams() {
      const eng = S.engines.find((e) => e.engine_id === engineSel.value);
      inputs = {};
      paramBox.replaceChildren(...(eng ? eng.parameters : []).map((p) => {
        let inp;
        if (p.type === "choice") { inp = el("select", { class: "select" }, p.choices.map((c) => el("option", { value: c, text: tOr("choice." + c, c) }))); inp.value = p.default; }
        else if (p.type === "bool") inp = el("input", { type: "checkbox", checked: !!p.default });
        else if (p.type === "date") inp = el("input", { type: "date", value: p.default || "" });
        else if (p.type === "text") inp = el("input", { type: "text", value: p.default || "" });
        else if (p.type === "overrides") inp = el("textarea", { class: "mono", rows: 2, text: JSON.stringify(p.default || []) });
        else inp = el("input", { type: "number", value: p.default, min: p.minimum, max: p.maximum, step: p.type === "int" ? 1 : "any" });
        inputs[p.name] = { p, inp };
        return el("label", { class: "field", title: p.description }, [el("span", { text: tOr("param." + p.name, p.name) }), inp]);
      }));
    }
    engineSel.addEventListener("change", renderParams);
    renderParams();
    const btn = el("button", { class: "btn", i18n: "runs.execute", onclick: async () => {
      if (!S.datasetId) return toast(t("msg.no_dataset"));
      btn.disabled = true;
      try {
        const parameters = {};
        for (const [k, { p, inp }] of Object.entries(inputs)) {
          if (p.type === "bool") parameters[k] = inp.checked;
          else if (p.type === "float" || p.type === "int") parameters[k] = Number(inp.value);
          else if (p.type === "overrides") { try { parameters[k] = JSON.parse(inp.value || "[]"); } catch (e) { toast(t("runs.bad_json", { name: k })); return; } }
          else if (p.type === "text" || p.type === "date") parameters[k] = inp.value === "" ? null : inp.value;
          else parameters[k] = inp.value;
        }
        const res = await api("POST", "runs", { engine_id: engineSel.value, dataset_id: S.datasetId, parameters, research_question: question.value });
        if (!res.executed) { result.replaceChildren(el("div", { class: "card" }, [el("p", { class: "err-text", i18n: "runs.blocked" }), issuesList(res.validation)])); return; }
        showRun(result, res.record, res.outputs);
        await refreshHistory();
      } catch (e) { fail(e); } finally { btn.disabled = false; }
    } });
    root.append(el("div", { class: "card" }, [
      el("div", { class: "controls" }, [el("label", { class: "field" }, [el("span", { i18n: "runs.engine" }), engineSel])]),
      paramBox, el("label", { class: "field" }, [el("span", { i18n: "runs.question" }), question]), el("div", { class: "spacer" }), btn,
      el("p", { class: "muted small", i18n: "runs.interface_note" })]));
    root.append(el("div", { class: "spacer" }), result, el("div", { class: "spacer" }), el("div", { class: "card" }, [el("h2", { i18n: "runs.history" }), history]));
    async function refreshHistory() {
      const list = await api("GET", "runs");
      if (!list.length) { history.replaceChildren(el("p", { class: "empty", i18n: "runs.none" })); return; }
      history.replaceChildren(renderTable(["run_id", "started_utc", "engine_id", "status", "dataset_name", "outcome", "integrity", "stale"],
        list.map((r) => Object.assign({}, r, { stale: r.stale ? t("common.yes") : "", integrity: t("integrity." + r.integrity),
          status: t("status." + r.status), outcome: t("outcome." + r.outcome) })),
        async (r) => { try { const d = await api("GET", "runs/" + r.run_id); showRun(result, d.record, d.outputs); result.scrollIntoView({ behavior: "smooth" }); } catch (e) { fail(e); } }));
    }
    await refreshHistory();
  };

  function showRun(box, rec, outputs) {
    const replayOut = el("span", { class: "small" });
    const isDemo = rec.engine.track === "demonstration";
    const verified = ["verified", "replicated", "replicated_with_discrepancies", "robust", "empirically_tested"].includes(rec.engine.status);
    const parts = [
      el("div", { class: "btn-row", style: "justify-content:space-between;align-items:center" }, [
        el("h2", { style: "margin:0", text: t("runs.run_title", { id: rec.run_id }) }),
        el("div", { class: "btn-row" }, [
          el("button", { class: "btn btn-ghost", i18n: "runs.replay", onclick: async () => {
            replayOut.textContent = "…";
            try { const r = await api("POST", `runs/${rec.run_id}/replay`, {}); replayOut.className = r.match ? "ok-text small" : "err-text small"; replayOut.textContent = r.match ? t("runs.replay_match") : t("runs.replay_differs", { reason: r.reason }); }
            catch (e) { fail(e); }
          } }),
          el("a", { class: "btn btn-ghost", href: `/api/runs/${rec.run_id}/record.json`, i18n: "runs.download_record" })])]),
      replayOut,
      el("p", { class: "small" }, [el("span", { class: "badge", style: "--c:" + (STATUS_COLOURS[rec.engine.status] || "#64748b"), text: t("status." + rec.engine.status) }), "  ",
        t("track." + rec.engine.track), "  ·  ", t("runs.outcome") + ": ", el("strong", { text: t("outcome." + rec.outcome) }), "  ·  ", rec.dataset.name, " (", t("status." + rec.dataset.data_status), ")"]),
      el("p", { class: "muted small", text: rec.engine.boundary }),
    ];
    if (rec.warnings.length) parts.push(el("ul", { class: "small" }, rec.warnings.map((w) => el("li", { text: w }))));
    for (const [name, out] of Object.entries(outputs || {})) {
      if (!out.columns.includes("jurisdiction_id")) {
        parts.push(el("h2", { style: "margin-top:16px", text: tOr("output." + name, name) }),
          renderTable(out.columns, out.rows.slice(0, 500)),
          out.rows.length > 500 ? el("p", { class: "muted small", text: t("data.truncated", { shown: 500, total: out.rows.length }) }) : "",
          el("div", { class: "btn-row", style: "margin-top:8px" }, [el("a", { class: "btn btn-ghost", href: `/api/runs/${rec.run_id}/outputs/${name}.csv`, i18n: "runs.download_output" })]));
        continue;
      }
      const numeric = out.columns.filter((c) => out.rows.length && out.rows.every((r) => typeof r[c] === "number"));
      let linkCols = numeric.filter((c) => c.endsWith("_links")), valueCols = numeric.filter((c) => !c.endsWith("_links"));
      if (!linkCols.length) { linkCols = valueCols; valueCols = []; }
      const p1 = el("div", { class: "plot" }), p2 = el("div", { class: "plot" });
      parts.push(el("h2", { style: "margin-top:16px", text: tOr("output." + name, name) }), el("div", { class: "grid grid-2" }, [p1, p2]));
      const x = out.rows.map((r) => r.jurisdiction_id);
      const marks = watermark([isDemo ? t("wm.demonstration") : !verified ? t("wm.unverified") : null, rec.dataset.data_status === "synthetic" ? t("wm.synthetic") : null]);
      const ns = rec.engine.engine_id.split(".")[0];
      const cols = (list) => list.map((c, k) => ({ type: "bar", name: tOr("measure." + ns + "." + c, tOr("col." + c, c)), x, y: out.rows.map((r) => r[c]), marker: { color: PALETTE[(k + (list === valueCols ? 3 : 0)) % PALETTE.length] } }));
      setTimeout(() => {
        plot(p1, cols(linkCols), { barmode: "group", annotations: marks, yaxis: { title: { text: valueCols.length ? t("runs.axis.links") : "" } } }, { name: `${rec.run_id}_${name}`, columns: ["jurisdiction_id"].concat(linkCols), rows: out.rows });
        if (!valueCols.length) { p2.remove(); return; }
        plot(p2, cols(valueCols).map((tr) => (tr.name === tOr("measure.demo.net_outbound_value", "net_outbound_value")
          ? Object.assign(tr, { type: "bar", marker: { color: out.rows.map((r) => (r.net_outbound_value >= 0 ? "#22c55e" : "#ef4444")) } }) : tr)),
        { barmode: "group", annotations: marks, yaxis: { title: { text: t("runs.axis.value") } }, showlegend: true }, { name: `${rec.run_id}_${name}_values`, columns: ["jurisdiction_id"].concat(valueCols), rows: out.rows });
      }, 0);
      parts.push(el("div", { class: "spacer" }), renderTable(out.columns, out.rows),
        el("div", { class: "btn-row", style: "margin-top:8px" }, [el("a", { class: "btn btn-ghost", href: `/api/runs/${rec.run_id}/outputs/${name}.csv`, i18n: "runs.download_output" })]));
    }
    parts.push(el("details", {}, [el("summary", { i18n: "runs.trace" }), renderTable(["step", "description", "detail", "result"], rec.trace)]));
    parts.push(el("details", {}, [el("summary", { i18n: "runs.record" }), el("pre", { class: "json", text: JSON.stringify(rec, null, 2) })]));
    box.replaceChildren(el("div", { class: "card" }, parts));
    applyI18n(box);
  }

  // ------------------------------------------------------------------ methods
  PAGES.methods = async function (root) {
    header(root, "methods.title", "methods.lede");
    root.append(el("div", { class: "grid grid-2" }, S.engines.map((e) => el("div", { class: "card" }, [
      el("div", { class: "btn-row", style: "justify-content:space-between;align-items:flex-start" }, [el("h2", { text: e.display_name }),
        el("span", { class: "badge", style: "--c:" + (STATUS_COLOURS[e.status] || "#64748b"), text: t("status." + e.status) })]),
      el("p", { class: "small muted", text: t("track." + e.track) + "  ·  " + e.engine_id + "  ·  v" + e.version }),
      el("p", { text: e.purpose }),
      el("dl", { class: "side-panel" }, [el("dt", { i18n: "methods.boundary" }), el("dd", { text: e.boundary }), el("dt", { i18n: "methods.spec" }), el("dd", { text: e.spec_ref }),
        el("dt", { i18n: "methods.next" }), el("dd", { text: e.next_step }), el("dt", { i18n: "methods.inputs" }), el("dd", { text: e.input_schema.join(", ") })]),
      e.measures.length ? el("details", {}, [el("summary", { i18n: "methods.measures" }), renderTable(["name", "definition", "numerator", "denominator", "unit"], e.measures)]) : null,
    ]))));
    root.append(el("div", { class: "spacer" }), el("div", { class: "card" }, [el("h2", { i18n: "methods.ladder" }), el("p", { class: "muted small", i18n: "methods.ladder_text" }),
      el("div", { class: "btn-row" }, Object.entries(STATUS_COLOURS).map(([k, c]) => el("span", { class: "badge", style: "--c:" + c, text: t("status." + k) })))]));
  };

  // ------------------------------------------------------------------ about
  PAGES.about = async function (root) {
    header(root, "about.title", "about.lede");
    const a = await api("GET", "about");
    const env = a.environment;
    const rows = [["about.version", a.version], ["about.workspace", a.workspace], ["about.python", env.python], ["about.platform", env.platform],
      ["about.frozen", t(env.frozen ? "common.yes" : "common.no")], ["about.exe_hash", env.executable_sha256 || t("common.none")],
      ["about.commit", (env.git && env.git.commit) || t("common.none")], ["about.lock", env.lock_sha256 || t("common.none")], ["about.built", env.built_utc || t("common.none")], ["about.licence", a.licence]];
    root.append(el("div", { class: "card side-panel" }, [el("dl", {}, rows.flatMap(([k, v]) => [el("dt", { i18n: k }), el("dd", {}, [el("code", { text: String(v) })])]))]));
    root.append(el("div", { class: "spacer" }), el("div", { class: "card" }, [el("h2", { i18n: "about.languages" }), el("p", { class: "muted small", i18n: "about.languages_text" }),
      el("ul", {}, S.locales.map((l) => el("li", { text: `${l.native_name} (${l.tag})${l.complete ? "" : " · " + t("about.incomplete")}` })))]));
    root.append(el("div", { class: "spacer" }), el("div", { class: "card" }, [el("h2", { i18n: "about.notice_title" }), el("p", { class: "small", i18n: "about.notice" })]));
  };

  // ------------------------------------------------------------------ boot
  async function boot() {
    const loc = await api("GET", "locales");
    S.locales = loc.locales;
    const want = recall("locale");
    const browser = (navigator.languages || [navigator.language || ""]);
    const tags = S.locales.map((l) => l.tag);
    const pick = (want && tags.includes(want)) ? want : (browser.find((b) => tags.includes(b)) || loc.default);
    const lsel = document.getElementById("locale-select");
    lsel.replaceChildren(...S.locales.map((l) => el("option", { value: l.tag, text: l.native_name })));
    lsel.value = pick;
    await loadLocale(pick);
    lsel.addEventListener("change", async () => { try { await loadLocale(lsel.value); await loadDataset(); await route(); } catch (e) { fail(e); } });
    S.engines = await api("GET", "engines");
    await loadDatasets();
    document.getElementById("dataset-select").addEventListener("change", async (ev) => {
      S.datasetId = ev.target.value; try { await loadDataset(); await route(); } catch (e) { fail(e); } });
    document.getElementById("quit-btn").addEventListener("click", async () => {
      try { await api("POST", "quit", {}); } catch (e) { /* server already stopping */ }
      document.body.replaceChildren(el("div", { class: "empty", style: "padding:80px" }, [el("h1", { text: t("quit.done") }), el("p", { text: t("quit.close_tab") })]));
    });
    window.addEventListener("hashchange", route);
    await route();
  }
  boot().catch((e) => { console.error(e); document.getElementById("page").textContent = "Failed to start: " + e.message; });
})();
