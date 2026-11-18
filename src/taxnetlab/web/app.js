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
  const S = { mode: "plain", strings: {}, locale: "en-GB", locales: [], datasets: [], datasetId: null, dataset: null, engines: [],
    page: "overview", jurColour: {} };

  // ------------------------------------------------------------------ i18n
  function t(key, params) {
    // Reading modes (plan s 8): a key may have a ".plain" or ".tech" variant that takes precedence in that mode.
    const variant = key + (S.mode === "technical" ? ".tech" : ".plain");
    let s = has(variant) ? S.strings[variant] : has(key) ? S.strings[key] : key;
    if (params) s = s.replace(/\{(\w+)\}/g, (m, k) => (params[k] === undefined || params[k] === null ? m : String(params[k])));
    return s;
  }
  function has(key) { return Object.prototype.hasOwnProperty.call(S.strings, key); }
  function tOr(key, fallback, params) { return has(key) || has(key + ".plain") || has(key + ".tech") ? t(key, params) : fallback; }
  // Chart guidance: open in Plain English mode, folded away in Technical mode.
  function guide(id) {
    const plain = S.mode !== "technical";
    const box = el("details", { class: "guide" + (plain ? " plain" : ""), open: plain }, [
      el("summary", { i18n: plain ? "guide.summary.plain" : "guide.summary.tech" }),
      el("p", { "data-i18n": "guide." + id, text: t("guide." + id) })]);
    return box;
  }
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
  // Publication style (plan Phase 8): white background, serif type, black ink; watermarks are kept.
  async function publicationFigure(gd, name) {
    const box = el("div", { style: "position:fixed;left:-10000px;top:0;width:1200px;height:800px" });
    document.body.append(box);
    try {
      const ax = { gridcolor: "#d9d9d9", zerolinecolor: "#999", linecolor: "#111", tickfont: { color: "#111" }, title: {} };
      const layout = JSON.parse(JSON.stringify(gd.layout));
      Object.assign(layout, { paper_bgcolor: "#ffffff", plot_bgcolor: "#ffffff", width: 1200, height: 800,
        font: { family: "Times New Roman, Times, serif", size: 16, color: "#111111" } });
      for (const k of Object.keys(layout)) if (/^[xy]axis\d*$/.test(k)) layout[k] = Object.assign({}, layout[k], ax, { title: layout[k].title });
      await Plotly.newPlot(box, JSON.parse(JSON.stringify(gd.data)), layout, { staticPlot: true });
      await Plotly.downloadImage(box, { format: "svg", width: 1200, height: 800, filename: name + "_publication" });
    } catch (e) { fail(e); } finally { Plotly.purge(box); box.remove(); }
  }

  function plot(node, traces, layout, csv) {
    const svgIcon = { width: 1000, height: 1000, path: "M200 100h400l200 200v600H200z M600 100v200h200 M330 520h340M330 640h340M330 760h220" };
    const buttons = [{ name: t("chart.download_svg"), icon: svgIcon, click: (gd) => Plotly.downloadImage(gd, { format: "svg", filename: csv ? csv.name : "chart" }) },
      { name: t("chart.download_publication"), icon: { width: 1000, height: 1000, path: "M150 150h700v700H150z M250 650l150-200 120 140 90-110 140 170" },
        click: (gd) => publicationFigure(gd, csv ? csv.name : "chart") }];
    if (csv) buttons.push({ name: t("chart.download_csv"), icon: Plotly.Icons.disk, click: () => download(csv.name + ".csv", csvOf(csv.columns, csv.rows)) });
    node.setAttribute("role", "img");
    node.setAttribute("aria-label", t("a11y.chart", { name: (csv && csv.name ? csv.name : "chart").replace(/_/g, " ") }));
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
      el("div", { class: "card" }, [el("h2", { i18n: "overview.chart.entities" }), guide("overview.entities"), p1]),
      el("div", { class: "card" }, [el("h2", { i18n: "overview.chart.fractions" }), guide("overview.fractions"), p2]),
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

    const prov = provenanceCard(d);
    if (prov) root.append(el("div", { class: "spacer" }), prov);
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
      el("div", { class: "card" }, [guide("network.graph"), plotNode, note]), el("div", { class: "card" }, [el("h2", { i18n: "network.details" }), panel])]));

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
    el("div", { class: "card" }, [guide("matrix.heatmap"), plotNode, note]));
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
        world_average: defaults.world_average, centrality_weights: defaults.centrality_weights }, overrides: [],
      elig: { eligibility: defaults.eligibility, holding_fraction: defaults.holding_fraction, holding_days: defaults.holding_days,
        assume_beneficial_ownership: defaults.assume_beneficial_ownership, assume_ppt: defaults.assume_ppt, assume_lob: defaults.assume_lob } }, saved || {});
    if (!R.elig) R.elig = { eligibility: defaults.eligibility, holding_fraction: defaults.holding_fraction, holding_days: defaults.holding_days,
      assume_beneficial_ownership: defaults.assume_beneficial_ownership, assume_ppt: defaults.assume_ppt, assume_lob: defaults.assume_lob };
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
    // Treaty conditions (rule layer, docs/specs/eligibility.md): the source assumes every treaty benefit applies.
    const assumeSel = (v) => sel(["unresolved", "met", "not_met"], v, (x) => t("choice." + x));
    const elig = {
      eligibility: sel(["assume_eligible", "strict", "contingent"], R.elig.eligibility, (v) => t("choice." + v)),
      holding_fraction: slider(0, 1, 0.01), holding_days: el("input", { type: "number", min: 0, max: 36500, step: 1, value: R.elig.holding_days }),
      assume_beneficial_ownership: assumeSel(R.elig.assume_beneficial_ownership), assume_ppt: assumeSel(R.elig.assume_ppt), assume_lob: assumeSel(R.elig.assume_lob),
    };
    elig.holding_fraction.value = R.elig.holding_fraction;
    const holdV = el("output", { class: "mono" });
    const eligFacts = el("div", {}, [field("param.holding_fraction", row(elig.holding_fraction, holdV)), field("param.holding_days", elig.holding_days),
      field("param.assume_beneficial_ownership", elig.assume_beneficial_ownership), field("param.assume_ppt", elig.assume_ppt), field("param.assume_lob", elig.assume_lob)]);

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
      el("h2", { style: "margin-top:14px", i18n: "routes.conditions_title" }), field("param.eligibility", elig.eligibility),
      el("p", { class: "muted small", i18n: "routes.conditions_note" }), eligFacts,
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
      el("div", { class: "card" }, [headline, guide("routes.map"), mapNode, el("p", { class: "legend-note", i18n: "routes.map_note" })]),
      el("div", { class: "grid grid-2" }, [el("div", { class: "card" }, [el("h2", { i18n: "routes.decomposition" }), guide("routes.decomposition"), barNode]),
        el("div", { class: "card" }, [el("h2", { i18n: "routes.legs" }), legsBox])]),
      el("div", { class: "grid grid-2" }, [el("div", { class: "card" }, [el("h2", { i18n: "routes.shop_matrix" }), guide("routes.shop"), heatNode]),
        el("div", { class: "card" }, [el("h2", { i18n: "routes.centrality" }), guide("routes.centrality"), centNode])]),
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
      holdV.textContent = pct(Number(elig.holding_fraction.value));
      eligFacts.hidden = elig.eligibility.value === "assume_eligible";
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
        centrality_weights: settings.centrality_weights.value, overrides: R.overrides.map((o) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== undefined))),
        eligibility: elig.eligibility.value, holding_fraction: Number(elig.holding_fraction.value), holding_days: Number(elig.holding_days.value),
        assume_beneficial_ownership: elig.assume_beneficial_ownership.value, assume_ppt: elig.assume_ppt.value, assume_lob: elig.assume_lob.value }, extra || {});
    }
    function changed(immediate) {
      R.host = hostSel.value; R.home = homeSel.value; R.adjust = adjustSel.value; R.payer = payerSel.value; R.recipient = recipientSel.value;
      if (R.period !== periodSel.value) { R.period = periodSel.value; codes = codesFor(R.period); R.overrides = []; }
      R.settings = { penalty: Number(settings.penalty.value), tolerance: Number(settings.tolerance.value),
        max_intermediates: Number(settings.max_intermediates.value), world_average: settings.world_average.value, centrality_weights: settings.centrality_weights.value };
      R.elig = { eligibility: elig.eligibility.value, holding_fraction: Number(elig.holding_fraction.value), holding_days: Number(elig.holding_days.value),
        assume_beneficial_ownership: elig.assume_beneficial_ownership.value, assume_ppt: elig.assume_ppt.value, assume_lob: elig.assume_lob.value };
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
    Object.values(elig).forEach((c) => c.addEventListener(c.type === "range" ? "input" : "change", () => changed(c.tagName === "SELECT")));

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
        kpi(t("routes.k.route"), pr.best_route.split(">").join(" → "), "#8b5cf6"),
        res.outputs.legs.some((l) => l.host === R.host && l.home === R.home && l.wht_basis === "treaty_contingent")
          ? kpi(t("routes.k.contingent"), t("routes.k.contingent_value"), "#f59e0b") : null]));
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

  // ------------------------------------------------------------------ conduits and sinks (live explorer)
  const GB_ENGINE = "gb2017.conduits_sinks";
  PAGES.conduits = async function (root) {
    header(root, "conduits.title", "conduits.lede");
    if (needDataset(root)) return;
    const eng = S.engines.find((e) => e.engine_id === GB_ENGINE);
    const fin = (await api("GET", `datasets/${S.datasetId}/tables/entity_financials`)).rows;
    if (!eng || !fin.length) {
      root.append(el("div", { class: "card empty" }, [el("p", { i18n: "conduits.no_revenue" }), el("a", { href: "#/data", i18n: "nav.data" })]));
      return;
    }
    const d = Object.fromEntries(eng.parameters.map((p) => [p.name, p.default]));
    const saved = (() => { try { return JSON.parse(recall("conduits." + S.datasetId) || "null"); } catch (e) { return null; } })();
    const C = Object.assign({ logThreshold: Math.log10(d.ownership_threshold), normalise: d.normalise_missing_shareholders,
      sink: d.sink_threshold, conduit: d.conduit_threshold, denominator: d.conduit_denominator }, saved || {});
    const slider = (min, max, step, value) => { const x = el("input", { type: "range", min, max, step, class: "slider" }); x.value = value; return x; };
    const ownS = slider(-5, -1, 0.25, C.logThreshold), sinkS = slider(0, 50, 0.5, C.sink), condS = slider(0, 10, 0.1, C.conduit);
    const ownV = el("output", { class: "mono" }), sinkV = el("output", { class: "mono" }), condV = el("output", { class: "mono" });
    const norm = el("input", { type: "checkbox", checked: !!C.normalise });
    const denom = el("select", { class: "select" }, ["subset_total", "all_g3"].map((v) => el("option", { value: v, text: t("choice." + v) })));
    denom.value = C.denominator;
    const status = el("p", { class: "muted small", style: "min-height:1.4em" });
    const question = el("textarea", { rows: 2, "data-i18n-placeholder": "runs.question_ph", placeholder: t("runs.question_ph") });
    const pinBtn = el("button", { class: "btn", i18n: "routes.pin", onclick: pin });
    const field = (key, ...kids) => el("label", { class: "field" }, [el("span", { i18n: key }), ...kids]);
    const row = (...kids) => el("div", { class: "slider-row" }, kids);
    root.append(el("div", { class: "live-grid" }, [
      el("div", { class: "card live-panel" }, [
        el("h2", { i18n: "conduits.settings" }),
        field("param.ownership_threshold", row(ownS, ownV)),
        el("label", { class: "field inline" }, [norm, el("span", { i18n: "param.normalise_missing_shareholders" })]),
        field("param.sink_threshold", row(sinkS, sinkV)), field("param.conduit_threshold", row(condS, condV)),
        field("param.conduit_denominator", denom),
        el("div", { class: "spacer" }), status, el("p", { class: "muted small", i18n: "routes.exploratory_note" }), question,
        el("div", { style: "height:8px" }), pinBtn]),
      el("div", { class: "grid" }, [
        el("div", { class: "card" }, [el("div", { class: "headline", id: "gb-head" }), guide("conduits.scatter"), el("div", { class: "plot tall", id: "gb-scatter" })]),
        el("div", { class: "grid grid-2" }, [
          el("div", { class: "card" }, [el("h2", { i18n: "conduits.sink_chart" }), guide("conduits.sink"), el("div", { class: "plot", id: "gb-sink" })]),
          el("div", { class: "card" }, [el("h2", { i18n: "conduits.flow_chart" }), guide("conduits.sankey"), el("div", { class: "plot", id: "gb-sankey" })])]),
        el("div", { class: "card" }, [el("h2", { i18n: "conduits.table" }), el("div", { id: "gb-table" })]),
      ])]));
    let seq = 0, timer = null;
    const params = () => ({ ownership_threshold: Math.pow(10, Number(ownS.value)), normalise_missing_shareholders: norm.checked,
      sink_threshold: Number(sinkS.value), conduit_threshold: Number(condS.value), conduit_denominator: denom.value });
    function sync() {
      ownV.textContent = fmt(Math.pow(10, Number(ownS.value)), 5); sinkV.textContent = fmt(Number(sinkS.value), 1); condV.textContent = fmt(Number(condS.value), 1);
      store("conduits." + S.datasetId, JSON.stringify({ logThreshold: Number(ownS.value), normalise: norm.checked, sink: Number(sinkS.value),
        conduit: Number(condS.value), denominator: denom.value }));
    }
    function changed(now) { sync(); clearTimeout(timer); timer = setTimeout(compute, now ? 0 : 160); }
    [ownS, sinkS, condS].forEach((x) => x.addEventListener("input", () => changed()));
    [norm, denom].forEach((x) => x.addEventListener("change", () => changed(true)));
    async function compute() {
      const my = ++seq;
      status.textContent = t("routes.computing");
      try {
        const res = await api("POST", `engines/${GB_ENGINE}/preview`, { dataset_id: S.datasetId, parameters: params() });
        if (my !== seq) return;
        if (!res.executed) { status.replaceChildren(el("span", { class: "err-text", i18n: "runs.blocked" })); document.getElementById("gb-table").replaceChildren(issuesList(res.validation)); return; }
        status.textContent = t("routes.status", { ms: res.cached ? t("routes.cached") : fmt(res.elapsed_ms, 0) + " ms", status: t("status." + res.status) })
          + (res.warnings.length ? "  ·  " + res.warnings.join(" ") : "");
        draw(res);
      } catch (e) { if (my === seq) fail(e); }
    }
    function draw(res) {
      const rows = res.outputs.jurisdictions, marks = watermark([t("wm.exploratory"), res.status !== "verified" ? t("wm.unverified") : null, statusWatermark()]);
      const sum = Object.fromEntries(res.outputs.summary.map((r) => [r.measure, r.value]));
      const sinks = rows.filter((r) => r.is_sink).map((r) => r.jurisdiction_id), conduits = rows.filter((r) => r.is_conduit).map((r) => r.jurisdiction_id);
      document.getElementById("gb-head").replaceChildren(el("div", { class: "kpis" }, [
        kpiBox(t("conduits.k.sinks"), sinks.join(", ") || t("conduits.none"), "#ef4444"),
        kpiBox(t("conduits.k.conduits"), conduits.join(", ") || t("conduits.none"), "#8b5cf6"),
        kpiBox(t("conduits.k.chains"), `${fmt(sum.g2_chains, 0)} · ${fmt(sum.g3_chains, 0)}`, "#14b8a6"),
        kpiBox(t("conduits.k.paths"), fmt(sum.firm_paths_kept, 0), "#f59e0b")]));
      // conduit map: outward (x) against inward (y), log axes, threshold quadrant
      const floor = 0.01, thr = Number(condS.value) || floor;
      const pos = (v) => (v === null || v === undefined || v <= floor ? floor : v);
      const sc = rows.map((r) => r.sink_centrality ?? 0), smax = Math.max(1, ...sc.map(Math.abs));
      const gmax = Math.max(1, ...rows.map((r) => r.gdp || 0));
      const ymax = Math.max(thr * 10, ...rows.map((r) => pos(r.conduit_in))) * 1.6, xmax = Math.max(thr * 10, ...rows.map((r) => pos(r.conduit_out))) * 1.6;
      plot(document.getElementById("gb-scatter"), [{ type: "scatter", mode: "markers+text", x: rows.map((r) => pos(r.conduit_out)), y: rows.map((r) => pos(r.conduit_in)),
        // Jurisdictions with no conduit role are pinned to the floor; their labels are dropped to avoid clutter.
        text: rows.map((r) => (pos(r.conduit_in) > floor || pos(r.conduit_out) > floor ? r.jurisdiction_id : "")),
        textposition: "top center", customdata: rows.map((r) => [r.sink_centrality, r.conduit_in, r.conduit_out, r.jurisdiction_id]),
        hovertemplate: `<b>%{customdata[3]}</b><br>${t("col.conduit_in")}: %{customdata[1]:.3f}<br>${t("col.conduit_out")}: %{customdata[2]:.3f}<br>${t("col.sink_centrality")}: %{customdata[0]:.3f}<extra></extra>`,
        marker: { size: rows.map((r) => 14 + 26 * Math.sqrt((r.gdp || 0) / gmax)), color: sc, cmin: -smax, cmax: smax, colorscale: "RdBu", reversescale: false,
          showscale: true, colorbar: { title: { text: t("col.sink_centrality") }, thickness: 12 },
          line: { width: rows.map((r) => (r.is_conduit ? 4 : r.is_sink ? 3 : 1)), color: rows.map((r) => (r.is_conduit ? "#8b5cf6" : r.is_sink ? "#ef4444" : "#ffffff")) } } }],
      { xaxis: { type: "log", dtick: 1, title: { text: t("conduits.axis.out") }, range: [Math.log10(floor) - 0.2, Math.log10(xmax)] },
        yaxis: { type: "log", dtick: 1, title: { text: t("conduits.axis.in") }, range: [Math.log10(floor) - 0.2, Math.log10(ymax)] },
        shapes: [{ type: "rect", xref: "x", yref: "y", x0: thr, x1: xmax, y0: thr, y1: ymax, fillcolor: "rgba(139,92,246,0.08)", line: { width: 0 } },
          { type: "line", xref: "x", yref: "paper", x0: thr, x1: thr, y0: 0, y1: 1, line: { color: "#8b5cf6", dash: "dot", width: 1.5 } },
          { type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: thr, y1: thr, line: { color: "#8b5cf6", dash: "dot", width: 1.5 } }],
        annotations: marks.concat([{ xref: "x", yref: "y", x: Math.log10(xmax) - 0.05, y: Math.log10(ymax) - 0.05, text: t("conduits.quadrant"), showarrow: false,
          xanchor: "right", yanchor: "top", font: { color: "#8b5cf6", size: 12 } }]) },
      { name: "conduit_centrality", columns: ["jurisdiction_id", "conduit_in", "conduit_out", "sink_centrality", "is_conduit", "is_sink"], rows });
      // sink centrality bars with the threshold
      const order = rows.slice().sort((a, b) => (b.sink_centrality ?? -1e9) - (a.sink_centrality ?? -1e9));
      plot(document.getElementById("gb-sink"), [{ type: "bar", x: order.map((r) => r.jurisdiction_id), y: order.map((r) => r.sink_centrality),
        marker: { color: order.map((r) => (r.is_sink ? "#ef4444" : (r.sink_centrality ?? 0) >= 0 ? "#f97316" : "#2563eb")) },
        hovertemplate: "%{x}: %{y:.3f}<extra></extra>" }],
      { yaxis: { title: { text: t("col.sink_centrality") } }, showlegend: false, annotations: marks,
        shapes: [{ type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: Number(sinkS.value), y1: Number(sinkS.value), line: { color: "#ef4444", dash: "dot", width: 1.5 } }] },
      { name: "sink_centrality", columns: ["jurisdiction_id", "sink_centrality", "is_sink", "value_in", "value_out", "gdp"], rows: order });
      // flows through three-country chains: origin -> conduit -> destination
      const g3 = res.outputs.country_chains.filter((c) => c.countries === 3).sort((a, b) => b.value - a.value).slice(0, 60);
      const sankeyNode = document.getElementById("gb-sankey");
      if (!g3.length) { Plotly.purge(sankeyNode); sankeyNode.replaceChildren(el("p", { class: "empty", i18n: "conduits.no_g3" })); applyI18n(sankeyNode); }
      else {
        if (sankeyNode.querySelector("p.empty")) sankeyNode.replaceChildren();
        const labels = [], index = {};
        const node = (c, col) => { const k = col + c; if (!(k in index)) { index[k] = labels.length; labels.push({ c, col }); } return index[k]; };
        const src = [], tgt = [], val = [], col = [];
        g3.forEach((g) => { const [a, b, c] = g.chain.split(">");
          src.push(node(a, 0)); tgt.push(node(b, 1)); val.push(g.value); col.push(jurColour(b) + "88");
          src.push(node(b, 1)); tgt.push(node(c, 2)); val.push(g.value); col.push(jurColour(b) + "88"); });
        plot(sankeyNode, [{ type: "sankey", arrangement: "snap", node: { label: labels.map((l) => l.c), color: labels.map((l) => jurColour(l.c)), pad: 14, thickness: 14,
          line: { width: 0 } }, link: { source: src, target: tgt, value: val, color: col } }],
        { annotations: marks, margin: { l: 10, r: 10, t: 34, b: 10 } },
        { name: "three_country_chains", columns: ["chain", "value", "firm_paths"], rows: g3 });
      }
      document.getElementById("gb-table").replaceChildren(renderTable(["jurisdiction_id", "sink_centrality", "is_sink", "conduit_in", "conduit_out", "is_conduit", "entropy_in", "entropy_out", "value_in", "value_out", "gdp_share"], rows));
    }
    function kpiBox(label, value, colour) { return el("div", { class: "card kpi", style: "--c:" + colour }, [el("div", { class: "value", text: value }), el("div", { class: "label", text: label })]); }
    async function pin() {
      pinBtn.disabled = true;
      try {
        const res = await api("POST", "runs", { engine_id: GB_ENGINE, dataset_id: S.datasetId, parameters: params(), research_question: question.value });
        toast(res.executed ? t("routes.pinned", { id: res.record.run_id }) : t("runs.blocked"));
      } catch (e) { fail(e); } finally { pinBtn.disabled = false; }
    }
    sync();
    await compute();
  };

  // ------------------------------------------------------------------ topology (persistent homology; plan v2.4, s 9.4)
  const PH_ENGINE = "ph.vietoris_rips";
  // Must match taxnetlab.features.CATALOGUE (checked by a test).
  const PH_FEATURES = ["cit", "dividend_wht", "mean_applicable_wht", "treaty_count", "log_gdp", "outward_links", "inward_links",
    "vtrl_btwns", "vtrl_mean_shop", "gb_sink_centrality", "gb_conduit_out"];
  const H_COLOURS = ["#2563eb", "#f97316"];
  PAGES.topology = async function (root) {
    header(root, "topology.title", "topology.lede");
    if (needDataset(root)) return;
    const eng = S.engines.find((e) => e.engine_id === PH_ENGINE);
    if (!eng) return;
    const d = Object.fromEntries(eng.parameters.map((p) => [p.name, p.default]));
    const saved = (() => { try { return JSON.parse(recall("topology." + S.datasetId) || "null"); } catch (e) { return null; } })();
    const C = Object.assign({ input: d.input, features: d.features.split(","), scaling: d.scaling, metric: d.metric, symmetrise: d.symmetrise,
      loops: d.max_dimension >= 1, influence: d.influence, scale: null }, saved || {});
    const select = (values, value) => { const s = el("select", { class: "select" }, values.map((v) => el("option", { value: v, text: t("choice." + v) }))); s.value = value; return s; };
    const inputSel = select(["features", "routing_cost"], C.input), scalingSel = select(["zscore", "minmax", "none"], C.scaling);
    const metricSel = select(["euclidean", "manhattan", "chebyshev"], C.metric), symSel = select(["max", "mean"], C.symmetrise);
    const boxes = Object.fromEntries(PH_FEATURES.map((f) => [f, el("input", { type: "checkbox", checked: C.features.includes(f) })]));
    const loops = el("input", { type: "checkbox", checked: !!C.loops }), infl = el("input", { type: "checkbox", checked: !!C.influence });
    const scaleS = el("input", { type: "range", min: 0, max: 1, step: 0.001, class: "slider", "aria-label": t("topology.scale") });
    const scaleV = el("output", { class: "mono" });
    const status = el("p", { class: "muted small", style: "min-height:1.4em" });
    const question = el("textarea", { rows: 2, "data-i18n-placeholder": "runs.question_ph", placeholder: t("runs.question_ph") });
    const pinBtn = el("button", { class: "btn", i18n: "routes.pin", onclick: pin });
    const field = (key, ...kids) => el("label", { class: "field" }, [el("span", { i18n: key }), ...kids]);
    const check = (box, key) => el("label", { class: "field inline" }, [box, el("span", { i18n: key })]);
    const featureBox = el("fieldset", { class: "field plain-fieldset" }, [el("legend", { i18n: "param.features" }),
      ...PH_FEATURES.map((f) => check(boxes[f], "topology.f." + f))]);
    const featureFields = el("div", {}, [featureBox, field("param.scaling", scalingSel), field("param.metric", metricSel)]);
    const symField = field("param.symmetrise", symSel);
    const small = S.dataset.jurisdictions.length < 10;
    const makeBtn = el("button", { class: "btn btn-ghost", i18n: "topology.make_world", onclick: makeWorld });
    root.append(el("div", { class: "live-grid" }, [
      el("div", { class: "card live-panel" }, [
        el("h2", { i18n: "topology.settings" }),
        field("topology.scale", el("div", { class: "slider-row" }, [scaleS, scaleV])),
        el("p", { class: "muted small", i18n: "topology.scale_note" }),
        field("param.input", inputSel), featureFields, symField,
        check(loops, "topology.loops"), check(infl, "param.influence"),
        el("div", { class: "spacer" }), status, el("p", { class: "muted small", i18n: "routes.exploratory_note" }), question,
        el("div", { style: "height:8px" }), pinBtn,
        el("p", { class: "muted small", i18n: "topology.ip_note" })]),
      el("div", { class: "grid" }, [
        small ? el("div", { class: "card" }, [el("p", { i18n: "topology.small_world" }), makeBtn]) : null,
        el("div", { class: "card" }, [el("div", { class: "headline", id: "ph-head" }), el("h2", { i18n: "topology.map" }), guide("topology.map"),
          el("div", { class: "plot tall", id: "ph-map" })]),
        el("div", { class: "grid grid-2" }, [
          el("div", { class: "card" }, [el("h2", { i18n: "topology.diagram" }), guide("topology.diagram"), el("div", { class: "plot", id: "ph-diagram" })]),
          el("div", { class: "card" }, [el("h2", { i18n: "topology.barcode" }), guide("topology.barcode"), el("div", { class: "plot", id: "ph-barcode" })])]),
        el("div", { class: "grid grid-2" }, [
          el("div", { class: "card" }, [el("h2", { i18n: "topology.betti" }), guide("topology.betti"), el("div", { class: "plot short", id: "ph-betti" })]),
          el("div", { class: "card" }, [el("h2", { i18n: "topology.influence" }), guide("topology.influence"), el("div", { class: "plot short", id: "ph-influence" })])]),
        el("div", { class: "card" }, [el("h2", { i18n: "topology.table" }), el("div", { id: "ph-table" })]),
      ])]));
    let seq = 0, timer = null, R = null, selected = null;
    const params = () => ({ input: inputSel.value, features: PH_FEATURES.filter((f) => boxes[f].checked).join(","),
      scaling: scalingSel.value, metric: metricSel.value, symmetrise: symSel.value, max_dimension: loops.checked ? 1 : 0, influence: infl.checked });
    const scale = () => Number(scaleS.value);
    function sync() {
      featureFields.hidden = inputSel.value !== "features"; symField.hidden = inputSel.value === "features";
      scaleV.textContent = fmt(scale(), 3);
      const p = params();
      store("topology." + S.datasetId, JSON.stringify({ input: p.input, features: p.features.split(","), scaling: p.scaling, metric: p.metric,
        symmetrise: p.symmetrise, loops: loops.checked, influence: infl.checked, scale: R ? scale() : C.scale }));
    }
    function changed() { sync(); clearTimeout(timer); timer = setTimeout(compute, 60); }
    [inputSel, scalingSel, metricSel, symSel, loops, infl, ...Object.values(boxes)].forEach((x) => x.addEventListener("change", changed));
    scaleS.addEventListener("input", () => { sync(); if (R) drawScale(); });
    async function compute() {
      const my = ++seq;
      const p = params();
      if (p.input === "features" && !p.features) { status.replaceChildren(el("span", { class: "err-text", i18n: "topology.need_feature" })); return; }
      status.textContent = t("routes.computing");
      try {
        const res = await api("POST", `engines/${PH_ENGINE}/preview`, { dataset_id: S.datasetId, parameters: p });
        if (my !== seq) return;
        if (!res.executed || res.outcome !== "ok") {
          status.replaceChildren(el("span", { class: "err-text", text: res.executed ? t("outcome." + res.outcome) + "  ·  " + res.warnings.join(" ") : t("runs.blocked") }));
          if (!res.executed) document.getElementById("ph-table").replaceChildren(issuesList(res.validation));
          return;
        }
        status.textContent = t("routes.status", { ms: res.cached ? t("routes.cached") : fmt(res.elapsed_ms, 0) + " ms", status: t("status." + res.status) })
          + (res.warnings.length ? "  ·  " + res.warnings.join(" ") : "");
        // A new distance scale (input, features, scaling, metric) resets the view scale to a sensible default.
        const geom = JSON.stringify([p.input, p.features, p.scaling, p.metric, p.symmetrise]);
        const first = !R || R.geom !== geom, restore = !R;
        R = res; R.geom = geom;
        R.sum = Object.fromEntries(res.outputs.summary.map((r) => [r.measure, r.value]));
        R.maxD = Math.max(1e-9, ...res.outputs.distances.map((r) => r.distance));
        const top = res.outputs.diagram.find((r) => r.dimension === 1 && !r.essential);
        if (selected) selected = res.outputs.diagram.find((r) => r.feature_id === selected.feature_id && r.birth_simplex === selected.birth_simplex) || null;
        scaleS.max = R.maxD; scaleS.step = R.maxD / 400;
        const savedScale = restore && C.scale !== null && C.scale !== undefined ? C.scale : null;
        const wanted = !first ? scale() : savedScale !== null ? savedScale : top ? (top.birth + top.death) / 2 : R.maxD / 3;
        scaleS.value = Math.min(R.maxD, Math.max(0, wanted));
        sync();
        drawStatic(); drawScale();
      } catch (e) { if (my === seq) fail(e); }
    }
    const marks = () => watermark([t("wm.exploratory"), R.status !== "verified" ? t("wm.unverified") : null, statusWatermark()]);
    const alive = (r, e) => r.birth <= e && (r.death === null || e < r.death);
    function select_(row) {
      selected = row;
      if (row && row.dimension === 1) scaleS.value = row.death === null ? row.birth : (row.birth + row.death) / 2;
      sync(); drawScale();
    }
    function bindClick(node, fn) {
      node._tnlClick = fn;
      if (!node._tnlBound) { node.on("plotly_click", (ev) => node._tnlClick && node._tnlClick(ev)); node._tnlBound = true; }
    }
    function drawStatic() {
      const rows = R.outputs.diagram;
      // influence
      const inf = R.outputs.influence.slice().sort((a, b) => (b.bottleneck_h1 ?? 0) - (a.bottleneck_h1 ?? 0) || (b.bottleneck_h0 ?? 0) - (a.bottleneck_h0 ?? 0));
      const infNode = document.getElementById("ph-influence");
      if (!inf.length) { Plotly.purge(infNode); infNode.replaceChildren(el("p", { class: "empty", i18n: "topology.no_influence" })); applyI18n(infNode); }
      else {
        if (infNode.querySelector("p.empty")) infNode.replaceChildren();
        const tr = [{ type: "bar", name: t("topology.h0"), x: inf.map((r) => r.jurisdiction_id), y: inf.map((r) => r.bottleneck_h0), marker: { color: H_COLOURS[0] },
          hovertemplate: "%{x}: %{y:.4f}<extra>H0</extra>" }];
        if (R.parameters.max_dimension >= 1) tr.push({ type: "bar", name: t("topology.h1"), x: inf.map((r) => r.jurisdiction_id), y: inf.map((r) => r.bottleneck_h1),
          marker: { color: H_COLOURS[1] }, hovertemplate: "%{x}: %{y:.4f}<extra>H1</extra>" });
        plot(infNode, tr, { barmode: "group", legend: { orientation: "h", y: -0.3 }, margin: { l: 56, r: 24, t: 34, b: 86 }, xaxis: { tickangle: -60, tickfont: { size: 10 } }, yaxis: { title: { text: t("topology.axis.bottleneck") } }, annotations: marks() },
          { name: "influence", columns: ["jurisdiction_id", "bottleneck_h0", "bottleneck_h1", "rank_h1"], rows: inf });
      }
      document.getElementById("ph-table").replaceChildren(renderTable(["feature_id", "dimension", "birth", "death", "persistence", "essential",
        "birth_simplex", "death_simplex", "representative_cycle", "members"], rows, (r) => select_(r)));
    }
    function drawScale() {
      const e = scale(), rows = R.outputs.diagram, m = marks();
      const pts = R.outputs.points.filter((p) => p.included);
      const idx = Object.fromEntries(pts.map((p, i) => [p.jurisdiction_id, i]));
      const parent = pts.map((_, i) => i);
      const find = (x) => { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; };
      const close = R.outputs.distances.filter((r) => r.distance <= e);
      close.forEach((r) => { const a = find(idx[r.a]), b = find(idx[r.b]); if (a !== b) parent[Math.max(a, b)] = Math.min(a, b); });
      const roots = [...new Set(pts.map((_, i) => find(i)))].sort((a, b) => a - b);
      const compColour = Object.fromEntries(roots.map((r, k) => [r, PALETTE[k % PALETTE.length]]));
      const b0 = roots.length, b1 = rows.filter((r) => r.dimension === 1 && alive(r, e)).length;
      const h1 = rows.filter((r) => r.dimension === 1);
      document.getElementById("ph-head").replaceChildren(el("div", { class: "kpis" }, [
        kpiCard(t("topology.k.clusters"), fmt(b0, 0), H_COLOURS[0]),
        kpiCard(t("topology.k.loops_now"), R.parameters.max_dimension >= 1 ? fmt(b1, 0) : "–", H_COLOURS[1]),
        kpiCard(t("topology.k.loops"), R.parameters.max_dimension >= 1 ? fmt(h1.length, 0) : "–", "#d946ef"),
        kpiCard(t("topology.k.persistent"), h1.length ? `${h1[0].feature_id} · ${fmt(h1[0].persistence, 3)}` : t("conduits.none"), "#14b8a6"),
        kpiCard(t("topology.k.influential"), R.sum.most_influential_h1 === "none" ? t("conduits.none") : R.sum.most_influential_h1, "#f59e0b")]));
      // map: Rips graph at the scale, clusters by colour, a selected loop traced
      const shown = close.slice(0, 4000), ex = [], ey = [];
      shown.forEach((r) => { const a = pts[idx[r.a]], b = pts[idx[r.b]]; ex.push(a.x, b.x, null); ey.push(a.y, b.y, null); });
      const traces = [{ type: "scatter", mode: "lines", x: ex, y: ey, line: { color: "rgba(100,116,139,0.35)", width: 1 }, hoverinfo: "skip", name: t("topology.edges") }];
      if (selected && selected.representative_cycle) {
        const cyc = selected.representative_cycle.split(">").filter((c) => c in idx);
        traces.push({ type: "scatter", mode: "lines", x: cyc.map((c) => pts[idx[c]].x), y: cyc.map((c) => pts[idx[c]].y), name: selected.feature_id,
          line: { color: H_COLOURS[1], width: 5 }, hoverinfo: "skip" });
      }
      traces.push({ type: "scatter", mode: "markers+text", x: pts.map((p) => p.x), y: pts.map((p) => p.y), text: pts.map((p) => p.jurisdiction_id),
        textposition: "top center", customdata: pts.map((p) => p.jurisdiction_id), name: t("topology.points"),
        marker: { size: 16, color: pts.map((_, i) => compColour[find(i)]), line: { width: 1.5, color: "#ffffff" } },
        hovertemplate: "<b>%{customdata}</b><extra></extra>" });
      plot(document.getElementById("ph-map"), traces, { showlegend: false,
        xaxis: { zeroline: false, showticklabels: false, title: { text: t("topology.axis.projection") + "<br><span style='font-size:11.5px'>"
          + t("topology.stress", { s: fmt(R.sum.projection_stress, 3) }) + "  ·  " + t("topology.scale_is", { e: fmt(e, 3) }) + "</span>" } },
        yaxis: { zeroline: false, showticklabels: false, scaleanchor: "x" }, annotations: m },
      { name: "rips_graph_at_scale", columns: ["a", "b", "distance"], rows: close });
      // persistence diagram
      const fin = rows.filter((r) => !r.essential), top = Math.max(R.maxD, ...fin.map((r) => r.death)) * 1.08;
      const dg = [0, 1].filter((k) => k === 0 || R.parameters.max_dimension >= 1).map((k) => {
        const rs = rows.filter((r) => r.dimension === k);
        return { type: "scatter", mode: "markers", name: t(k ? "topology.h1" : "topology.h0"), x: rs.map((r) => r.birth), y: rs.map((r) => (r.essential ? top : r.death)),
          customdata: rs.map((r) => [r.feature_id, r.persistence === null ? "∞" : fmt(r.persistence, 4), r.representative_cycle || r.members || ""]),
          marker: { color: H_COLOURS[k], size: rs.map((r) => (selected && r.feature_id === selected.feature_id ? 16 : 10)), symbol: rs.map((r) => (r.essential ? "triangle-up" : "circle")),
            line: { width: 1.5, color: rs.map((r) => (alive(r, e) ? "#111827" : "#ffffff")) }, opacity: 0.9 },
          hovertemplate: `<b>%{customdata[0]}</b><br>${t("col.birth")}: %{x:.4f}<br>${t("col.persistence")}: %{customdata[1]}<br>%{customdata[2]}<extra></extra>` };
      });
      const dNode = document.getElementById("ph-diagram");
      plot(dNode, dg, { xaxis: { title: { text: t("col.birth") }, range: [-top * 0.03, top * 1.02] }, yaxis: { title: { text: t("col.death") }, range: [-top * 0.03, top * 1.04] },
        shapes: [{ type: "line", x0: 0, y0: 0, x1: top, y1: top, line: { color: cssVar("--muted"), width: 1 } },
          { type: "rect", x0: -top, x1: e, y0: e, y1: top * 1.04, fillcolor: "rgba(249,115,22,0.08)", line: { width: 0 } },
          { type: "line", x0: e, x1: e, y0: e, y1: top * 1.04, line: { color: H_COLOURS[1], dash: "dot", width: 1.5 } },
          { type: "line", x0: -top, x1: e, y0: e, y1: e, line: { color: H_COLOURS[1], dash: "dot", width: 1.5 } },
          { type: "line", x0: 0, x1: top, y0: top, y1: top, line: { color: cssVar("--line"), dash: "dash", width: 1 } }],
        annotations: m.concat([{ x: top, y: top, xanchor: "right", yanchor: "bottom", text: t("topology.infinite"), showarrow: false, font: { size: 11, color: cssVar("--muted") } }]) },
      { name: "persistence_diagram", columns: ["feature_id", "dimension", "birth", "death", "persistence", "essential"], rows });
      bindClick(dNode, (ev) => { const p = ev.points && ev.points[0]; if (p && p.customdata) select_(rows.find((r) => r.feature_id === p.customdata[0])); });
      // barcode: every loop and the 30 longest-lived clusters
      const bars = rows.filter((r) => r.dimension === 1).concat(rows.filter((r) => r.dimension === 0).slice(0, 30)).reverse();
      const bNode = document.getElementById("ph-barcode");
      plot(bNode, [{ type: "bar", orientation: "h", y: bars.map((r) => r.feature_id), base: bars.map((r) => r.birth), x: bars.map((r) => (r.essential ? top : r.death) - r.birth),
        marker: { color: bars.map((r) => H_COLOURS[r.dimension]), opacity: bars.map((r) => (alive(r, e) ? 1 : 0.35)),
          line: { width: bars.map((r) => (selected && r.feature_id === selected.feature_id ? 2.5 : 0)), color: "#111827" } },
        customdata: bars.map((r) => [r.feature_id, r.essential ? "∞" : fmt(r.death, 4), r.representative_cycle || r.members || ""]),
        hovertemplate: `<b>%{customdata[0]}</b><br>${t("col.birth")}: %{base:.4f}<br>${t("col.death")}: %{customdata[1]}<br>%{customdata[2]}<extra></extra>` }],
      { showlegend: false, bargap: 0.25, xaxis: { title: { text: t("topology.scale") }, range: [0, top] }, yaxis: { automargin: true, tickfont: { size: 10.5 } },
        shapes: [{ type: "line", xref: "x", yref: "paper", x0: e, x1: e, y0: 0, y1: 1, line: { color: H_COLOURS[1], dash: "dot", width: 1.5 } }], annotations: m },
      { name: "barcode", columns: ["feature_id", "dimension", "birth", "death", "persistence"], rows: bars });
      bindClick(bNode, (ev) => { const p = ev.points && ev.points[0]; if (p && p.customdata) select_(rows.find((r) => r.feature_id === p.customdata[0])); });
      // Betti curves
      const bc = R.outputs.betti.slice().sort((a, b) => a.scale - b.scale);
      const xs = bc.map((r) => r.scale).concat([top]), b0s = bc.map((r) => r.b0), b1s = bc.map((r) => r.b1);
      b0s.push(b0s[b0s.length - 1]); b1s.push(b1s[b1s.length - 1]);
      const bt = [{ type: "scatter", mode: "lines", line: { shape: "hv", color: H_COLOURS[0], width: 2.5 }, name: t("topology.b0"), x: xs, y: b0s }];
      if (R.parameters.max_dimension >= 1) bt.push({ type: "scatter", mode: "lines", line: { shape: "hv", color: H_COLOURS[1], width: 2.5 }, name: t("topology.b1"), x: xs, y: b1s, yaxis: "y2" });
      plot(document.getElementById("ph-betti"), bt, { legend: { orientation: "h", y: -0.34 }, margin: { l: 56, r: 48, t: 34, b: 78 }, xaxis: { title: { text: t("topology.scale") }, range: [0, top] }, yaxis: { title: { text: t("topology.b0") }, rangemode: "tozero" },
        yaxis2: { title: { text: t("topology.b1") }, overlaying: "y", side: "right", rangemode: "tozero", showgrid: false, dtick: 1 },
        shapes: [{ type: "line", xref: "x", yref: "paper", x0: e, x1: e, y0: 0, y1: 1, line: { color: H_COLOURS[1], dash: "dot", width: 1.5 } }], annotations: m },
      { name: "betti_curves", columns: ["scale", "b0", "b1"], rows: bc });
    }
    function kpiCard(label, value, colour) { return el("div", { class: "card kpi", style: "--c:" + colour }, [el("div", { class: "value", text: value }), el("div", { class: "label", text: label })]); }
    async function makeWorld() {
      makeBtn.disabled = true;
      try {
        const res = await api("POST", "datasets/synthetic", { seed: 7, n_jurisdictions: 20, n_groups: 12, entities_per_group: 6, cross_holdings: 4 });
        toast(t("data.generated", { name: res.name }));
        await loadDatasets(res.dataset_id); await route();
      } catch (e) { fail(e); } finally { makeBtn.disabled = false; }
    }
    async function pin() {
      pinBtn.disabled = true;
      try {
        const res = await api("POST", "runs", { engine_id: PH_ENGINE, dataset_id: S.datasetId, parameters: params(), research_question: question.value });
        toast(res.executed ? t("routes.pinned", { id: res.record.run_id }) : t("runs.blocked"));
      } catch (e) { fail(e); } finally { pinBtn.disabled = false; }
    }
    sync();
    await compute();
  };

  // ------------------------------------------------------------------ model comparison (plan s 8; spec compare_models.md)
  const CMP_ENGINE = "compare.models";
  PAGES.compare = async function (root) {
    header(root, "compare.title", "compare.lede");
    if (needDataset(root)) return;
    const eng = S.engines.find((e) => e.engine_id === CMP_ENGINE);
    if (!eng) return;
    const topo = el("input", { type: "checkbox", checked: recall("compare.topology") !== "false" });
    const measureSel = el("select", { class: "select" });
    const status = el("p", { class: "muted small", style: "min-height:1.4em" });
    const question = el("textarea", { rows: 2, "data-i18n-placeholder": "runs.question_ph", placeholder: t("runs.question_ph") });
    const pinBtn = el("button", { class: "btn", i18n: "routes.pin", onclick: pin });
    root.append(el("div", { class: "live-grid" }, [
      el("div", { class: "card live-panel" }, [el("h2", { i18n: "topology.settings" }),
        el("label", { class: "field inline" }, [topo, el("span", { i18n: "param.include_topology" })]),
        el("p", { class: "muted small", i18n: "compare.readings_note" }),
        el("div", { class: "spacer" }), status, el("p", { class: "muted small", i18n: "routes.exploratory_note" }), question,
        el("div", { style: "height:8px" }), pinBtn]),
      el("div", { class: "grid" }, [
        el("div", { class: "card" }, [el("div", { class: "headline", id: "cmp-head" }), el("h2", { i18n: "compare.grid" }), guide("compare.grid"),
          el("div", { class: "plot tall", id: "cmp-grid" })]),
        el("div", { class: "card" }, [el("h2", { i18n: "compare.robust" }), guide("compare.robust"), el("div", { class: "plot short", id: "cmp-robust" })]),
        el("div", { class: "card" }, [el("h2", { i18n: "compare.corr" }), guide("compare.corr"), el("div", { class: "plot tall", id: "cmp-corr" })]),
        el("div", { class: "card" }, [el("h2", { i18n: "compare.sensitivity" }), guide("compare.sensitivity"),
          el("label", { class: "field", style: "max-width:360px" }, [el("span", { i18n: "compare.measure" }), measureSel]), el("div", { class: "plot", id: "cmp-sens" })]),
        el("div", { class: "card" }, [el("h2", { i18n: "compare.definitions" }), el("div", { id: "cmp-defs" })]),
        el("div", { class: "card" }, [el("h2", { i18n: "compare.table" }), el("div", { id: "cmp-table" })]),
      ])]));
    let res = null, seq = 0;
    const params = () => ({ include_topology: topo.checked });
    topo.addEventListener("change", () => { store("compare.topology", String(topo.checked)); compute(); });
    measureSel.addEventListener("change", () => drawSensitivity());
    function kpiCard(label, value, colour) { return el("div", { class: "card kpi", style: "--c:" + colour }, [el("div", { class: "value", text: value }), el("div", { class: "label", text: label })]); }
    async function compute() {
      const my = ++seq;
      status.textContent = t("routes.computing");
      try {
        const r = await api("POST", `engines/${CMP_ENGINE}/preview`, { dataset_id: S.datasetId, parameters: params() });
        if (my !== seq) return;
        if (!r.executed || r.outcome !== "ok") {
          status.replaceChildren(el("span", { class: "err-text", text: r.executed ? t("outcome." + r.outcome) + "  ·  " + r.warnings.join(" ") : t("runs.blocked") }));
          if (!r.executed) document.getElementById("cmp-table").replaceChildren(issuesList(r.validation));
          return;
        }
        res = r; res.sum = Object.fromEntries(r.outputs.summary.map((x) => [x.measure, x.value]));
        status.textContent = t("routes.status", { ms: r.cached ? t("routes.cached") : fmt(r.elapsed_ms, 0) + " ms", status: t("status." + r.status) })
          + (r.warnings.length ? "  ·  " + r.warnings.join(" ") : "");
        draw();
      } catch (e) { if (my === seq) fail(e); }
    }
    const marks = () => watermark([t("wm.exploratory"), t("wm.unverified"), statusWatermark()]);
    function draw() {
      const ag = res.outputs.agreement, sum = res.sum;
      const measures = [...new Set(ag.map((r) => r.measure))];
      const jurs = [...new Set(ag.map((r) => r.jurisdiction_id))].sort().reverse();
      document.getElementById("cmp-head").replaceChildren(el("div", { class: "kpis" }, [
        kpiCard(t("compare.k.agreed"), pct(sum.share_agreed), "#22c55e"),
        kpiCard(t("compare.k.readings"), fmt(sum.readings_run, 0), "#2563eb"),
        kpiCard(t("compare.k.unranked"), sum.engines_unranked === "none" ? t("conduits.none") : sum.engines_unranked, "#f59e0b"),
        kpiCard(t("compare.k.status"), t("status." + sum.lowest_engine_status), "#8b5cf6")]));
      // agreement grid: agreed ranks coloured; ties shown as a range, uncoloured
      const cell = (j, m) => ag.find((r) => r.jurisdiction_id === j && r.measure === m);
      const z = jurs.map((j) => measures.map((m) => { const c = cell(j, m); return c && c.agreed ? c.rank : null; }));
      const text = jurs.map((j) => measures.map((m) => { const c = cell(j, m); if (!c || c.rank_min === null) return "–";
        return c.agreed ? String(c.rank) : `${c.rank_min}–${c.rank_max}`; }));
      const n = jurs.length;
      const gNode = document.getElementById("cmp-grid");
      plot(gNode, [
        { type: "heatmap", x: measures, y: jurs, z: jurs.map(() => measures.map(() => 0)), showscale: false, hoverinfo: "skip",
          colorscale: [[0, cssVar("--line") || "#e2e8f0"], [1, cssVar("--line") || "#e2e8f0"]] },
        { type: "heatmap", x: measures, y: jurs, z, zmin: 1, zmax: Math.max(2, n), colorscale: SCALE.map(([p, c]) => [1 - p, c]).reverse(),
          text, texttemplate: "%{text}", hovertemplate: "%{y} · %{x}<br>" + t("compare.rank") + ": %{text}<extra></extra>", xgap: 2, ygap: 2,
          colorbar: { title: { text: t("compare.rank") }, thickness: 12 } }],
      { xaxis: { side: "bottom", tickangle: -30 }, yaxis: { automargin: true }, margin: { l: 70, r: 24, t: 50, b: 130 }, annotations: marks() },
      { name: "agreement", columns: ["jurisdiction_id", "measure", "agreed", "rank", "rank_min", "rank_max", "readings", "ranked_readings", "value_default"], rows: ag });
      // robustness shares of classifications
      const cls = res.outputs.classification.filter((r) => r.classified_in > 0);
      const rNode = document.getElementById("cmp-robust");
      if (!cls.length) { Plotly.purge(rNode); rNode.replaceChildren(el("p", { class: "empty", i18n: "compare.no_classes" })); applyI18n(rNode); }
      else {
        if (rNode.querySelector("p.empty")) rNode.replaceChildren();
        const kinds = ["gb2017.sink_ofc", "gb2017.conduit_ofc"], colours = { "gb2017.sink_ofc": "#ef4444", "gb2017.conduit_ofc": "#8b5cf6" };
        const js = [...new Set(cls.map((r) => r.jurisdiction_id))].sort();
        plot(rNode, kinds.map((k) => ({ type: "bar", name: t("compare.class." + k.split(".")[1]), x: js,
          y: js.map((j) => (res.outputs.classification.find((r) => r.jurisdiction_id === j && r.classification === k) || {}).share || 0),
          marker: { color: colours[k] }, hovertemplate: "%{x}: %{y:.0%}<extra></extra>" })),
        { barmode: "group", yaxis: { tickformat: ".0%", range: [0, 1.05], title: { text: t("compare.share") } }, annotations: marks() },
        { name: "robustness_shares", columns: ["jurisdiction_id", "classification", "classified_in", "readings", "share", "robust"], rows: res.outputs.classification });
      }
      // rank correlation matrix
      const cr = res.outputs.correlation, ms = [...new Set(cr.flatMap((r) => [r.measure_a, r.measure_b]))].sort();
      const rho = (a, b) => { if (a === b) return 1; const r = cr.find((x) => (x.measure_a === a && x.measure_b === b) || (x.measure_a === b && x.measure_b === a)); return r ? r.spearman : null; };
      plot(document.getElementById("cmp-corr"), [{ type: "heatmap", x: ms, y: ms, z: ms.map((a) => ms.map((b) => rho(a, b))), zmin: -1, zmax: 1, colorscale: "RdBu", reversescale: true,
        text: ms.map((a) => ms.map((b) => { const v = rho(a, b); return v === null ? "–" : fmt(v, 2); })), texttemplate: "%{text}",
        hovertemplate: "%{y} · %{x}<br>Spearman %{text}<extra></extra>", colorbar: { title: { text: "ρ" }, thickness: 12 } }],
      { xaxis: { tickangle: -35 }, yaxis: { automargin: true }, margin: { l: 170, r: 24, t: 50, b: 150 }, font: { size: 12.5 }, annotations: marks() },
      { name: "rank_correlations", columns: ["measure_a", "measure_b", "n", "spearman", "kendall_tau_b"], rows: cr });
      // sensitivity selector
      const prev = measureSel.value;
      measureSel.replaceChildren(...measures.map((m) => el("option", { value: m, text: m })));
      measureSel.value = measures.includes(prev) ? prev : measures.find((m) => m.startsWith("gb2017.conduit")) || measures[0];
      drawSensitivity();
      // definitions side by side (from the engines' declared measures)
      const defs = [];
      S.engines.forEach((e) => e.measures.forEach((m) => { if (measures.includes(m.name) || (m.name === "vtrl2018.shop" && measures.includes("vtrl2018.shop_as_host")))
        defs.push({ name: m.name, engine: e.display_name, status: t("status." + e.status), definition: m.definition, numerator: m.numerator, denominator: m.denominator, unit: m.unit, source_ref: m.source_ref }); }));
      document.getElementById("cmp-defs").replaceChildren(renderTable(["name", "engine", "status", "definition", "numerator", "denominator", "unit", "source_ref"], defs));
      document.getElementById("cmp-table").replaceChildren(renderTable(["jurisdiction_id", "measure", "agreed", "rank", "rank_min", "rank_max", "ranked_readings", "readings", "value_default"],
        ag.slice().sort((a, b) => a.measure.localeCompare(b.measure) || (a.rank_min ?? 1e9) - (b.rank_min ?? 1e9))));
    }
    function drawSensitivity() {
      if (!res) return;
      const m = measureSel.value, rows = res.outputs.readings.filter((r) => r.measure === m);
      const readings = [...new Set(rows.map((r) => r.reading))];
      const js = [...new Set(rows.map((r) => r.jurisdiction_id))].sort();
      plot(document.getElementById("cmp-sens"), readings.map((rd, i) => ({ type: "scatter", mode: "markers", name: rd, x: js,
        y: js.map((j) => (rows.find((r) => r.reading === rd && r.jurisdiction_id === j) || {}).value ?? null),
        marker: { size: 12, color: PALETTE[i % PALETTE.length], symbol: ["circle", "diamond", "square", "triangle-up"][i % 4], line: { width: 1, color: "#ffffff" } },
        hovertemplate: "%{x}: %{y:.4f}<extra>" + rd + "</extra>" })),
      { yaxis: { title: { text: m } }, legend: { orientation: "h", y: -0.25 }, margin: { l: 70, r: 24, t: 34, b: 90 }, annotations: marks() },
      { name: "readings_" + m, columns: ["measure", "reading", "jurisdiction_id", "value", "rank"], rows });
    }
    async function pin() {
      pinBtn.disabled = true;
      try {
        const r = await api("POST", "runs", { engine_id: CMP_ENGINE, dataset_id: S.datasetId, parameters: params(), research_question: question.value });
        toast(r.executed ? t("routes.pinned", { id: r.record.run_id }) : t("runs.blocked"));
      } catch (e) { fail(e); } finally { pinBtn.disabled = false; }
    }
    await compute();
  };

  // ------------------------------------------------------------------ guide (user guide, method notes, glossary)
  // A deliberately small Markdown renderer for the bundled guide: text is escaped first, so the guide cannot
  // inject markup; it supports headings, paragraphs, lists, code blocks, inline code, bold, italic and links.
  function markdown(src) {
    const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const inline = (s) => esc(s).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>").replace(/&lt;(https?:[^&\s]+)&gt;/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
    const out = []; let list = null, para = [], code = null;
    const flush = () => { if (para.length) { out.push("<p>" + inline(para.join(" ")) + "</p>"); para = []; } if (list) { out.push(list.tag === "ol" ? "<ol>" + list.items.join("") + "</ol>" : "<ul>" + list.items.join("") + "</ul>"); list = null; } };
    for (const line of src.split("\n")) {
      if (code !== null) { if (line.startsWith("```")) { out.push("<pre><code>" + esc(code.join("\n")) + "</code></pre>"); code = null; } else code.push(line); continue; }
      if (line.startsWith("```")) { flush(); code = []; continue; }
      const h = line.match(/^(#{1,3}) (.*)$/);
      if (h) { flush(); const n = h[1].length + 1; out.push(`<h${n}>${inline(h[2])}</h${n}>`); continue; }
      const li = line.match(/^\s*(\*|\d+\.) (.*)$/);
      if (li) { if (para.length) { out.push("<p>" + inline(para.join(" ")) + "</p>"); para = []; } const tag = li[1] === "*" ? "ul" : "ol"; if (!list || list.tag !== tag) { if (list) flush(); list = { tag, items: [] }; } list.items.push("<li>" + inline(li[2]) + "</li>"); continue; }
      if (!line.trim()) { flush(); continue; }
      if (list && /^\s{2,}\S/.test(line)) { list.items[list.items.length - 1] = list.items[list.items.length - 1].replace("</li>", " " + inline(line.trim()) + "</li>"); continue; }
      para.push(line.trim());
    }
    flush();
    const box = el("div", { class: "prose" }); box.innerHTML = out.join("\n"); return box;
  }
  PAGES.guide = async function (root) {
    header(root, "guide.title", "guide.lede");
    const g = await api("GET", "guide?locale=" + encodeURIComponent(S.locale));
    const measures = [];
    S.engines.forEach((e) => e.measures.forEach((m) => measures.push({ name: m.name, definition: m.definition, unit: m.unit, engine: e.display_name })));
    const statuses = ["interface", "specified", "implemented", "verified", "replicated", "replicated_with_discrepancies"];
    root.append(el("div", { class: "grid" }, [
      el("div", { class: "card" }, [markdown(g.user_guide)]),
      el("div", { class: "card" }, [markdown(g.methods)]),
      el("div", { class: "card" }, [el("h2", { i18n: "guide.glossary" }), el("h3", { i18n: "guide.statuses" }),
        renderTable(["status", "meaning"], statuses.map((s) => ({ status: t("status." + s), meaning: t("glossary.status." + s) }))),
        el("h3", { i18n: "guide.measures" }), renderTable(["name", "definition", "unit", "engine"], measures)]),
    ]));
  };

  // ------------------------------------------------------------------ data
  const TABLES = ["sources", "jurisdictions", "jurisdiction_attributes", "entities", "ownership", "illustrative_tax_edges",
    "tax_domestic", "tax_treaty_dividends", "tax_relief_overrides", "entity_financials", "tax_treaty_conditions", "rule_verifications"];
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
    const complete = completeForm();
    if (complete) root.append(complete, el("div", { class: "spacer" }));
    root.append(el("div", { class: "grid grid-2" }, [synthForm(), importForm()]), el("div", { class: "spacer" }), codingForm());
  };

  function renderTable(columns, rows, onRow) {
    if (!rows.length) return el("p", { class: "empty", i18n: "data.empty" });
    const isNum = (v) => typeof v === "number";
    return el("div", { class: "table-wrap" }, [el("table", {}, [
      el("thead", {}, [el("tr", {}, columns.map((c) => el("th", { text: tOr("col." + c, c) })))]),
      el("tbody", {}, rows.map((r) => el("tr", onRow ? { class: "clickable", onclick: () => onRow(r) } : {}, columns.map((c) => {
        const v = r[c];
        if (typeof v === "string" && /^https?:\/\/\S+$/i.test(v)) return el("td", {}, [el("a", { href: v, target: "_blank", rel: "noopener noreferrer", text: v })]);
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

  // Legal coding templates (plan s 5.4): download, code the legal fields, import the ZIP.
  function codingForm() {
    const cands = el("input", { type: "text", value: "NLD,LUX,IRL,GBR,USA,DEU,FRA,CHE,SGP,HKG,MYS,CHN,CYP,MLT,BEL" });
    const zipName = el("input", { type: "text", "data-i18n-placeholder": "data.import_name", placeholder: t("data.import_name") });
    const zipFile = el("input", { type: "file", accept: ".zip,application/zip" });
    const out = el("div");
    const realLink = () => "/api/templates/real_sample.zip?jurisdictions=" + encodeURIComponent(cands.value.replace(/\s+/g, ""));
    const realBtn = el("a", { class: "btn btn-ghost", href: realLink(), download: "", i18n: "coding.real" });
    cands.addEventListener("input", () => { realBtn.href = realLink(); });
    const btn = el("button", { class: "btn", i18n: "coding.import", onclick: async () => {
      const f = zipFile.files[0];
      if (!f) { toast(t("coding.choose_file")); return; }
      btn.disabled = true;
      try {
        const buf = new Uint8Array(await f.arrayBuffer());
        let bin = ""; for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
        const res = await api("POST", "datasets/import_zip", { name: zipName.value || f.name.replace(/\.zip$/i, ""), zip_base64: btoa(bin) });
        out.replaceChildren(issuesList(res.validation));
        if (res.saved) { await loadDatasets(res.dataset_id); toast(t("data.import_ok", { id: res.dataset_id })); }
        else toast(t("data.import_blocked"));
      } catch (e) { fail(e); } finally { btn.disabled = false; }
    } });
    return el("div", { class: "card" }, [el("h2", { i18n: "coding.title" }), el("p", { class: "muted small", i18n: "coding.lede" }),
      el("div", { class: "grid grid-2" }, [
        el("div", {}, [el("h3", { i18n: "coding.download" }),
          el("div", { class: "btn-row" }, [el("a", { class: "btn btn-ghost", href: "/api/templates/illustrative.zip", download: "", i18n: "coding.illustrative" })]),
          el("label", { class: "field" }, [el("span", { i18n: "coding.candidates" }), cands]), el("div", { class: "btn-row" }, [realBtn])]),
        el("div", {}, [el("h3", { i18n: "coding.upload" }), el("label", { class: "field" }, [el("span", { i18n: "coding.name" }), zipName]),
          el("label", { class: "field" }, [el("span", { i18n: "coding.file" }), zipFile]), btn, out])])]);
  }

  function importForm() {
    const name = el("input", { type: "text", "data-i18n-placeholder": "data.import_name", placeholder: t("data.import_name") });
    const inputs = Object.fromEntries(TABLES.map((tb) => [tb, el("input", { type: "file", accept: ".csv,text/csv" })]));
    const mapping = el("textarea", { rows: 4, class: "mono", placeholder: '{"ownership": {"holder_id": "Shareholder BvD ID", "source_id": "=ORBIS_2025"}}' });
    const out = el("div");
    const btn = el("button", { class: "btn", i18n: "data.import", onclick: async () => {
      btn.disabled = true; out.replaceChildren();
      try {
        const tables = {};
        for (const [tb, inp] of Object.entries(inputs)) if (inp.files[0]) tables[tb] = await inp.files[0].text();
        let map = null;
        if (mapping.value.trim()) { try { map = JSON.parse(mapping.value); } catch (e) { toast(t("data.mapping_bad")); return; } }
        const res = await api("POST", "datasets/import", { name: name.value, tables, mapping: map });
        out.append(el("p", { class: res.saved ? "ok-text" : "err-text", text: res.saved ? t("data.import_ok", { id: res.dataset_id }) : t("data.import_blocked") }), issuesList(res.validation));
        if (res.saved) { await loadDatasets(res.dataset_id); toast(t("data.import_ok", { id: res.dataset_id })); }
      } catch (e) { fail(e); } finally { btn.disabled = false; }
    } });
    return el("div", { class: "card" }, [el("h2", { i18n: "data.import_title" }), el("p", { class: "muted small", i18n: "data.import_lede" }),
      el("div", { class: "controls" }, [el("label", { class: "field", style: "flex:1 1 100%" }, [el("span", { i18n: "data.import_name_label" }), name]),
        ...TABLES.map((tb) => el("label", { class: "field" }, [el("span", { text: t("table." + tb) + (["sources", "jurisdictions", "entities", "ownership"].includes(tb) ? " *" : "") }), inputs[tb]]))]),
      el("details", { style: "margin:10px 0" }, [el("summary", { i18n: "data.mapping" }), el("p", { class: "muted small", i18n: "data.mapping_help" }), mapping]),
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
        // Background job (plan s 11): progress and cancellation; the run record is written only on completion.
        const job = await api("POST", "jobs", { engine_id: engineSel.value, dataset_id: S.datasetId, parameters, research_question: question.value });
        const bar = el("progress", { max: 1, value: 0, class: "progress" }), msg = el("span", { class: "muted small" });
        const cancel = el("button", { class: "btn btn-ghost", i18n: "runs.cancel", onclick: () => api("POST", `jobs/${job.job_id}/cancel`, {}).catch(fail) });
        result.replaceChildren(el("div", { class: "card" }, [el("p", { i18n: "runs.running" }), el("div", { class: "btn-row" }, [bar, msg, cancel])]));
        applyI18n(result);
        let state = job;
        while (state.state === "queued" || state.state === "running") {
          await new Promise((r) => setTimeout(r, 300));
          state = await api("GET", "jobs/" + job.job_id);
          bar.value = state.progress; msg.textContent = `${Math.round(state.progress * 100)}% ${state.message || ""}`;
        }
        if (state.state === "done") {
          const rr = await api("GET", "runs/" + state.run_id);
          showRun(result, rr.record, rr.outputs);
          await refreshHistory();
        } else if (state.state === "blocked") {
          result.replaceChildren(el("div", { class: "card" }, [el("p", { class: "err-text", i18n: "runs.blocked" }), issuesList(state.validation)]));
        } else if (state.state === "cancelled") {
          result.replaceChildren(el("div", { class: "card" }, [el("p", { class: "muted", i18n: "runs.cancelled" })]));
        } else {
          result.replaceChildren(el("div", { class: "card" }, [el("p", { class: "err-text", text: t("msg.error", { message: state.error || state.state }) })]));
        }
        applyI18n(result);
      } catch (e) { fail(e); } finally { btn.disabled = false; }
    } });
    root.append(el("div", { class: "card" }, [
      el("div", { class: "controls" }, [el("label", { class: "field" }, [el("span", { i18n: "runs.engine" }), engineSel])]),
      paramBox, el("label", { class: "field" }, [el("span", { i18n: "runs.question" }), question]), el("div", { class: "spacer" }), btn,
      el("p", { class: "muted small", i18n: "runs.interface_note" })]));
    root.append(el("div", { class: "spacer" }), result, el("div", { class: "spacer" }), el("div", { class: "card" }, [el("h2", { i18n: "runs.history" }), history]),
      el("div", { class: "spacer" }), expectationCard(), el("div", { class: "spacer" }), reproduceCard());
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

  // Reproduce a run from an export package (plan s 7.3 acceptance criterion).
  function reproduceCard() {
    const file = el("input", { type: "file", accept: ".zip,application/zip" }), out = el("div", { class: "small" });
    const btn = el("button", { class: "btn", i18n: "pkg.reproduce", onclick: async () => {
      if (!file.files[0]) { toast(t("coding.choose_file")); return; }
      btn.disabled = true;
      try {
        const buf = new Uint8Array(await file.files[0].arrayBuffer());
        let bin = ""; for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
        const r = await api("POST", "reproduce", { zip_base64: btoa(bin) });
        out.replaceChildren(el("p", { class: r.reproduced ? "ok-text" : "err-text", text: r.reproduced ? t("pkg.ok", { id: r.new_run_id }) : t("pkg.failed", { reason: r.reason }) }),
          r.note ? el("p", { class: "muted", text: r.note }) : "");
        await loadDatasets(S.datasetId);
      } catch (e) { fail(e); } finally { btn.disabled = false; }
    } });
    return el("div", { class: "card" }, [el("h2", { i18n: "pkg.title" }), el("p", { class: "muted small", i18n: "pkg.lede" }),
      el("div", { class: "controls" }, [el("label", { class: "field" }, [el("span", { i18n: "pkg.file" }), file]), btn]), out]);
  }

  // Expectation register (plan s 7.5): list frozen entries; freeze a draft JSON file.
  function expectationCard() {
    const list = el("div"), who = el("input", { type: "text", "data-i18n-placeholder": "rep.frozen_by_ph", placeholder: t("rep.frozen_by_ph") });
    const file = el("input", { type: "file", accept: ".json,application/json" });
    const refresh = async () => {
      const rows = await api("GET", "expectations");
      list.replaceChildren(rows.length ? renderTable(["entry_id", "title", "engine_id", "state", "frozen_utc", "frozen_by", "supersedes", "superseded"], rows)
        : el("p", { class: "empty", i18n: "rep.none" }));
      applyI18n(list);
    };
    const btn = el("button", { class: "btn", i18n: "rep.freeze", onclick: async () => {
      if (!file.files[0] || !who.value.trim()) { toast(t("rep.need_file_and_name")); return; }
      try {
        const entry = JSON.parse(await file.files[0].text());
        const r = await api("POST", "expectations", { entry, frozen_by: who.value });
        toast(t("rep.frozen", { id: r.entry_id })); await refresh();
      } catch (e) { fail(e); }
    } });
    refresh().catch(fail);
    return el("div", { class: "card" }, [el("h2", { i18n: "rep.title" }), el("p", { class: "muted small", i18n: "rep.lede" }), list,
      el("div", { class: "controls", style: "margin-top:10px" }, [el("label", { class: "field" }, [el("span", { i18n: "rep.file" }), file]),
        el("label", { class: "field" }, [el("span", { i18n: "rep.frozen_by" }), who]), btn])]);
  }

  // Replication check against a frozen expectation (plan s 7.5).
  function replicationBox(rec) {
    const box = el("div", { class: "btn-row", style: "margin:8px 0" });
    api("GET", "expectations").then((list) => {
      const usable = list.filter((e) => e.state === "frozen" && e.engine_id === rec.engine.engine_id && !e.superseded);
      if (!usable.length) return;
      const sel = el("select", { class: "select" }, usable.map((e) => el("option", { value: e.entry_id, text: `${e.entry_id} · ${e.title}` })));
      const out = el("div", { class: "small", style: "flex-basis:100%" });
      box.append(el("span", { class: "small muted", i18n: "rep.check_against" }), sel, el("button", { class: "btn btn-ghost", i18n: "rep.check", onclick: async () => {
        try {
          const r = await api("POST", "replications", { entry_id: sel.value, run_id: rec.run_id });
          out.replaceChildren(el("p", {}, [el("strong", { text: t("rep.verdict." + r.verdict) }), `  ${r.passed} / ${r.total}`]),
            r.problems.length ? el("ul", {}, r.problems.map((x) => el("li", { class: "err-text", text: x }))) : "",
            r.note ? el("p", { class: "muted", text: r.note }) : "",
            renderTable(["label", "pass", "statistic", "observed", "missing", "unexpected"], r.comparisons.map((c) => Object.assign({}, c, {
              observed: Array.isArray(c.observed) ? c.observed.join(", ") : c.observed, missing: (c.missing || []).join(", "), unexpected: (c.unexpected || []).join(", ") }))));
          applyI18n(out);
        } catch (e) { fail(e); }
      } }), out);
      applyI18n(box);
    }).catch(() => {});
    return box;
  }

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
          el("a", { class: "btn btn-ghost", href: `/api/runs/${rec.run_id}/record.json`, i18n: "runs.download_record" }),
          el("a", { class: "btn btn-ghost", href: `/api/runs/${rec.run_id}/report.html`, i18n: "runs.download_report" }),
          el("a", { class: "btn btn-ghost", href: `/api/runs/${rec.run_id}/package.zip`, i18n: "runs.download_package" })])]),
      replayOut, replicationBox(rec),
      el("p", { class: "small" }, [el("span", { class: "badge", style: "--c:" + (STATUS_COLOURS[rec.engine.status] || "#64748b"), text: t("status." + rec.engine.status) }), "  ",
        t("track." + rec.engine.track), "  ·  ", t("runs.outcome") + ": ", el("strong", { text: t("outcome." + rec.outcome) }), "  ·  ", rec.dataset.name, " (", t("status." + rec.dataset.data_status), ")"]),
      el("p", { class: "muted small", text: rec.engine.boundary }),
    ];
    if (rec.warnings.length) parts.push(el("ul", { class: "small" }, rec.warnings.map((w) => el("li", { text: w }))));
    for (const [name, out] of Object.entries(outputs || {})) {
      // Charts only for one row per jurisdiction; long tables (one row per draw or reading) are shown as tables.
      if (!out.columns.includes("jurisdiction_id") || new Set(out.rows.map((r) => r.jurisdiction_id)).size !== out.rows.length) {
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

  // ------------------------------------------------------------------ Research Suite (A-share releases)
  // The converter is the Research Suite's own (rscore, vendored and pinned), so that a release is converted here
  // exactly as ResearchSuite.exe converts it. Paths are typed or pasted: a browser cannot hand a folder path over.
  const cleanPath = (s) => String(s || "").trim().replace(/^["']|["']$/g, "");
  let suiteJurs = null;
  async function suiteJurisdictions() {
    if (!suiteJurs) suiteJurs = await api("GET", "suite/jurisdictions");
    return suiteJurs;
  }
  function reasonText(code) { return tOr("suite.reason." + code, code.replace(/_/g, " ")); }
  function reviewStatus(s) { return tOr("suite.review_status." + String(s).replace(/\s+/g, "_"), s); }
  function tableName(tb) { return tOr("table." + tb, tOr("suite.table." + tb, tb)); }
  function busy(btn, on) { btn.disabled = on; btn.classList.toggle("busy", on); }

  PAGES.suite = async function (root) {
    header(root, "suite.title", "suite.lede");
    const status = await api("GET", "suite");
    const core = status.core;
    root.append(el("p", { class: "muted small" }, [t("suite.core", { version: core.rscore_version, commit: (core.commit || "").slice(0, 7) }),
      status.config_found ? "  ·  " + t("suite.config_found") : "  ·  " + t("suite.config_absent")]));

    const projectBox = el("div");
    let projectsNow = status.projects;
    const projectList = el("div");
    async function refreshProjects() { projectsNow = (await api("GET", "suite")).projects; drawProjects(); }
    // ---- release card
    const relPath = el("input", { type: "text", class: "mono", style: "width:100%", value: S.suiteRelease || recall("suite.release") || "",
      "data-i18n-placeholder": "suite.release_ph", placeholder: t("suite.release_ph") });
    const relInfo = el("div");
    const readBtn = el("button", { class: "btn btn-ghost", i18n: "suite.read", onclick: () => readRelease().catch(fail) });
    async function readRelease() {
      const path = cleanPath(relPath.value);
      if (!path) { toast(t("suite.need_path")); return; }
      busy(readBtn, true);
      try {
        const info = await api("POST", "suite/inspect", { release: path });
        store("suite.release", path); S.suiteRelease = path;
        relInfo.replaceChildren(releaseCard(info, projectsNow));
        applyI18n(relInfo);
      } catch (e) { relInfo.replaceChildren(el("p", { class: "err-text", text: e.message })); } finally { busy(readBtn, false); }
    }
    root.append(el("div", { class: "card" }, [el("h2", { i18n: "suite.release_title" }), el("p", { class: "muted small", i18n: "suite.release_lede" }),
      el("div", { class: "controls" }, [el("label", { class: "field", style: "flex:1 1 420px" }, [el("span", { i18n: "suite.release_folder" }), relPath]), readBtn]),
      el("p", { class: "muted small", i18n: "suite.path_hint" }), relInfo]));
    root.append(el("div", { class: "spacer" }));

    function releaseCard(info, projects) {
      const rc = info.row_counts || {};
      const facts = [["suite.r.name", info.name], ["suite.r.created", info.created_utc || ""], ["suite.r.software", info.software || ""],
        ["suite.r.companies", fmt(info.companies.length, 0)], ["suite.r.pseudonymised", t(info.pseudonymised ? "common.yes" : "common.no")],
        ["suite.r.citation", info.citation || ""]];
      const counts = Object.entries(rc).map(([k, v]) => ({ table: tableName(k), rows: v }));
      const target = el("select", { class: "select" }, [el("option", { value: "", text: t("suite.new_project", { name: info.name }) })]
        .concat(projects.filter((p) => p.exists && !p.error).map((p) => el("option", { value: p.path, text: p.name + "  ·  " + t("suite.origin." + p.origin) }))));
      // default: the project this release was imported into before (same name), otherwise a new project
      const same = projects.find((p) => p.exists && !p.error && p.name === info.name);
      if (same) target.value = same.path;
      const all = el("input", { type: "checkbox", checked: true });
      const boxes = info.companies.map((c) => el("input", { type: "checkbox", value: c.security_code, checked: true }));
      const list = el("div", { class: "company-list", hidden: true }, info.companies.map((c, i) => el("label", { class: "field inline" },
        [boxes[i], el("span", { text: `${c.security_code}  ${c.short_name || ""}${c.name_en ? "  (" + c.name_en + ")" : ""}` })])));
      all.addEventListener("change", () => { list.hidden = all.checked; });
      const cons = el("input", { type: "checkbox" }), acc = el("input", { type: "checkbox" });
      const minc = el("input", { type: "number", min: 0, max: 1, step: 0.05, value: 0 });
      const out = el("div");
      const go = el("button", { class: "btn", i18n: "suite.import", onclick: async () => {
        const companies = all.checked ? [] : boxes.filter((b) => b.checked).map((b) => b.value);
        if (!all.checked && !companies.length) { toast(t("suite.no_companies")); return; }
        busy(go, true); out.replaceChildren(el("p", { class: "muted", i18n: "suite.importing" }));
        try {
          const detail = await api("POST", "suite/import", { release: info.folder, project: target.value || null, companies,
            assume_consolidated: cons.checked, accept_suggestions: acc.checked, min_confidence: Number(minc.value) || 0 });
          S.suiteProject = detail.path; store("suite.project", detail.path);
          out.replaceChildren(el("p", { class: "ok-text", text: t("suite.imported", { name: detail.name }) }));
          showProject(detail);
          refreshProjects().catch(fail);
          projectBox.scrollIntoView({ behavior: "smooth", block: "start" });
        } catch (e) { out.replaceChildren(el("p", { class: "err-text", text: e.message })); } finally { busy(go, false); }
      } });
      return el("div", {}, [
        el("div", { class: "grid grid-2" }, [
          el("dl", { class: "side-panel" }, facts.flatMap(([k, v]) => [el("dt", { i18n: k }), el("dd", { text: String(v) })])),
          renderTable(["table", "rows"], counts)]),
        el("h3", { i18n: "suite.options" }),
        el("div", { class: "controls" }, [el("label", { class: "field" }, [el("span", { i18n: "suite.target" }), target]),
          el("label", { class: "field" }, [el("span", { i18n: "suite.min_confidence" }), minc])]),
        el("label", { class: "field inline" }, [all, el("span", { i18n: "suite.all_companies" })]), list,
        el("label", { class: "field inline" }, [cons, el("span", { i18n: "suite.assume_consolidated" })]),
        el("p", { class: "muted small", i18n: "suite.assume_consolidated_help" }),
        el("label", { class: "field inline" }, [acc, el("span", { i18n: "suite.accept_suggestions" })]),
        el("p", { class: "muted small", i18n: "suite.accept_suggestions_help" }),
        el("p", { class: "muted small", i18n: "suite.privacy" }), go, out]);
    }

    // ---- projects card
    const openPath = el("input", { type: "text", class: "mono", style: "width:100%", "data-i18n-placeholder": "suite.open_ph", placeholder: t("suite.open_ph") });
    const openBtn = el("button", { class: "btn btn-ghost", i18n: "suite.open", onclick: async () => {
      const p = cleanPath(openPath.value);
      if (!p) { toast(t("suite.need_path")); return; }
      busy(openBtn, true);
      try { const d = await api("POST", "suite/open", { path: p }); S.suiteProject = d.path; store("suite.project", d.path); showProject(d); await refreshProjects(); }
      catch (e) { fail(e); } finally { busy(openBtn, false); }
    } });
    function drawProjects() {
      const rows = projectsNow.map((p) => ({ name: p.name, origin: t("suite.origin." + p.origin),
        entities: p.counts ? p.counts.entities : "", relations: p.counts ? p.counts.ownership : "",
        latest: p.latest_report || "", state: p.error ? t("suite.damaged") : p.exists ? "" : t("suite.missing"), _p: p }));
      projectList.replaceChildren(rows.length ? renderTable(["name", "origin", "entities", "relations", "latest", "state"], rows, (r) => {
        if (!r._p.exists || r._p.error) return;
        api("GET", "suite/project?path=" + encodeURIComponent(r._p.path)).then((d) => { S.suiteProject = d.path; store("suite.project", d.path); showProject(d); }).catch(fail);
      }) : el("p", { class: "muted", i18n: "suite.no_projects" }));
      applyI18n(projectList);
    }
    drawProjects();
    root.append(el("div", { class: "card" }, [el("h2", { i18n: "suite.projects_title" }), el("p", { class: "muted small", i18n: "suite.projects_lede" }),
      projectList,
      el("p", { class: "muted small", text: t("suite.workspace_folder", { folder: status.workspace_folder }) }),
      el("div", { class: "controls" }, [el("label", { class: "field", style: "flex:1 1 360px" }, [el("span", { i18n: "suite.open_label" }), openPath]), openBtn])]));
    root.append(el("div", { class: "spacer" }), projectBox);

    // ---- one project: review and hand-over
    function showProject(d) {
      const c = d.counts || {};
      const kpis = [["suite.k.entities", c.entities, "#ef4444"], ["suite.k.relations", c.ownership, "#10b981"],
        ["suite.k.revenue", c.entity_financials, "#f59e0b"], ["suite.k.sources", c.sources, "#4338ca"]];
      const parts = [el("h2", { text: t("suite.project_title", { name: d.name }) }), el("p", { class: "muted small mono", text: d.path }),
        el("div", { class: "grid grid-4" }, kpis.map(([k, v, col]) => el("div", { class: "card kpi", style: "--c:" + col }, [
          el("div", { class: "value", text: fmt(v || 0, 0) }), el("div", { class: "label", i18n: k })])))];
      const rep = d.report;
      if (rep) {
        const sm = rep.summary;
        parts.push(el("h3", { text: t("suite.latest", { name: rep.name }) }),
          el("div", { class: "grid grid-2" }, [
            el("div", {}, [el("h4", { i18n: "suite.imported_rows" }), renderTable(["table", "rows"], Object.entries(sm.imported || {}).map(([k, v]) => ({ table: tableName(k), rows: v })))]),
            el("div", {}, [el("h4", { i18n: "suite.rejected_rows" }), renderTable(["table", "reason", "rows"],
              (sm.rejected || []).map((r) => ({ table: tableName(r.table), reason: reasonText(r.reason), rows: r.rows })))])]));
        if ((sm.notes || []).length) parts.push(el("ul", { class: "small" }, sm.notes.map((n) => el("li", { text: n }))));
        parts.push(reviewBlock(d, rep));
        if (rep.revenue_conflicts.length) {
          parts.push(el("h4", { i18n: "suite.revenue_title" }), el("p", { class: "muted small", i18n: "suite.revenue_lede" }),
            renderTable(Object.keys(rep.revenue_conflicts[0]), rep.revenue_conflicts));
        }
      } else parts.push(el("p", { class: "muted", i18n: "suite.no_import" }));
      parts.push(bringBlock(d));
      projectBox.replaceChildren(el("div", { class: "card" }, parts));
      applyI18n(projectBox);
    }

    function reviewBlock(d, rep) {
      const box = el("div");
      if (!rep.review.length) { box.append(el("p", { class: "ok-text", i18n: "suite.review_done" })); return box; }
      const listId = "suite-jur-list";
      const datalist = el("datalist", { id: listId });
      suiteJurisdictions().then((js) => datalist.replaceChildren(...js.map((j) => el("option", { value: j.code, text: j.name })))).catch(fail);
      const inputs = {};
      const table = el("div", { class: "table-wrap" }, [el("table", {}, [
        el("thead", {}, [el("tr", {}, ["name", "status", "suggestion", "rows", "choice"].map((c) => el("th", { text: t("suite.col." + c) })))]),
        el("tbody", {}, rep.review.map((r) => {
          const inp = el("input", { type: "text", list: listId, class: "mono", style: "width:7em", value: r.chosen || "", "aria-label": t("suite.col.choice") + ": " + r.name });
          inputs[r.name] = inp;
          const use = r.suggestion && !r.suggestion.includes("/") ? el("button", { class: "btn btn-ghost btn-small", text: t("suite.use", { code: r.suggestion }), onclick: () => { inp.value = r.suggestion; } }) : null;
          const opts = r.suggestion && r.suggestion.includes("/") ? r.suggestion.split("/").map((code) => el("button", { class: "btn btn-ghost btn-small", text: code, onclick: () => { inp.value = code; } })) : [];
          return el("tr", {}, [el("td", { text: r.name }), el("td", { text: reviewStatus(r.status) }), el("td", {}, [use || "", ...opts]),
            el("td", { class: "num", text: fmt(r.rows, 0) }), el("td", {}, [inp])]);
        }))])]);
      const save = async (again) => {
        const choices = {};
        for (const [name, inp] of Object.entries(inputs)) choices[name] = inp.value.trim().toUpperCase();
        try {
          let nd = await api("POST", "suite/overrides", { project: d.path, choices });
          if (again) nd = await api("POST", "suite/reimport", { project: d.path });
          toast(t(again ? "suite.reimported" : "suite.saved")); showProject(nd);
        } catch (e) { fail(e); }
      };
      box.append(el("h4", { text: t("suite.review_title", { n: rep.review.length }) }), el("p", { class: "muted small", i18n: "suite.review_lede" }), datalist, table,
        el("div", { class: "btn-row" }, [el("button", { class: "btn btn-ghost", i18n: "suite.save", onclick: () => save(false) }),
          el("button", { class: "btn", i18n: "suite.save_reimport", onclick: () => save(true) })]));
      return box;
    }

    function bringBlock(d) {
      const name = el("input", { type: "text", value: d.name + " (Research Suite)" });
      const trim = el("input", { type: "checkbox", checked: true });
      const out = el("div");
      const go = el("button", { class: "btn", i18n: "suite.bring", onclick: async () => {
        busy(go, true);
        try {
          const res = await api("POST", "suite/bring", { project: d.path, name: name.value, trim_jurisdictions: trim.checked });
          out.replaceChildren(el("p", { class: res.saved ? "ok-text" : "err-text", text: res.saved ? t(res.already_present ? "suite.brought_same" : "suite.brought", { id: res.dataset_id }) : t("data.import_blocked") }), issuesList(res.validation));
          if (res.saved) { await loadDatasets(res.dataset_id); toast(t("data.import_ok", { id: res.dataset_id })); }
        } catch (e) { fail(e); } finally { busy(go, false); }
      } });
      const exports = (d.lab_exports || []).map((x) => ({ name: x.name, _x: x }));
      return el("div", {}, [el("h3", { i18n: "suite.bring_title" }), el("p", { class: "muted small", i18n: "suite.bring_lede" }),
        el("div", { class: "controls" }, [el("label", { class: "field", style: "flex:1 1 320px" }, [el("span", { i18n: "data.import_name_label" }), name])]),
        el("label", { class: "field inline" }, [trim, el("span", { i18n: "suite.trim" })]), el("p", { class: "muted small", i18n: "suite.trim_help" }),
        el("div", { class: "btn-row" }, [go, el("a", { class: "btn btn-ghost", href: "#/overview", i18n: "suite.go_overview" })]), out,
        exports.length ? el("details", {}, [el("summary", { i18n: "suite.previous_exports" }), renderTable(["name"], exports, async (r) => {
          try {
            const res = await api("POST", "suite/import_export", { folder: r._x.path, trim_jurisdictions: trim.checked });
            if (res.saved) { await loadDatasets(res.dataset_id); toast(t("data.import_ok", { id: res.dataset_id })); }
            else out.replaceChildren(issuesList(res.validation));
          } catch (e) { fail(e); }
        })]) : null]);
    }

    if (S.suiteRelease && relPath.value) readRelease().catch(fail);
    const remembered = S.suiteProject || recall("suite.project");
    if (remembered) api("GET", "suite/project?path=" + encodeURIComponent(remembered)).then((d) => { S.suiteProject = d.path; showProject(d); }).catch(() => { /* moved or deleted */ });
  };

  // Provenance of the selected dataset: where a Research Suite import or a completed dataset came from.
  function provenanceCard(d) {
    const m = d.metadata || {};
    if (m.origin !== "research_suite" && m.origin !== "derived") return null;
    const rows = [];
    if (m.origin === "derived") {
      rows.push(["prov.derived_from", `${m.derived_from_name || ""} (${m.derived_from})`], ["prov.mode", t("prov.mode." + m.mode)],
        ["prov.tables_changed", Object.entries(m.tables_changed || {}).map(([k, v]) => `${tableName(k)}: ${v}`).join("; ")]);
    }
    const s = m.origin === "research_suite" ? m : (m.parent_metadata && m.parent_metadata.origin === "research_suite" ? m.parent_metadata : null);
    if (s) {
      rows.push(["prov.release", s.release || ""], ["prov.project", s.suite_project || ""], ["prov.core", `rscore ${s.rscore_version} · ${(s.commit || "").slice(0, 7)}`],
        ["prov.review_outstanding", String(s.review_outstanding ?? "")], ["prov.revenue_conflicts", String(s.revenue_conflicts ?? "")],
        ["prov.dropped", String(s.unused_registry_jurisdictions_dropped ?? "")]);
      if (s.import_settings) rows.push(["prov.settings", t("prov.settings_text", { cons: t(s.import_settings.assume_consolidated ? "common.yes" : "common.no"),
        acc: t(s.import_settings.accept_suggestions ? "common.yes" : "common.no"), conf: s.import_settings.min_confidence, overrides: s.import_settings.overrides_used })]);
    }
    return el("div", { class: "card" }, [el("h2", { i18n: "prov.title" }), el("p", { class: "muted small", i18n: m.origin === "derived" ? "prov.lede_derived" : "prov.lede_suite" }),
      el("dl", { class: "side-panel" }, rows.flatMap(([k, v]) => [el("dt", { i18n: k }), el("dd", { text: v })]))]);
  }

  // Complete a dataset (GDP, tax rules): a new dataset with tables added or replaced; the original is kept.
  function completeForm() {
    if (!S.dataset) return null;
    const file = el("input", { type: "file", accept: ".zip,.csv", multiple: true });
    const mode = el("select", { class: "select" }, [el("option", { value: "merge", i18n: "complete.merge" }), el("option", { value: "replace", i18n: "complete.replace" })]);
    const name = el("input", { type: "text", value: S.dataset.name + " (completed)" });
    const out = el("div");
    const real = S.dataset.jurisdictions.filter((j) => /^[A-Z]{3}$/.test(j));
    const go = el("button", { class: "btn", i18n: "complete.go", onclick: async () => {
      if (!file.files.length) { toast(t("coding.choose_file")); return; }
      busy(go, true); out.replaceChildren();
      try {
        const tables = {};
        for (const f of file.files) {
          if (/\.zip$/i.test(f.name)) {
            const buf = new Uint8Array(await f.arrayBuffer());
            let bin = ""; for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
            const res = await api("POST", "datasets/" + S.datasetId + "/derive", { name: name.value, mode: mode.value, zip_base64: btoa(bin) });
            return finish(res);
          }
          tables[f.name.replace(/\.csv$/i, "").toLowerCase()] = await f.text();
        }
        finish(await api("POST", "datasets/" + S.datasetId + "/derive", { name: name.value, mode: mode.value, tables }));
      } catch (e) { out.replaceChildren(el("p", { class: "err-text", text: e.message })); } finally { busy(go, false); }
    } });
    async function finish(res) {
      const skippedRows = Object.values(res.unfilled_rows_skipped || {}).reduce((a, b) => a + b, 0);
      out.replaceChildren(el("p", { class: res.saved ? "ok-text" : "err-text", text: res.saved ? t("complete.done", { id: res.dataset_id }) : t("data.import_blocked") }),
        skippedRows ? el("p", { class: "muted small", text: t("complete.skipped", { n: skippedRows }) }) : "", issuesList(res.validation));
      if (res.saved) { await loadDatasets(res.dataset_id); toast(t("complete.done", { id: res.dataset_id })); }
    }
    return el("div", { class: "card" }, [el("h2", { i18n: "complete.title" }), el("p", { class: "muted small", i18n: "complete.lede" }),
      real.length ? el("a", { class: "btn btn-ghost", href: `/api/datasets/${S.datasetId}/completion_template.zip`, download: "", text: t("complete.template", { n: real.length }) })
        : el("p", { class: "muted small", i18n: "complete.no_real" }),
      el("div", { class: "controls", style: "margin-top:12px" }, [el("label", { class: "field" }, [el("span", { i18n: "complete.files" }), file]),
        el("label", { class: "field" }, [el("span", { i18n: "complete.mode" }), mode]),
        el("label", { class: "field", style: "flex:1 1 260px" }, [el("span", { i18n: "data.import_name_label" }), name])]),
      el("p", { class: "muted small", i18n: "complete.mode_help" }), go, out]);
  }

  // ------------------------------------------------------------------ boot
  // Start-up hand-over from the command line or ResearchSuite.exe (taxnetlab --import PATH --language TAG).
  function startup() {
    const m = document.querySelector('meta[name="taxnetlab-startup"]');
    try { const v = m && m.content && m.content !== "__STARTUP__" ? JSON.parse(m.content) : {}; return v && typeof v === "object" ? v : {}; }
    catch (e) { return {}; }
  }
  async function boot() {
    const start = startup();
    const loc = await api("GET", "locales");
    S.locales = loc.locales;
    const tagsAll = S.locales.map((l) => l.tag);
    const forced = start.locale && tagsAll.includes(start.locale) && (start.force_locale || !recall("locale")) ? start.locale : null;
    const want = forced || recall("locale");
    const browser = (navigator.languages || [navigator.language || ""]);
    const tags = S.locales.map((l) => l.tag);
    const pick = (want && tags.includes(want)) ? want : (browser.find((b) => tags.includes(b)) || loc.default);
    const lsel = document.getElementById("locale-select");
    lsel.replaceChildren(...S.locales.map((l) => el("option", { value: l.tag, text: l.native_name })));
    lsel.value = pick;
    await loadLocale(pick);
    lsel.addEventListener("change", async () => { try { await loadLocale(lsel.value); await loadDataset(); await route(); } catch (e) { fail(e); } });
    // Display theme (plan s 11.1 smoke test, step 6): system, light or dark; charts are redrawn in the new colours.
    const themeSel = document.getElementById("theme-select");
    const applyTheme = (v) => { if (v === "system") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = v; };
    themeSel.value = ["light", "dark"].includes(recall("theme")) ? recall("theme") : "system";
    applyTheme(themeSel.value);
    themeSel.addEventListener("change", async () => { applyTheme(themeSel.value); store("theme", themeSel.value); await route(); });
    S.mode = recall("mode") === "technical" ? "technical" : "plain";
    const msel = document.getElementById("mode-select");
    msel.value = S.mode;
    msel.addEventListener("change", async () => { S.mode = msel.value; store("mode", S.mode); applyI18n(); await route(); });
    S.engines = await api("GET", "engines");
    if (start.release) S.suiteRelease = start.release;
    if (start.project) { S.suiteProject = start.project; store("suite.project", start.project); }
    await loadDatasets(start.dataset_id || undefined);
    if (start.page && PAGES[start.page]) history.replaceState(null, "", "#/" + start.page);
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
