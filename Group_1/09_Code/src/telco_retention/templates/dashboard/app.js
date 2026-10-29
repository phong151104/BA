// UI of the single-file dashboard: the pages of app/Home.py, drawn from the embedded run results and the engine.
"use strict";
(function () {
  const E = Engine, cfg0 = DATA.config, ev = DATA.evidence;
  const BLUE = "#2a78d6", ORANGE = "#eb6834", AQUA = "#1baf7a", GREY = "#b9b8b2", INK = "#0b0b0b", MUTED = "#898781", RED = "#d03b3b";
  const PAGES = ["Decision", "Assumptions & sensitivity", "Model evidence"];
  const MODES = { ev: "Single standard offer", segment_offers: "Segment-specific offers" };
  const LIVE_DRAWS = 2000;
  const demo = E.rows(DATA.customers);
  const standardId = cfg0.campaign.default_offer;
  const S = { page: "Decision", source: "demo", uploaded: null, search: "", selectedOnly: true, explain: null, tab: "Performance",
    gridView: "retarget", scenario: null, upload: null, shapCustomer: null, compareOpen: false };

  // ---- formatting ------------------------------------------------------------------------------------------
  const missing = (x) => x == null || (typeof x === "number" && !isFinite(x));
  const usd = (x, d = 0) => (missing(x) ? "n/a" : (x < 0 ? "-$" : "$") + Math.abs(x).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }));
  const pct = (x, d = 1) => (missing(x) ? "n/a" : (x * 100).toFixed(d) + "%");
  const num = (x, d = 0) => (missing(x) ? "n/a" : Number(x).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }));
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const $ = (id) => document.getElementById(id);
  const median = (xs) => { if (!xs.length) return null; const s = [...xs].sort((a, b) => a - b), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  const mean = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);

  function table(rows, columns, cls = "") {
    const head = columns.map((c) => `<th class="${c.num ? "num" : ""}">${esc(c.label)}</th>`).join("");
    const body = rows.map((r) => "<tr>" + columns.map((c) => {
      const v = c.fmt ? c.fmt(r[c.key], r) : r[c.key];
      return `<td class="${c.num ? "num" : ""}">${c.html ? v : esc(missing(v) ? "n/a" : v)}</td>`;
    }).join("") + "</tr>").join("");
    return `<table class="data ${cls}"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  }
  const metric = (label, value, delta, cls = "", help = "") => `<div class="metric" title="${esc(help)}"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div>${delta ? `<div class="delta ${cls}">${esc(delta)}</div>` : ""}</div>`;
  const chart = (id, height = 420) => `<div class="chart" id="${id}" style="height:${height}px"></div>`;
  function plot(id, traces, layout) {
    const el = $(id);
    if (!el) return;
    Plotly.newPlot(el, traces, { margin: { l: 70, r: 20, t: 50, b: 55 }, paper_bgcolor: "#fff", plot_bgcolor: "#fff", font: { family: "Segoe UI, Arial, sans-serif", size: 12, color: INK },
      legend: { orientation: "h", y: -0.18 }, ...layout }, { displaylogo: false, responsive: true });
  }
  function download(name, text, type = "text/csv") {
    const blob = new Blob([type === "text/csv" ? "\uFEFF" + text : text], { type });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }
  function csv(rows, columns) {
    columns = columns || Object.keys(rows[0] || {});
    const cell = (v) => { if (v == null || (typeof v === "number" && !isFinite(v))) return ""; const s = String(v); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
    return [columns.join(","), ...rows.map((r) => columns.map((c) => cell(r[c])).join(","))].join("\n");
  }

  // ---- assumptions: one set of controls shared by every page ------------------------------------------------
  function scores() { return S.source === "upload" && S.uploaded ? S.uploaded : demo; }
  function defaults() {
    const std = E.defaultOffer(cfg0), v = cfg0.value;
    const c = { mode: DATA.recommended_strategy, save_rate: std.save_rate, offer_cost: std.offer_cost, contact: std.contact_cost, margin: v.margin,
      horizon: v.base_horizon_months, discount: v.discount_rate_annual, segments: [...E.SEGMENTS], budget_demo: E.campaignBudget(demo.length, cfg0), budget_upload: null };
    for (const s of E.SEGMENTS) c["tenure_" + s] = v.tenure_factors[s];
    for (const o of cfg0.offers) if (o.offer_id !== standardId) { c["cost_" + o.offer_id] = o.offer_cost; c["rate_" + o.offer_id] = o.save_rate; }
    return c;
  }
  const C = defaults();
  const budgetKey = () => (S.source === "upload" ? "budget_upload" : "budget_demo");
  function budget() { if (C[budgetKey()] == null) C[budgetKey()] = E.campaignBudget(scores().length, cfg0); return C[budgetKey()]; }

  function settings() {
    const cfg = JSON.parse(JSON.stringify(cfg0));
    const std = E.defaultOffer(cfg);
    std.save_rate = C.save_rate; std.offer_cost = C.offer_cost;
    cfg.value.margin = C.margin; cfg.value.base_horizon_months = C.horizon; cfg.value.discount_rate_annual = C.discount;
    for (const s of E.SEGMENTS) cfg.value.tenure_factors[s] = C["tenure_" + s];
    for (const o of cfg.offers) {
      o.contact_cost = C.contact;
      if (C.mode === "segment_offers" && o.offer_id !== standardId) { o.offer_cost = C["cost_" + o.offer_id]; o.save_rate = C["rate_" + o.offer_id]; }
    }
    return cfg;
  }

  // ---- the campaign for the current list and assumptions, cached until a control changes ----------------------
  let cache = null;
  function current() {
    const key = JSON.stringify([C, S.source, S.uploaded ? S.uploaded.length : 0]);
    if (cache && cache.key === key) return cache;
    const start = performance.now();
    const cfg = settings(), b = budget();
    const population = scores().filter((r) => C.segments.includes(E.tenureSegment(r.tenure)));
    const offers = E.strategyOffers(cfg, C.mode);
    let target = null, baseline = null;
    if (population.length) {
      target = E.campaign(population, b, cfg, offers, "ev", DATA.thresholds);
      baseline = E.campaign(population, b, cfg, [E.defaultOffer(cfg)], "risk", DATA.thresholds);
    }
    cache = { key, cfg, budget: b, population, offers, target, baseline, seconds: (performance.now() - start) / 1000, mc: null };
    return cache;
  }
  const labelled = () => scores().length > 0 && scores()[0].churn != null;

  // ---- widgets -------------------------------------------------------------------------------------------------
  const numberField = (key, label, step, min = 0) => `<div class="field"><label for="f_${key}">${esc(label)}</label><input type="number" id="f_${key}" data-key="${key}" step="${step}" min="${min}" value="${C[key]}"></div>`;
  const slider = (key, label, max = 1, fmt = (v) => pct(v, 0)) => `<div class="field"><label for="f_${key}">${esc(label)} <span class="val" id="v_${key}">${fmt(C[key])}</span></label><input type="range" id="f_${key}" data-key="${key}" min="0" max="${max}" step="0.01" value="${C[key]}"></div>`;
  const modeSelect = () => `<div class="field"><label for="f_mode">Offer policy</label><select id="f_mode" data-key="mode">${Object.entries(MODES).map(([k, v]) => `<option value="${k}" ${C.mode === k ? "selected" : ""}>${v}</option>`).join("")}</select></div>`;
  function bindControls(root) {
    root.querySelectorAll("[data-key]").forEach((el) => {
      const key = el.dataset.key;
      if (el.type === "range") el.addEventListener("input", () => { const v = $("v_" + key); if (v) v.textContent = pct(Number(el.value), 0); });
      el.addEventListener("change", () => {
        if (key === "mode") C.mode = el.value;
        else { const v = Number(el.value); if (!isFinite(v) || v < 0) { el.value = C[key]; return; } C[key] = v; }
        render();
      });
    });
    root.querySelectorAll("[data-segment]").forEach((el) => el.addEventListener("change", () => {
      C.segments = [...root.querySelectorAll("[data-segment]")].filter((x) => x.checked).map((x) => x.dataset.segment);
      render();
    }));
  }

  function strip(c) {
    const offer = E.defaultOffer(c.cfg), v = c.cfg.value;
    const factors = E.SEGMENTS.map((s) => +v.tenure_factors[s].toFixed(4)).join("/");
    const extra = C.mode === "segment_offers" ? ` · ${c.offers.length} offers in catalog` : "";
    return `<div class="strip"><b>Assumptions</b> · Budget <b>${usd(c.budget)}</b> for ${num(c.population.length)} customers · Offer <b>${esc(offer.label)}</b>:
      ${usd(offer.offer_cost)} + ${usd(offer.contact_cost)} contact, save rate <b>${pct(offer.save_rate, 0)}</b>${extra} · Margin <b>${pct(v.margin, 0)}</b> ·
      Value horizon <b>${+v.base_horizon_months.toFixed(2)} months</b> (x${factors} by tenure) · Discount <b>${pct(v.discount_rate_annual, 0)}/yr</b></div>`;
  }

  // ---- sidebar -------------------------------------------------------------------------------------------------
  function sidebar() {
    const sources = [["demo", "Demo: held-out test customers"], ...(S.uploaded ? [["upload", "Uploaded CSV"]] : [])];
    $("sidebar").innerHTML = `<h2>◈ Retention Lab</h2><div class="sub">Profit-aware churn &amp; retention targeting</div>
      <div class="nav">${PAGES.map((p) => `<button data-page="${p}" class="${S.page === p ? "active" : ""}">${p}</button>`).join("")}</div>
      <label>Customer list<select id="source">${sources.map(([k, v]) => `<option value="${k}" ${S.source === k ? "selected" : ""}>${v}</option>`).join("")}</select></label>
      <div class="note">${num(scores().length)} customers · model: ${esc(DATA.model_name)}</div><hr>
      <div class="note">Money figures are expected values under the visible assumptions (USD of the sample company), not realised profit or measured uplift.</div>
      <div class="note">Single-file edition: the scores, model evidence and model come from pipeline run <code>${esc(DATA.run_id)}</code>; every campaign is computed in this browser.</div>`;
    $("sidebar").querySelectorAll("[data-page]").forEach((b) => b.addEventListener("click", () => { S.page = b.dataset.page; render(); window.scrollTo(0, 0); }));
    $("source").addEventListener("change", (e) => { S.source = e.target.value; render(); });
  }

  // ---- Decision ------------------------------------------------------------------------------------------------
  function decisionPage(c) {
    const lab = labelled();
    let html = `<div class="hero"><h2>Which customers should get a retention offer?</h2><p>Spend a fixed budget where churn risk and customer value together return the most - and know when not to spend.</p></div>
      <div class="row c4">${numberField(budgetKey(), "Budget (USD)", 100)}${modeSelect()}</div>`;
    if (!c.population.length) return html + `<div class="box info">No customers in the selected tenure segments.</div>`;
    const s = c.target.stats, base = c.baseline.stats;
    html += strip(c);
    if (!s.selected_count) html += `<div class="box info">Nobody is selected: no customer has positive expected value under these assumptions, or the budget is below one offer. Not running the campaign is the right decision here.</div>`;
    const delta = s.expected_net_value - base.expected_net_value;
    const precision = lab ? s.precision_contacted : s.expected_precision;
    html += `<div class="row c5">
      ${metric("Expected net value", usd(s.expected_net_value), `${usd(delta)} vs risk-only`, delta >= 0 ? "up" : "down", "Sum of p(churn) x save rate x customer value - offer and contact cost, for the contacted list. Delta: same budget spent on the highest-risk customers.")}
      ${metric("ROI", pct(s.roi), "", "", "Expected net value / campaign cost.")}
      ${metric("Customers contacted", num(s.selected_count), `${usd(s.cost)} spent`, "", "Customers who receive an offer within the budget and contact cap.")}
      ${metric("Precision among contacted", pct(precision), lab ? "" : "expected (no labels)", "", "Share of contacted customers who actually churned (labelled data) or their mean predicted churn probability (unlabelled).")}
      ${metric("High-risk/high-value coverage", pct(s.high_risk_high_value_coverage), `risk-only: ${pct(base.high_risk_high_value_coverage)}`, "", "Share of high-risk and high-value customers (validation 75th percentiles) that the list reaches.")}</div>`;
    const options = E.offerOptions(E.valueCustomers(c.population, c.cfg), c.offers);
    const be = E.breakEven(c.target.table, c.cfg, options);
    if (s.selected_count) {
      html += `<div class="box ok"><b>Recommended action:</b> offer <b>${num(s.selected_count)} customers</b> a retention offer for <b>${usd(s.cost)}</b>. Expected net value <b>${usd(s.expected_net_value)}</b>
        (ROI ${pct(s.roi, 0)}), <b>${usd(delta)} more</b> than spending the same budget on the highest-risk customers. The list pays off only if its offers keep at least
        <b>${pct(be.break_even_mix_save_rate)}</b> of would-be churners on average (assumed ${pct(be.mix_save_rate)}), so test it in a pilot before scaling.</div>`;
    }
    // Who gets an offer
    const t = c.target.table, picked = t.filter((r) => r.selected), rest = t.filter((r) => !r.selected);
    const share = (rs, f) => (rs.length ? pct(rs.filter(f).length / rs.length, 0) : "n/a");
    const traits = [["Fibre internet", (r) => r.InternetService === "Fiber optic"], ["Month-to-month contract", (r) => r.Contract === "Month-to-month"],
      ["Pays by electronic check", (r) => r.PaymentMethod === "Electronic check"], ["Tenure 12 months or less", (r) => r.tenure_segment === "new"]];
    if (t.length && t[0].SeniorCitizen != null) traits.push(["Senior", (r) => String(r.SeniorCitizen) === "1"]);
    const profile = traits.map(([name, f]) => ({ who: name, list: share(picked, f), rest: share(rest, f), all: share(t, f) }));
    profile.push({ who: "Median monthly bill", list: picked.length ? usd(median(picked.map((r) => r.MonthlyCharges))) : "n/a", rest: usd(median(rest.map((r) => r.MonthlyCharges))), all: usd(median(t.map((r) => r.MonthlyCharges))) });
    const riskSelected = new Set(c.baseline.table.filter((r) => r.selected).map((r) => r.customer_id));
    const matrix = E.QUADRANTS.map((q) => ({ quadrant: q, customers: 0, value_at_risk: 0, contacted: 0, risk_only: 0 }));
    for (const r of t) {
      const m = matrix[E.QUADRANTS.indexOf(E.quadrant(r, DATA.thresholds))];
      m.customers++; m.value_at_risk += r.churn_probability * r.customer_value; m.contacted += r.selected ? 1 : 0; m.risk_only += riskSelected.has(r.customer_id) ? 1 : 0;
    }
    const totalRisk = matrix.reduce((a, m) => a + m.value_at_risk, 0);
    html += `<h3>Who gets an offer, and who does not</h3><div class="row split"><div>${table(profile, [{ key: "who", label: "Customers who..." }, { key: "list", label: "On the list", num: true },
      { key: "rest", label: "Not contacted", num: true }, { key: "all", label: "All", num: true }])}</div>
      <div>${table(matrix, [{ key: "quadrant", label: "Segment (validation cut-offs)" }, { key: "customers", label: "Customers", num: true, fmt: (v) => num(v) },
        { key: "value_at_risk", label: "Value at risk", num: true, fmt: (v) => pct(totalRisk ? v / totalRisk : null) }, { key: "contacted", label: "This plan", num: true }, { key: "risk_only", label: "Risk-only", num: true }])}</div></div>
      <div class="caption">Low-risk customers get no offer: most would stay anyway. High-risk, low-value customers get few: their remaining value rarely repays an offer, which is where risk-only targeting spends its budget.</div>
      ${chart("riskValue", 460)}`;
    html += `<details id="compare" ${S.compareOpen ? "open" : ""}><summary>Compare targeting rules at the same budget</summary><div id="compareBody"></div>
      <div class="caption">Same customers, budget and assumptions. Risk and value rules ignore expected value; 'positive EV only' drops customers with non-positive EV, then ranks by risk.</div></details>`;
    // Action list
    html += `<h3>Action list</h3><div class="row c3"><div class="field"><label for="search">Search customer ID (filters the view only)</label><input type="text" id="search" value="${esc(S.search)}"></div>
      <div class="field"><label>&nbsp;</label><label class="checks"><input type="checkbox" id="selectedOnly" ${S.selectedOnly ? "checked" : ""}> Customers who get an offer only</label></div></div>
      <div id="actionList"></div>
      <details><summary>Why is a customer in or out of the list?</summary><div class="field" style="margin-top:8px"><select id="explainCustomer"></select></div><div id="explainText"></div>
        <div class="caption">This is the economic formula, not a cause of churn or proof that the offer works. With several offers the optimiser maximises total value within budget, so a customer's individually best offer is not always chosen.</div></details>
      <button class="primary" id="exportList">Export contact list (CSV)</button><button class="secondary" id="exportAll">Export full targeting table (CSV)</button><button class="secondary" id="exportAssumptions">Export assumptions and summary (JSON)</button>
      <details><summary>Technical details</summary><p>Run <code>${esc(DATA.run_id)}</code> · model: ${esc(DATA.model_name)} · solver: ${esc(s.solver)} · computed in ${c.seconds.toFixed(2)}s · budget used ${usd(s.cost)} of ${usd(c.budget)} ·
        expected customers saved ${num(s.expected_saved, 1)} · contact cap ${s.max_contacts == null ? "none" : num(s.max_contacts)}</p>
        <div class="caption">The optimiser is an exact dynamic programme over the budget in whole cost units (the pipeline uses an integer programme; both find the same optimum).
        ${s.solver.startsWith("near_optimal") ? "Here it ran in an approximate mode, so global optimality is not proven." : ""}</div></details>`;
    $("main").innerHTML = html;
    bindControls($("main"));
    // Chart: risk x value
    const offerLabels = Object.fromEntries(c.cfg.offers.map((o) => [o.offer_id, o.label]));
    const trace = (rs, name, color) => ({ type: "scattergl", mode: "markers", name, x: rs.map((r) => r.churn_probability), y: rs.map((r) => r.customer_value), marker: { color, size: 6, opacity: 0.75 },
      text: rs.map((r) => `${r.customer_id}<br>${r.tenure_segment} · ${offerLabels[r.offer_id] || r.offer_id}<br>EV ${usd(r.expected_net_value, 2)}`), hovertemplate: "%{text}<extra></extra>" });
    plot("riskValue", [trace(rest, "No offer", GREY), trace(picked, "Gets an offer", BLUE)], {
      title: { text: "Risk x value: who gets an offer" }, xaxis: { title: "Predicted churn probability" }, yaxis: { title: "Customer value proxy (USD)" },
      shapes: [{ type: "line", x0: DATA.thresholds.risk, x1: DATA.thresholds.risk, yref: "paper", y0: 0, y1: 1, line: { dash: "dash", color: MUTED, width: 1 } },
        { type: "line", y0: DATA.thresholds.value, y1: DATA.thresholds.value, xref: "paper", x0: 0, x1: 1, line: { dash: "dash", color: MUTED, width: 1 } }],
      annotations: [{ x: DATA.thresholds.risk, yref: "paper", y: 1, text: "high risk", showarrow: false, xanchor: "left" }, { xref: "paper", x: 1, y: DATA.thresholds.value, text: "high value", showarrow: false, xanchor: "right", yanchor: "top" }] });
    // Compare rules (computed when opened)
    const fillCompare = () => {
      const rows = E.COMPARED.map((strategy) => {
        const item = E.campaign(c.population, c.budget, c.cfg, E.strategyOffers(c.cfg, strategy), strategy === "segment_offers" ? "ev" : strategy, DATA.thresholds).stats;
        return { rule: E.STRATEGY_LABELS[strategy], customers: num(item.selected_count), cost: usd(item.cost), net: usd(item.expected_net_value), roi: pct(item.roi, 0),
          precision: pct(lab ? item.precision_contacted : item.expected_precision, 0), coverage: pct(item.high_risk_high_value_coverage, 0) };
      });
      $("compareBody").innerHTML = table(rows, [{ key: "rule", label: "Targeting rule" }, { key: "customers", label: "Customers", num: true }, { key: "cost", label: "Cost", num: true },
        { key: "net", label: "Expected net value", num: true }, { key: "roi", label: "ROI", num: true }, { key: "precision", label: "Precision among contacted" + (lab ? "" : " (expected)"), num: true },
        { key: "coverage", label: "High-risk/high-value coverage", num: true }]);
    };
    if (S.compareOpen) fillCompare();
    $("compare").addEventListener("toggle", (e) => { S.compareOpen = e.target.open; if (S.compareOpen) fillCompare(); });
    // Action list
    const visible = () => {
      let rs = S.selectedOnly ? picked : t;
      if (S.search) rs = rs.filter((r) => r.customer_id.toLowerCase().includes(S.search.toLowerCase()));
      return rs;
    };
    const drawList = () => {
      const rs = visible();
      $("actionList").innerHTML = `<div class="scroll">${table(rs, [{ key: "customer_id", label: "Customer" }, { key: "churn_probability", label: "Churn probability", num: true, fmt: (v) => pct(v) },
        { key: "customer_value", label: "Value", num: true, fmt: (v) => usd(v, 2) }, { key: "offer_id", label: "Offer", fmt: (v) => offerLabels[v] || v }, { key: "total_cost", label: "Cost", num: true, fmt: (v) => usd(v, 2) },
        { key: "expected_net_value", label: "Expected net value", num: true, fmt: (v) => usd(v, 2) }, { key: "selection_reason", label: "Why" }])}</div><div class="caption">${num(rs.length)} rows</div>`;
      const sel = $("explainCustomer");
      sel.innerHTML = rs.map((r) => `<option ${r.customer_id === S.explain ? "selected" : ""}>${esc(r.customer_id)}</option>`).join("");
      drawExplain();
    };
    const drawExplain = () => {
      const id = $("explainCustomer").value, r = t.find((x) => x.customer_id === id);
      S.explain = id || null;
      $("explainText").innerHTML = r ? `<p>${esc(r.selection_reason)}</p><p>${esc(r.decision_detail)}</p>` : "";
    };
    drawList();
    $("search").addEventListener("input", (e) => { S.search = e.target.value; drawList(); });
    $("selectedOnly").addEventListener("change", (e) => { S.selectedOnly = e.target.checked; drawList(); });
    $("explainCustomer").addEventListener("change", drawExplain);
    const exportColumns = ["customer_id", "churn_probability", "churn", "tenure", "tenure_segment", "MonthlyCharges", "Contract", "InternetService", "TechSupport", "PaymentMethod", "SeniorCitizen",
      "remaining_months", "discounted_months", "customer_value", "offer_id", "assumed_save_rate", "offer_cost", "contact_cost", "total_cost", "expected_saved_probability",
      "expected_retained_value", "expected_net_value", "break_even_save_rate", "break_even_probability", "selected", "selection_reason", "decision_detail"];
    $("exportList").addEventListener("click", () => download("selected_customers.csv", csv(picked, exportColumns)));
    $("exportAll").addEventListener("click", () => download("targeting_all.csv", csv(t, exportColumns)));
    $("exportAssumptions").addEventListener("click", () => download("assumptions_and_summary.json", JSON.stringify({ run_id: DATA.run_id, budget: c.budget, strategy: C.mode,
      value: c.cfg.value, offers: c.offers, summary: s }, null, 2), "application/json"));
  }

  // ---- Assumptions & sensitivity -----------------------------------------------------------------------------------
  function assumptionsPage(c) {
    const std = E.defaultOffer(cfg0);
    let html = `<div class="hero"><h2>What if the assumptions are wrong?</h2><p>Every number the decision rests on is set here. The list, KPIs and risk of a loss update at once.</p></div>
      <div class="row c4">${numberField(budgetKey(), "Budget (USD)", 100)}${modeSelect()}${slider("save_rate", "Save rate of the standard offer")}${numberField("offer_cost", "Standard offer cost (USD)", 1)}</div>
      <div class="row c4">${numberField("contact", "Contact cost per customer (USD)", 0.5)}${slider("margin", "Contribution margin")}${numberField("horizon", "Value horizon (months)", 1)}${slider("discount", "Annual discount rate", 0.5)}</div>
      <div class="row c4">${numberField("tenure_new", "Horizon factor: new (<=12 months)", 0.05)}${numberField("tenure_developing", "Horizon factor: developing (13-24)", 0.05)}${numberField("tenure_loyal", "Horizon factor: loyal (>24)", 0.05)}</div>
      <div class="field checks"><label style="display:block">Eligible tenure segments</label>${E.SEGMENTS.map((s) => `<label><input type="checkbox" data-segment="${s}" ${C.segments.includes(s) ? "checked" : ""}> ${s}</label>`).join("")}</div>`;
    if (C.mode === "segment_offers") {
      html += `<div class="caption">Segment-specific offers: each customer can only receive offers whose eligibility rule they meet; the optimiser picks the best mix within budget.</div>`;
      for (const o of cfg0.offers) {
        if (o.offer_id === std.offer_id) continue;
        const rule = Object.entries(o.eligibility || {}).map(([k, v]) => `${k}: ${v.join(", ")}`).join("; ") || "all customers";
        html += `<div class="offer-row"><div class="name">${esc(o.label)}<div class="rule">Eligible: ${esc(rule)}</div></div>${numberField("cost_" + o.offer_id, "Cost (USD)", 1)}${slider("rate_" + o.offer_id, "Save rate")}</div>`;
      }
    }
    if (!c.population.length) { $("main").innerHTML = html + `<div class="box info">No customers in the selected tenure segments.</div>`; bindControls($("main")); return; }
    const s = c.target.stats;
    html += strip(c);
    if (!s.selected_count) html += `<div class="box info">Nobody is selected: no customer has positive expected value under these assumptions, or the budget is below one offer. Not running the campaign is the right decision here.</div>`;
    const options = E.offerOptions(E.valueCustomers(c.population, c.cfg), c.offers);
    const be = E.breakEven(c.target.table, c.cfg, options);
    if (!c.mc) c.mc = s.selected_count ? E.repriceFrozen(c.target.table, c.cfg, E.drawAssumptions(c.cfg, LIVE_DRAWS, c.cfg.seed)) : new Float64Array(LIVE_DRAWS);
    const loss = c.mc.filter((x) => x < 0).length / c.mc.length;
    html += `<div class="row c4">${metric("Expected net value", usd(s.expected_net_value), `${num(s.selected_count)} customers contacted`)}
      ${metric("Break-even save rate (this list)", pct(be.break_even_mix_save_rate), "", "", `Average save rate of this list's offers (what a pilot measures) at which its expected net value is zero; the standard offer alone would need ${pct(be.break_even_default_save_rate)}. Assumed: ${pct(be.mix_save_rate)}.`)}
      ${metric("Chance this list loses money", pct(loss, 0), "", "", `${num(LIVE_DRAWS)} draws: every register assumption drawn at once from a triangular distribution over its tested range, centred on the values set above.`)}
      ${metric("Minimum viable save rate", pct(be.minimum_viable_save_rate), "", "", "Standard-offer save rate (other offers scaled in proportion) below which no customer has positive expected value: the best decision is no campaign.")}</div>
      <div class="caption">Hover a card for its definition. The chance of a loss uses the browser's random draws, so it can differ from the Streamlit dashboard by about a percentage point.</div>
      ${s.selected_count ? chart("mc", 320) : ""}
      <h3>Scenarios and budget size</h3><div class="caption">A frozen list keeps today's customers and offers when an assumption changes; a re-optimised list picks again within the same budget. These are scenarios, not confidence intervals.</div>
      <button class="primary" id="runScenarios">Run scenario analysis</button><span id="scenarioStatus" class="caption"></span><div id="scenarioBody"></div>
      <h3>Outside the sample: lower churn and Vietnamese prices</h3>
      ${table(ev.stress, [{ key: "economy", label: "Prices" }, { key: "mean_probability", label: "Average churn", num: true, fmt: (v) => pct(v, 0) }, { key: "positive_ev_customers", label: "Customers worth an offer", num: true, fmt: (v) => num(v) },
        { key: "positive_ev_share", label: "Share", num: true, fmt: (v) => pct(v, 0) }, { key: "net_no_budget_limit", label: "Expected net (USD)", num: true, fmt: (v) => usd(v) }, { key: "pilot_per_arm", label: "Pilot customers per arm", num: true, fmt: (v) => (missing(v) ? "n/a" : num(v)) }])}
      <div class="caption">From the pipeline, at the registered assumptions: probabilities shifted to lower average churn with the ranking unchanged; 'Vietnam-like' scales bills and offers to a home-fibre bill and contacts by SMS. See the analysis report.</div>`;
    $("main").innerHTML = html;
    bindControls($("main"));
    if (s.selected_count) {
      plot("mc", [{ type: "histogram", x: Array.from(c.mc), nbinsx: 60, marker: { color: BLUE }, name: "draws" }], { title: { text: "Net value of this list when every assumption is uncertain" },
        xaxis: { title: "Expected net value of the frozen list (USD)" }, yaxis: { title: "Draws" }, bargap: 0.05, showlegend: false,
        shapes: [{ type: "line", x0: 0, x1: 0, yref: "paper", y0: 0, y1: 1, line: { color: RED, width: 1 } }], annotations: [{ x: 0, yref: "paper", y: 1, text: "loss", showarrow: false, xanchor: "right" }] });
    }
    $("runScenarios").addEventListener("click", () => {
      const button = $("runScenarios");
      button.disabled = true; $("scenarioStatus").textContent = " Computing tornado, scenarios, profit curve and grid...";
      setTimeout(() => {
        const start = performance.now();
        S.scenario = { key: c.key, mode: C.mode, budget: c.budget, tornado: E.tornado(c.population, c.budget, c.cfg, C.mode, DATA.thresholds),
          scenarios: E.scenarioTable(c.population, c.budget, c.cfg, C.mode, DATA.thresholds), sensitivity: E.sensitivity(c.population, c.budget, c.cfg, C.mode, DATA.thresholds),
          curve: E.profitCurve(c.population, c.cfg, [C.mode, "risk"], DATA.thresholds), cfg: c.cfg, n: c.population.length, seconds: (performance.now() - start) / 1000 };
        render();
      }, 30);
    });
    if (S.scenario) drawScenarios(c);
    else $("scenarioStatus").textContent = " Press the button to compute the analysis for the current list and assumptions.";
  }

  function drawScenarios(c) {
    const r = S.scenario;
    let html = r.key !== c.key ? `<div class="box warn">Assumptions changed since this analysis. Run it again to refresh the charts.</div>` : "";
    html += `<div class="caption">Computed in ${r.seconds.toFixed(1)}s.</div>${chart("tornado", 420)}`;
    html += table(r.scenarios.map((x) => ({ scenario: x.scenario[0].toUpperCase() + x.scenario.slice(1), customers: num(x.selected_count), net: usd(x.expected_net_value), roi: pct(x.roi, 0), frozen: usd(x.fixed_expected_net_value) })),
      [{ key: "scenario", label: "Scenario" }, { key: "customers", label: "Customers (re-optimised)", num: true }, { key: "net", label: "Net value, re-optimised", num: true }, { key: "roi", label: "ROI", num: true }, { key: "frozen", label: "Net value, frozen list", num: true }]);
    html += `<div class="caption">Pessimistic and optimistic combine several register assumptions at once; see the assumption register for the ranges and sources.</div>${chart("curve", 420)}${chart("marginal", 300)}
      <div class="radio">Grid view: <label><input type="radio" name="grid" value="retarget" ${S.gridView === "retarget" ? "checked" : ""}> Re-optimised list</label><label><input type="radio" name="grid" value="fixed" ${S.gridView === "fixed" ? "checked" : ""}> Frozen list</label></div>
      ${chart("grid", 420)}<button class="secondary" id="downloadSensitivity">Download the full sensitivity table</button>`;
    $("scenarioBody").innerHTML = html;
    const tor = [...r.tornado].reverse(), base = tor.length ? tor[0].base_net : 0;
    const bar = (end, name, color) => ({ type: "bar", orientation: "h", y: tor.map((x) => x.label), x: tor.map((x) => x[`net_${end}_retarget`] - base), base, name, marker: { color },
      customdata: tor.map((x) => x[end]), hovertemplate: `%{y}<br>${end} %{customdata}: $%{x:,.0f} vs base<extra></extra>` });
    plot("tornado", [bar("low", "Low end of range", ORANGE), bar("high", "High end of range", BLUE)], { barmode: "overlay", title: { text: `Tornado: one assumption at a time (base ${usd(base)})` },
      xaxis: { title: "Expected net value, list re-optimised (USD)" }, shapes: [{ type: "line", x0: base, x1: base, yref: "paper", y0: 0, y1: 1, line: { color: INK, width: 1 } }] });
    const colors = { ev: BLUE, risk: ORANGE, segment_offers: AQUA };
    const std = E.defaultOffer(r.cfg), currentShare = r.budget / Math.max(r.n * (std.offer_cost + std.contact_cost), 1e-9);
    plot("curve", [...new Set(r.curve.map((x) => x.strategy))].map((strategy) => { const part = r.curve.filter((x) => x.strategy === strategy);
      return { type: "scatter", mode: "lines+markers", name: E.STRATEGY_LABELS[strategy], x: part.map((x) => x.budget_share), y: part.map((x) => x.expected_net_value), line: { color: colors[strategy] } }; }),
      { title: { text: "Profit curve: expected net value by budget size" }, xaxis: { title: "Budget, as the share of customers the standard offer could reach", tickformat: ".0%" }, yaxis: { title: "Expected net value (USD)" },
        shapes: [{ type: "line", x0: currentShare, x1: currentShare, yref: "paper", y0: 0, y1: 1, line: { dash: "dash", color: MUTED } },
          { type: "line", x0: DATA.budget_recommendation.recommended_share, x1: DATA.budget_recommendation.recommended_share, yref: "paper", y0: 0, y1: 1, line: { dash: "dot", color: INK } }],
        annotations: [{ x: currentShare, yref: "paper", y: 1, text: "current budget", showarrow: false, xanchor: "left" }, { x: DATA.budget_recommendation.recommended_share, yref: "paper", y: 0, text: "recommended", showarrow: false, xanchor: "left", yanchor: "bottom" }] });
    const part = r.curve.filter((x) => x.strategy === r.mode), hurdle = cfg0.campaign.recommendation.min_marginal_roi;
    plot("marginal", [{ type: "bar", x: part.map((x) => x.budget_share), y: part.map((x) => x.marginal_roi), marker: { color: BLUE }, name: "Marginal ROI" }],
      { title: { text: "Return on each extra budget step (stop when it falls below the hurdle)" }, xaxis: { title: "Budget share", tickformat: ".0%" }, yaxis: { title: "Marginal ROI", tickformat: ".0%" }, showlegend: false,
        shapes: [{ type: "line", y0: hurdle, y1: hurdle, xref: "paper", x0: 0, x1: 1, line: { color: ORANGE } }], annotations: [{ xref: "paper", x: 1, y: hurdle, text: "hurdle", showarrow: false, xanchor: "right", yanchor: "bottom" }] });
    const drawGrid = () => {
      const cells = r.sensitivity.filter((x) => x.axis === "save_rate x offer_cost" && x.mode === S.gridView);
      const rates = [...new Set(cells.map((x) => x.parameter))].sort((a, b) => a - b), mults = [...new Set(cells.map((x) => x.cost_multiplier))].sort((a, b) => a - b);
      const z = rates.map((q) => mults.map((m) => cells.find((x) => x.parameter === q && x.cost_multiplier === m).expected_net_value));
      const limit = Math.max(1, ...z.flat().map(Math.abs));
      plot("grid", [{ type: "heatmap", x: mults.map((m) => m + "x"), y: rates.map((q) => pct(q, 0)), z, zmin: -limit, zmax: limit, colorscale: [[0, RED], [0.5, "#f0efec"], [1, BLUE]],
        text: z.map((row) => row.map((v) => v.toFixed(0))), texttemplate: "%{text}", colorbar: { title: "USD" }, hovertemplate: "save rate %{y}, cost %{x}: $%{z:,.0f}<extra></extra>" }],
        { title: { text: "Expected net value: save rate x offer cost multiplier (USD)" }, xaxis: { title: "Offer cost multiplier", type: "category" }, yaxis: { title: "Save rate", type: "category" } });
    };
    drawGrid();
    $("scenarioBody").querySelectorAll("input[name=grid]").forEach((el) => el.addEventListener("change", () => { S.gridView = el.value; drawGrid(); }));
    $("downloadSensitivity").addEventListener("click", () => download("sensitivity.csv", csv(r.sensitivity)));
  }

  // ---- Model evidence ----------------------------------------------------------------------------------------------
  function evidencePage() {
    const tabs = ["Performance", "Drivers and scorecard", "Errors and money check", "Data and new customers"];
    $("main").innerHTML = `<div class="hero"><h2>Can we trust the scores?</h2><p>How well the deployed model ranks and calibrates, what drives it, and where the data come from.</p></div>
      <div class="tabs">${tabs.map((t) => `<button data-tab="${t}" class="${S.tab === t ? "active" : ""}">${t}</button>`).join("")}</div><div id="tab"></div>`;
    $("main").querySelectorAll("[data-tab]").forEach((b) => b.addEventListener("click", () => { S.tab = b.dataset.tab; evidencePage(); }));
    ({ Performance: performanceTab, "Drivers and scorecard": driversTab, "Errors and money check": errorsTab, "Data and new customers": dataTab })[S.tab]();
  }

  function performanceTab() {
    const chosen = DATA.selected_model + "_calibrated", row = ev.test_metrics.find((m) => m.model === chosen) || {};
    const ci = Object.fromEntries(ev.intervals.map((x) => [x.metric, x]));
    const cards = [["roc_auc", "ROC-AUC"], ["average_precision", "PR-AUC (average precision)"], ["brier", "Brier score"], ["ece", "Expected calibration error"], ["calibration_slope", "Calibration slope"]]
      .map(([k, label]) => metric(label, num(row[k], 3), ci[k] ? `95% interval ${num(ci[k].lower_95, 3)}-${num(ci[k].upper_95, 3)}` : "")).join("");
    $("tab").innerHTML = `<h3>Deployed model: ${esc(DATA.model_name)}</h3><div class="caption">Chosen on the validation split by a rule fixed in advance (best average precision within 0.01, Brier within 0.002, prefer the simpler model). Metrics are on the untouched test split.</div>
      <div class="row c5">${cards}</div><div class="row c2">${chart("calibration", 420)}${chart("gains", 420)}</div>
      ${table(ev.test_metrics, [{ key: "model", label: "Candidate (test split)" }, { key: "average_precision", label: "PR-AUC", num: true, fmt: (v) => num(v, 3) }, { key: "roc_auc", label: "ROC-AUC", num: true, fmt: (v) => num(v, 3) },
        { key: "brier", label: "Brier", num: true, fmt: (v) => num(v, 3) }, { key: "ece", label: "ECE", num: true, fmt: (v) => num(v, 3) }, { key: "calibration_slope", label: "Calibration slope", num: true, fmt: (v) => num(v, 3) }])}`;
    const names = { [chosen]: `Deployed (${DATA.model_name})`, xgboost_calibrated: "Challenger (calibrated XGBoost)" };
    const traces = Object.entries(names).map(([m, name], i) => { const pts = ev.calibration.filter((x) => x.model === m);
      return { type: "scatter", mode: "lines+markers", name, x: pts.map((x) => x.predicted), y: pts.map((x) => x.observed), line: { color: [BLUE, ORANGE][i] } }; });
    traces.push({ type: "scatter", mode: "lines", name: "Perfect calibration", x: [0, 1], y: [0, 1], line: { color: GREY, width: 1 } });
    plot("calibration", traces, { title: { text: "Calibration on the test split" }, xaxis: { title: "Predicted churn probability" }, yaxis: { title: "Observed churn rate" } });
    plot("gains", [{ type: "scatter", mode: "lines", name: "Random contact", x: [0, 1], y: [0, 1], line: { color: GREY, width: 1 } },
      { type: "scatter", mode: "lines+markers", name: "By predicted risk", x: [0, ...ev.gains.map((g) => g.cumulative_customer_share)], y: [0, ...ev.gains.map((g) => g.cumulative_churner_capture)], line: { color: BLUE } }],
      { title: { text: `Cumulative gains (riskiest tenth: ${num(ev.gains[0].lift, 1)}x the average churn rate)` }, xaxis: { title: "Share of customers contacted", tickformat: ".0%" }, yaxis: { title: "Share of churners reached", tickformat: ".0%" } });
  }

  function driversTab() {
    const meta = ev.scorecard_meta;
    let html = "";
    if (ev.odds_ratios.length) {
      html += `${chart("odds", 440)}<div class="caption">Categories are compared with their lowest-churn level, flags with not having the service, tenure per 12 months and charges per $10 a month.</div>
        <h3>Points scorecard for the call centre</h3><p>Start at <b>${meta.base_points} points</b> and add the points of each attribute. ${meta.anchor_score} points = 50% churn probability; every ${meta.pdo} points doubles the odds.
        On test the card stays within ${num(meta.mean_abs_probability_gap * 100, 1)} percentage points of the model on average.</p>
        <div class="row split"><div class="scroll">${table(ev.scorecard_points, [{ key: "characteristic", label: "Characteristic" }, { key: "attribute", label: "Attribute" }, { key: "points", label: "Points", num: true }])}</div>
        <div>${table(ev.scorecard_bands, [{ key: "band", label: "Points" }, { key: "customers", label: "Customers", num: true }, { key: "card_probability", label: "Card probability", num: true, fmt: (v) => pct(v) }, { key: "observed_churn", label: "Observed churn", num: true, fmt: (v) => pct(v) }])}</div></div>`;
    }
    const local = [...ev.shap_local].sort((a, b) => b.raw_probability - a.raw_probability);
    if (!S.shapCustomer) S.shapCustomer = local[0].customer_id;
    html += `<h3>Challenger: XGBoost (not deployed) - SHAP attribution</h3><div class="caption">TreeSHAP on 200 validation customers, log-odds scale. It explains the raw XGBoost challenger, not the deployed model, and it is not causal.</div>
      ${chart("shap", 420)}<div class="field"><label for="shapCustomer">Explain one validation customer (challenger model)</label><select id="shapCustomer">${local.map((r) => `<option ${r.customer_id === S.shapCustomer ? "selected" : ""}>${esc(r.customer_id)}</option>`).join("")}</select></div>${chart("shapLocal", 420)}`;
    $("tab").innerHTML = html;
    if (ev.odds_ratios.length) {
      const sorted = [...ev.odds_ratios].sort((a, b) => b.odds_ratio - a.odds_ratio);
      const picks = [...new Map([...sorted.slice(0, 7), ...sorted.slice(-5)].map((r) => [r.variable + ": " + r.comparison, r])).values()].sort((a, b) => a.odds_ratio - b.odds_ratio);
      const group = (up) => { const rs = picks.filter((r) => (r.odds_ratio > 1) === up);
        return { type: "scatter", mode: "markers", name: up ? "Higher churn odds" : "Lower churn odds", x: rs.map((r) => r.odds_ratio), y: rs.map((r) => r.variable + ": " + r.comparison), marker: { size: 11, color: up ? ORANGE : BLUE } }; };
      plot("odds", [group(true), group(false)], { title: { text: "What moves the deployed model's churn odds (associations, not causes)" }, xaxis: { title: "Odds ratio (log scale)", type: "log" },
        yaxis: { categoryorder: "array", categoryarray: picks.map((r) => r.variable + ": " + r.comparison) },
        shapes: [{ type: "line", x0: 1, x1: 1, yref: "paper", y0: 0, y1: 1, line: { color: MUTED, width: 1 } }] });
    }
    const shap = [...ev.shap_global].sort((a, b) => a.mean_abs_shap - b.mean_abs_shap);
    plot("shap", [{ type: "bar", orientation: "h", x: shap.map((r) => r.mean_abs_shap), y: shap.map((r) => r.feature), marker: { color: GREY } }],
      { title: { text: "Average size of each feature's contribution" }, xaxis: { title: "Mean |SHAP| (log-odds)" }, showlegend: false });
    const drawLocal = () => {
      const row = local.find((r) => r.customer_id === S.shapCustomer);
      const contributions = Object.entries(row).filter(([k]) => !["customer_id", "base_value", "raw_probability"].includes(k)).map(([k, v]) => [k, Number(v)])
        .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 10).reverse();
      const group = (up) => { const rs = contributions.filter(([, v]) => (v > 0) === up);
        return { type: "bar", orientation: "h", name: up ? "Raises churn risk" : "Lowers churn risk", x: rs.map(([, v]) => v), y: rs.map(([k]) => k), marker: { color: up ? ORANGE : BLUE } }; };
      plot("shapLocal", [group(true), group(false)], { title: { text: `${row.customer_id}: challenger probability ${pct(row.raw_probability)}` }, xaxis: { title: "Contribution (log-odds)" },
        yaxis: { categoryorder: "array", categoryarray: contributions.map(([k]) => k) }, barmode: "relative" });
    };
    drawLocal();
    $("shapCustomer").addEventListener("change", (e) => { S.shapCustomer = e.target.value; drawLocal(); });
  }

  function errorsTab() {
    $("tab").innerHTML = `<h3>Model choice checked in money</h3>${table(ev.profit_check, [{ key: "population", label: "Population" }, { key: "model", label: "Candidate (calibrated)" }, { key: "selected_count", label: "Contacted", num: true },
        { key: "expected_net_value", label: "Expected net", num: true, fmt: (v) => usd(v) }, { key: "label_based_net", label: "Net with actual churn", num: true, fmt: (v) => usd(v) }, { key: "precision_contacted", label: "Precision", num: true, fmt: (v) => pct(v) }])}
      <div class="caption">Each candidate picks customers for the same budget and standard offer. The choice was made on validation; test is reported only.</div>
      <h3>Who the model gets wrong</h3>${table(ev.error_profiles, [{ key: "outcome", label: "Outcome (test, model threshold)" }, { key: "customers", label: "Customers", num: true }, { key: "mean_probability", label: "Mean probability", num: true, fmt: (v) => pct(v) },
        { key: "mean_tenure", label: "Mean tenure (months)", num: true, fmt: (v) => num(v, 1) }, { key: "median_monthly_charges", label: "Median bill", num: true, fmt: (v) => usd(v, 2) },
        { key: "month_to_month_share", label: "Month-to-month", num: true, fmt: (v) => pct(v) }, { key: "fibre_share", label: "Fibre", num: true, fmt: (v) => pct(v) }])}
      <h3>Performance by segment</h3>${table(ev.segment_errors, [{ key: "attribute", label: "Segment" }, { key: "group", label: "Group" }, { key: "n", label: "Customers", num: true },
        { key: "average_precision", label: "PR-AUC", num: true, fmt: (v) => num(v, 3) }, { key: "roc_auc", label: "ROC-AUC", num: true, fmt: (v) => num(v, 3) }, { key: "ece", label: "ECE", num: true, fmt: (v) => num(v, 3) },
        { key: "calibration_slope", label: "Calibration slope", num: true, fmt: (v) => num(v, 3) }])}`;
  }

  function dataTab() {
    const src = ev.source, q = ev.quality, reasons = ev.reasons;
    let html = `<h3>Data source and quality</h3><p>IBM Telco Customer Churn sample, downloaded from <a href="${esc(src.dataset_page)}" target="_blank" rel="noopener">${esc(src.source)}</a> on ${esc(String(src.downloaded_at_utc).slice(0, 10))};
      ${num(src.rows)} customers. ${q.total_charges_filled_zero} blank TotalCharges for new customers (tenure 0) set to 0; ${q.duplicates_removed} duplicate rows. Split 60/20/20 train/validation/test, stratified, seed ${cfg0.seed}. Join: ${esc(q.joins)}.</p>
      ${chart("reasons", 380)}<div class="caption">Reasons come from IBM's extended sample of the same customers and are recorded after customers left, so they are descriptive, never model inputs.</div>
      <h3>Score new customers</h3>`;
    if (DATA.model.linear) {
      html += `<p>Upload a CSV with the same columns as the template to score it with the trained model (the deployed calibrated logistic regression, embedded in this file). Up to 10 MB / 50,000 rows, UTF-8, comma-separated. Nothing leaves this browser.</p>
        <button class="secondary" id="template">Download the unlabelled CSV template</button><div class="field" style="margin-top:8px"><input type="file" id="upload" accept=".csv,text/csv"></div><div id="uploadResult"></div>`;
    } else html += `<div class="box info">The deployed model is not a logistic regression, so it cannot be embedded; use the Streamlit dashboard to score new customers.</div>`;
    $("tab").innerHTML = html;
    const cats = Object.keys(reasons.category_share);
    plot("reasons", [{ type: "bar", orientation: "h", name: "All churners", y: cats, x: cats.map((k) => reasons.category_share[k]), marker: { color: GREY } },
      { type: "bar", orientation: "h", name: "Churners on the recommended list", y: cats, x: cats.map((k) => (reasons.category_share_on_list || {})[k] || 0), marker: { color: BLUE } }],
      { barmode: "group", title: { text: `Why churners left: only ${pct(reasons.addressable_share, 0)} for price or a competitor's offer` }, xaxis: { title: "Share of churners", tickformat: ".0%" }, yaxis: { categoryorder: "total ascending" } });
    if (!DATA.model.linear) return;
    $("template").addEventListener("click", () => download("customers_template.csv", DATA.template_csv));
    $("upload").addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (!file) return;
      if (file.size > 10 * 1024 * 1024) { S.upload = { errors: [[0, "file", "Limit is 10 MB"]] }; drawUpload(); return; }
      file.text().then((text) => {
        const checked = E.validateUpload(text, DATA.model);
        if (checked.errors.length) S.upload = { errors: checked.errors };
        else {
          const scored = E.score(checked.records, DATA.model);
          S.upload = { scored, ignored: checked.ignored };
          S.uploaded = scored; C.budget_upload = null; cache = null;
        }
        drawUpload(); sidebar();
      });
    });
    drawUpload();
  }

  function drawUpload() {
    const box = $("uploadResult");
    if (!box || !S.upload) return;
    if (S.upload.errors) {
      box.innerHTML = `<div class="box warn">The CSV is not valid; nothing was imported. The previous customer list is unchanged.</div><div class="scroll errors">${table(S.upload.errors.slice(0, 500).map(([row, column, message]) => ({ row, column, message })),
        [{ key: "row", label: "Row", num: true }, { key: "column", label: "Column" }, { key: "message", label: "Problem" }])}</div>`;
      return;
    }
    const scored = S.upload.scored;
    box.innerHTML = `<div class="box ok">Scored ${num(scored.length)} customers. Choose 'Uploaded CSV' in the sidebar to build a campaign for them.</div>
      ${S.upload.ignored.length ? `<div class="box info">Ignored columns: ${esc(S.upload.ignored.join(", "))}</div>` : ""}
      ${scored.some((r) => r.prediction_origin.includes("matches_")) ? `<div class="box warn">Some IDs match the project's own data. Check 'Origin': IDs seen in training are not an independent evaluation, and an ID match does not verify content or timing.</div>` : ""}
      <div class="scroll">${table(scored, [{ key: "customer_id", label: "Customer" }, { key: "churn_probability", label: "Churn probability", num: true, fmt: (v) => num(v, 3) }, { key: "risk_band", label: "Risk band" }, { key: "prediction_origin", label: "Origin" }])}</div>
      <button class="secondary" id="downloadScores">Download scores</button>`;
    $("downloadScores").addEventListener("click", () => download("scores.csv", csv(scored, [...Object.keys(scored[0]).filter((k) => k !== "customer_id"), "customer_id"])));
  }

  // ---- render ------------------------------------------------------------------------------------------------------
  function render() {
    sidebar();
    try {
      if (S.page === "Model evidence") return evidencePage();
      const c = current();
      if (S.page === "Decision") decisionPage(c); else assumptionsPage(c);
    } catch (err) {
      $("main").innerHTML = `<div class="box warn">Something went wrong: ${esc(err.message)}</div>`;
      console.error(err);
    }
  }
  window.RetentionLab = { state: S, controls: C, render, current };
  render();
})();
