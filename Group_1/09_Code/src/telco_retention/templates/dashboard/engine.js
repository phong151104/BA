// Decision engine of the HTML dashboard: a line-by-line port of business.py and analysis.py (value proxy, offer options,
// budget optimiser, targeting rules, break-even, frozen repricing, tornado, scenarios, sensitivity grid, profit curve)
// and of the deployed model's scoring. tests/test_html_dashboard.py checks it against the Python results.
"use strict";
const Engine = (function () {
  const SEGMENTS = ["new", "developing", "loyal"];
  const QUADRANTS = ["High risk / High value", "High risk / Low value", "Low risk / High value", "Low risk / Low value"];
  const STRATEGY_LABELS = {
    none: "No campaign", random: "Random contact", risk: "Highest churn risk", risk_positive_ev: "Highest risk, positive EV only",
    value: "Highest customer value", ev: "Expected value (single offer)", segment_offers: "Expected value + segment offers",
  };
  const COMPARED = ["none", "risk", "risk_positive_ev", "value", "ev", "segment_offers"];
  const MAX_DP_CELLS = 40e6; // budget units x customers; above it costs are rounded up to a coarser unit

  const clone = (x) => JSON.parse(JSON.stringify(x));
  const byKey = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

  function rows(columns) {
    const names = Object.keys(columns), n = columns[names[0]].length, out = new Array(n);
    for (let i = 0; i < n; i++) { const r = {}; for (const k of names) r[k] = columns[k][i]; out[i] = r; }
    return out;
  }

  function tenureSegment(t) { return t <= 12 ? "new" : t <= 24 ? "developing" : "loyal"; }

  function defaultOffer(cfg) {
    const offer = cfg.offers.find((o) => o.offer_id === cfg.campaign.default_offer);
    if (!offer) throw new Error("Unknown default offer");
    return offer;
  }

  function annuityMonths(months, rate) {
    const monthly = Math.pow(1 + rate, 1 / 12) - 1;
    return monthly <= 0 ? months : (1 - Math.pow(1 + monthly, -months)) / monthly;
  }

  function valueCustomers(customers, cfg) {
    const v = cfg.value;
    return customers.map((c) => {
      const segment = tenureSegment(c.tenure);
      const remaining = Math.min(v.horizon_cap_months, v.base_horizon_months * v.tenure_factors[segment]);
      const discounted = annuityMonths(remaining, v.discount_rate_annual);
      return { ...c, tenure_segment: segment, remaining_months: remaining, discounted_months: discounted, customer_value: c.MonthlyCharges * v.margin * discounted };
    });
  }

  function eligible(c, rules) {
    for (const [column, allowed] of Object.entries(rules || {})) {
      if (!(column in c)) throw new Error("Eligibility column missing from customer data: " + column);
      if (!allowed.map(String).includes(String(c[column]))) return false;
    }
    return true;
  }

  // One row per eligible customer and offer, offer by offer (the order pandas concatenates them in).
  function offerOptions(customers, offers) {
    const out = [];
    offers.forEach((offer) => {
      const q = offer.save_rate, total = offer.offer_cost + offer.contact_cost;
      customers.forEach((c, i) => {
        if (!eligible(c, offer.eligibility)) return;
        const pv = c.churn_probability * c.customer_value, qv = q * c.customer_value;
        const esp = c.churn_probability * q, erv = esp * c.customer_value;
        out.push({ c, ci: i, customer_id: c.customer_id, offer_id: offer.offer_id, assumed_save_rate: q, offer_cost: offer.offer_cost,
          contact_cost: offer.contact_cost, total_cost: total, expected_saved_probability: esp, expected_retained_value: erv,
          expected_net_value: erv - total, break_even_save_rate: pv > 0 ? total / pv : NaN, break_even_probability: qv > 0 ? total / qv : NaN });
      });
    });
    return out;
  }

  function contactLimit(n, share) { return share == null ? null : Math.ceil(share * n - 1e-9); }

  // Python's _greedy: priority descending, then customer and offer ID; skip what no longer fits.
  function greedy(pool, budget, key, maxContacts) {
    const sorted = pool.map((o, idx) => ({ o, idx, p: key === "ratio" ? (o.total_cost > 0 ? o.expected_net_value / o.total_cost : Infinity) : (key === "expected_net_value" ? o.expected_net_value : o.c[key]) }))
      .sort((a, b) => (b.p - a.p) || byKey(a.o.customer_id, b.o.customer_id) || byKey(a.o.offer_id, b.o.offer_id));
    const limit = maxContacts == null ? sorted.length : maxContacts;
    const chosen = [], used = new Set();
    let spent = 0;
    for (const { o } of sorted) {
      if (chosen.length >= limit) break;
      if (!used.has(o.ci) && spent + o.total_cost <= budget + 1e-8) { chosen.push(o); used.add(o.ci); spent += o.total_cost; }
    }
    return chosen;
  }

  const gcd = (a, b) => { while (b) [a, b] = [b, a % b]; return a; };

  // Multiple-choice knapsack by dynamic programming over the budget in whole cost units: at most one option per
  // customer, maximum total EV within the budget. Exact whenever the costs share a unit (whole dollars by default).
  function knapsack(pool, budget, penalty) {
    const cents = pool.map((o) => Math.round(o.total_cost * 100));
    const budgetCents = Math.floor(budget * 100 + 1e-6);
    let unit = cents.reduce((g, c) => (c > 0 ? gcd(g, c) : g), 0) || 1;
    const groups = new Map();
    pool.forEach((o, k) => { if (o.expected_net_value - penalty > 0) { if (!groups.has(o.ci)) groups.set(o.ci, []); groups.get(o.ci).push(k); } });
    const list = [...groups.values()];
    let exact = true, capacity = Math.floor(budgetCents / unit);
    const heaviest = list.reduce((s, g) => s + Math.max(...g.map((k) => cents[k])), 0);
    capacity = Math.min(capacity, Math.ceil(heaviest / unit));
    if (list.length * (capacity + 1) > MAX_DP_CELLS) {
      unit = Math.ceil(Math.min(budgetCents, heaviest) / Math.floor(MAX_DP_CELLS / Math.max(list.length, 1))) || 1;
      capacity = Math.floor(Math.min(budgetCents, heaviest) / unit);
      exact = false;
    }
    const weight = cents.map((c) => (exact ? c / unit : Math.ceil(c / unit)));
    const C = capacity + 1;
    let best = new Float64Array(C);
    const choice = new Uint8Array(list.length * C);
    list.forEach((group, g) => {
      const next = Float64Array.from(best);
      group.forEach((k, j) => {
        const w = weight[k], v = pool[k].expected_net_value - penalty;
        for (let c = w; c < C; c++) {
          const cand = best[c - w] + v;
          if (cand > next[c] + 1e-12) { next[c] = cand; choice[g * C + c] = j + 1; }
        }
      });
      best = next;
    });
    const picked = [];
    let c = capacity;
    for (let g = list.length - 1; g >= 0; g--) {
      const j = choice[g * C + c];
      if (j) { const k = list[g][j - 1]; picked.push(pool[k]); c -= weight[k]; }
    }
    return { picked, exact };
  }

  function selectOptions(options, budget, strategy, maxContacts) {
    if (!isFinite(budget) || budget < 0) throw new Error("Budget must be finite and non-negative");
    if (!options.length || strategy === "none" || maxContacts === 0) return { picked: [], status: "empty" };
    const pool = strategy === "ev" || strategy === "risk_positive_ev" ? options.filter((o) => o.expected_net_value > 0) : options;
    if (!pool.length) return { picked: [], status: "no_positive_ev" };
    if (strategy !== "ev") {
      const key = { risk: "churn_probability", risk_positive_ev: "churn_probability", value: "customer_value" }[strategy];
      if (!key) throw new Error("Unsupported rule: " + strategy);
      return { picked: greedy(pool, budget, key, maxContacts), status: "baseline" };
    }
    const unique = new Set(pool.map((o) => o.ci)).size === pool.length;
    if (unique && new Set(pool.map((o) => o.total_cost)).size === 1) {
      return { picked: greedy(pool, budget, "expected_net_value", maxContacts), status: "optimal_sort" };
    }
    let { picked, exact } = knapsack(pool, budget, 0);
    if (maxContacts != null && picked.length > maxContacts) {
      // Contact cap binding: price each contact (Lagrange multiplier) until the list fits the cap.
      let lo = 0, hi = Math.max(...pool.map((o) => o.expected_net_value)), fit = null;
      for (let i = 0; i < 40; i++) {
        const mid = (lo + hi) / 2, trial = knapsack(pool, budget, mid);
        if (trial.picked.length <= maxContacts) { hi = mid; fit = trial; } else lo = mid;
      }
      return { picked: fit ? fit.picked : [], status: "near_optimal_contact_cap" };
    }
    return { picked, status: exact ? "optimal" : "near_optimal_rounded_costs" };
  }

  const pct = (x, d) => (x * 100).toFixed(d) + "%";
  const num2 = (x) => x.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ","); // Python's {:,.2f}

  function explain(r, strategy, budget, currency) {
    let reason;
    if (r.selected) reason = "Selected by rule: " + (STRATEGY_LABELS[strategy] || strategy);
    else if (strategy === "none") reason = "No campaign is run";
    else if (r.expected_net_value <= 0) reason = "Expected value is not positive";
    else if (r.total_cost > budget) reason = "Budget is below the offer cost";
    else reason = "Positive EV but outranked within the budget";
    const detail = `p=${pct(r.churn_probability, 1)} x save rate ${pct(r.assumed_save_rate, 0)} x value ${num2(r.customer_value)} - cost ${num2(r.total_cost)} = EV ${num2(r.expected_net_value)} ${currency}; `
      + (isFinite(r.break_even_save_rate) ? `break-even save rate ${pct(r.break_even_save_rate, 1)}` : "no finite break-even save rate")
      + (r.selected && r.expected_net_value <= 0 ? "; a baseline rule selected it despite non-positive EV" : "");
    return { reason, detail };
  }

  function summarize(table, budget, thresholds) {
    const picked = table.filter((r) => r.selected);
    const sum = (f) => picked.reduce((s, r) => s + f(r), 0);
    const spent = sum((r) => r.total_cost), net = sum((r) => r.expected_net_value);
    const out = {
      selected_count: picked.length, cost: spent, remaining_budget: budget - spent, expected_saved: sum((r) => r.expected_saved_probability),
      expected_retained_value: sum((r) => r.expected_retained_value), expected_net_value: net, roi: spent > 0 ? net / spent : null,
      expected_precision: picked.length ? sum((r) => r.churn_probability) / picked.length : null,
      precision_contacted: table.length && table[0].churn != null && picked.length ? sum((r) => r.churn) / picked.length : null,
    };
    if (thresholds) {
      const high = table.filter((r) => r.churn_probability >= thresholds.risk && r.customer_value >= thresholds.value);
      out.high_risk_high_value_count = high.length;
      out.high_risk_high_value_coverage = high.length ? high.filter((r) => r.selected).length / high.length : null;
    }
    return out;
  }

  // One row per customer: the chosen offer, otherwise the best potential offer (python: campaign()).
  // `details: false` skips the per-customer explanations, which the scenario analysis never shows.
  function campaign(customers, budget, cfg, offers, strategy, thresholds, details = true) {
    offers = offers || [defaultOffer(cfg)];
    const valued = valueCustomers(customers, cfg);
    const options = offerOptions(valued, offers);
    const maxContacts = contactLimit(valued.length, cfg.campaign.max_contact_share);
    const { picked, status } = selectOptions(options, budget, strategy, maxContacts);
    const chosen = new Set(picked);
    const best = new Map();
    for (const o of options) {
      const selected = chosen.has(o), cur = best.get(o.ci);
      if (!cur || (selected && !cur.selected) || (selected === cur.selected && (o.expected_net_value > cur.o.expected_net_value
        || (o.expected_net_value === cur.o.expected_net_value && o.offer_id < cur.o.offer_id)))) best.set(o.ci, { o, selected });
    }
    const table = [...best.values()].map(({ o, selected }) => { const row = Object.assign({}, o.c, o, { selected }); delete row.c; return row; })
      .sort((a, b) => byKey(a.customer_id, b.customer_id));
    if (details) {
      const rule = strategy === "ev" && offers.length > 1 ? "segment_offers" : strategy;
      for (const r of table) { const { reason, detail } = explain(r, rule, budget, cfg.currency || "USD"); r.selection_reason = reason; r.decision_detail = detail; }
    }
    return { table, stats: { ...summarize(table, budget, thresholds), solver: status, max_contacts: maxContacts } };
  }

  function strategyOffers(cfg, strategy) { return strategy === "segment_offers" ? clone(cfg.offers) : [clone(defaultOffer(cfg))]; }
  function runStrategy(customers, budget, cfg, strategy, thresholds, details = false) {
    return campaign(customers, budget, cfg, strategyOffers(cfg, strategy), strategy === "segment_offers" ? "ev" : strategy, thresholds, details);
  }

  function campaignBudget(n, cfg, share) {
    const offer = defaultOffer(cfg);
    return Math.floor((share == null ? cfg.campaign.budget_share : share) * n + 1e-9) * (offer.offer_cost + offer.contact_cost);
  }

  function getParam(cfg, key) { return key.split(".").reduce((o, k) => o[k], cfg); }
  function setParam(cfg, key, value) {
    const parts = key.split("."), last = parts.pop();
    const target = parts.reduce((o, k) => o[k], cfg);
    if (!(last in target)) throw new Error("Unknown parameter: " + key);
    target[last] = value;
  }

  function applyOverrides(cfg, overrides) {
    const out = clone(cfg);
    for (const [key, value] of Object.entries(overrides)) {
      if (key === "save_rate") {
        const shift = value - defaultOffer(cfg).save_rate;
        out.offers.forEach((o) => { o.save_rate = Math.min(1, Math.max(0, o.save_rate + shift)); });
      } else if (key === "offer_cost_multiplier") {
        out.offers.forEach((o, i) => { o.offer_cost = cfg.offers[i].offer_cost * value; });
      } else if (key === "contact_cost") {
        out.offers.forEach((o) => { o.contact_cost = Number(value); });
      } else if (key === "value.tenure_factor_spread") {
        out.value.tenure_factors = { new: 1 - value, developing: 1.0, loyal: 1 + value };
      } else setParam(out, key, value);
    }
    return out;
  }

  function baseValue(cfg, key) {
    if (key === "save_rate") return defaultOffer(cfg).save_rate;
    if (key === "offer_cost_multiplier") return 1.0;
    if (key === "contact_cost") return defaultOffer(cfg).contact_cost;
    if (key === "value.tenure_factor_spread") { const f = cfg.value.tenure_factors; return (f.loyal - f.new) / 2; }
    return getParam(cfg, key);
  }

  // Re-price a frozen list (same customers, same offers) under changed assumptions (python: fixed_campaign).
  function fixedCampaign(customers, reference, budget, cfg, offers, thresholds) {
    const options = offerOptions(valueCustomers(customers, cfg), offers.map((o) => ({ ...o, eligibility: {} })));
    const index = new Map(options.map((o) => [o.customer_id + "\u0000" + o.offer_id, o]));
    const table = reference.map((r) => {
      const o = index.get(r.customer_id + "\u0000" + r.offer_id);
      if (!o) throw new Error("A fixed list must keep every customer and offer of the reference list");
      const row = { ...o.c, ...o, selected: r.selected };
      delete row.c;
      return row;
    });
    const stats = summarize(table, budget, thresholds);
    stats.budget_feasible = stats.cost <= budget + 1e-7;
    return { table, stats };
  }

  function breakEven(target, cfg, populationOptions) {
    const picked = target.filter((r) => r.selected);
    const qStandard = defaultOffer(cfg).save_rate;
    const out = { selected_count: picked.length };
    if (picked.length) {
      const sum = (f) => picked.reduce((s, r) => s + f(r), 0);
      const pqv = sum((r) => r.churn_probability * r.assumed_save_rate * r.customer_value);
      const p = sum((r) => r.churn_probability), pq = sum((r) => r.churn_probability * r.assumed_save_rate);
      const cost = sum((r) => r.total_cost), offerCost = sum((r) => r.offer_cost), contact = sum((r) => r.contact_cost);
      const multiplier = pqv > 0 ? cost / pqv : null, mix = p > 0 ? pq / p : null;
      Object.assign(out, {
        save_rate_multiplier: multiplier,
        break_even_default_save_rate: multiplier != null && qStandard > 0 ? qStandard * multiplier : null,
        mix_save_rate: mix, break_even_mix_save_rate: multiplier != null && mix != null ? mix * multiplier : null,
        offer_cost_multiplier: offerCost > 0 ? (pqv - contact) / offerCost : null,
      });
    }
    if (populationOptions) {
      let min = Infinity;
      for (const o of populationOptions) {
        if (o.assumed_save_rate > 0 && isFinite(o.break_even_save_rate)) min = Math.min(min, qStandard / o.assumed_save_rate * o.break_even_save_rate);
      }
      out.minimum_viable_save_rate = qStandard > 0 && isFinite(min) ? min : null;
    }
    return out;
  }

  function quadrant(r, thresholds) {
    const risk = r.churn_probability >= thresholds.risk, value = r.customer_value >= thresholds.value;
    return risk && value ? QUADRANTS[0] : risk ? QUADRANTS[1] : value ? QUADRANTS[2] : QUADRANTS[3];
  }

  function tornado(customers, budget, cfg, strategy, thresholds) {
    const reference = runStrategy(customers, budget, cfg, strategy, thresholds);
    const rows = cfg.assumption_register.map((item) => {
      const row = { id: item.id, parameter: item.parameter, label: item.label, unit: item.unit, low: item.low, high: item.high, base: baseValue(cfg, item.parameter) };
      for (const end of ["low", "high"]) {
        const changed = applyOverrides(cfg, { [item.parameter]: item[end] });
        row[`net_${end}_retarget`] = runStrategy(customers, budget, changed, strategy, thresholds).stats.expected_net_value;
        row[`net_${end}_fixed`] = fixedCampaign(customers, reference.table, budget, changed, strategyOffers(changed, strategy), thresholds).stats.expected_net_value;
      }
      row.base_net = reference.stats.expected_net_value;
      row.swing_retarget = Math.abs(row.net_high_retarget - row.net_low_retarget);
      return row;
    });
    return rows.sort((a, b) => b.swing_retarget - a.swing_retarget);
  }

  function scenarioTable(customers, budget, cfg, strategy, thresholds) {
    const reference = runStrategy(customers, budget, cfg, strategy, thresholds);
    return Object.entries(cfg.sensitivity.scenarios).map(([name, overrides]) => {
      const changed = applyOverrides(cfg, overrides);
      const s = runStrategy(customers, budget, changed, strategy, thresholds).stats;
      const frozen = fixedCampaign(customers, reference.table, budget, changed, strategyOffers(changed, strategy), thresholds).stats;
      return { scenario: name, selected_count: s.selected_count, cost: s.cost, expected_net_value: s.expected_net_value, roi: s.roi,
        expected_saved: s.expected_saved, fixed_expected_net_value: frozen.expected_net_value, fixed_roi: frozen.roi };
    });
  }

  function sensitivity(customers, budget, cfg, strategy, thresholds) {
    const grids = cfg.sensitivity;
    const reference = runStrategy(customers, budget, cfg, strategy, thresholds);
    const referenceIds = new Set(reference.table.filter((r) => r.selected).map((r) => r.customer_id));
    const cases = [];
    for (const q of grids.save_rate) for (const m of grids.offer_cost_multiplier) cases.push(["save_rate x offer_cost", q, m, { save_rate: q, offer_cost_multiplier: m }]);
    for (const axis of ["contact_cost", "value.margin", "value.base_horizon_months", "value.discount_rate_annual"]) for (const v of grids[axis]) cases.push([axis, v, 1.0, { [axis]: v }]);
    const rows = [];
    for (const [axis, parameter, multiplier, overrides] of cases) {
      const changed = applyOverrides(cfg, overrides);
      const retarget = runStrategy(customers, budget, changed, strategy, thresholds);
      const frozen = fixedCampaign(customers, reference.table, budget, changed, strategyOffers(changed, strategy), thresholds);
      const ids = new Set(retarget.table.filter((r) => r.selected).map((r) => r.customer_id));
      const union = new Set([...ids, ...referenceIds]);
      const changedIds = [...union].filter((x) => ids.has(x) !== referenceIds.has(x)).length;
      for (const [mode, s] of [["fixed", frozen.stats], ["retarget", retarget.stats]]) {
        rows.push({ axis, parameter, cost_multiplier: multiplier, mode, strategy, turnover: mode === "fixed" ? 0 : (union.size ? changedIds / union.size : 0),
          budget_feasible: s.cost <= budget + 1e-7, selected_count: s.selected_count, cost: s.cost, expected_net_value: s.expected_net_value, roi: s.roi });
      }
    }
    return rows;
  }

  function shareGrid(cfg) {
    const g = cfg.campaign.recommendation.share_grid, out = [];
    for (let x = g.start; x <= g.stop + g.step / 2; x += g.step) out.push(Math.round(x * 1e6) / 1e6);
    return out;
  }

  function profitCurve(customers, cfg, strategies, thresholds) {
    const rows = [];
    for (const strategy of strategies) {
      let previous = null;
      for (const share of shareGrid(cfg)) {
        const budget = campaignBudget(customers.length, cfg, share);
        const s = runStrategy(customers, budget, cfg, strategy, thresholds).stats;
        const row = { budget_share: share, budget, strategy, selected_count: s.selected_count, cost: s.cost, expected_net_value: s.expected_net_value, roi: s.roi,
          marginal_net: null, marginal_cost: null, marginal_roi: null };
        if (previous) {
          row.marginal_net = s.expected_net_value - previous.expected_net_value;
          row.marginal_cost = s.cost - previous.cost;
          row.marginal_roi = row.marginal_cost > 1e-9 ? row.marginal_net / row.marginal_cost : null;
        }
        rows.push(row);
        previous = row;
      }
    }
    return rows;
  }

  // Seeded generator (mulberry32): the browser cannot reproduce numpy's draws, only their distribution.
  function rng(seed) {
    let a = seed >>> 0;
    return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  }

  function triangular(u, a, c, b) {
    if (b <= a) return a;
    const f = (c - a) / (b - a);
    return u < f ? a + Math.sqrt(u * (b - a) * (c - a)) : b - Math.sqrt((1 - u) * (b - a) * (b - c));
  }

  function drawAssumptions(cfg, draws, seed) {
    const random = rng(seed), out = {};
    for (const item of cfg.assumption_register) {
      const base = Number(baseValue(cfg, item.parameter));
      const a = Math.min(item.low, base), b = Math.max(item.high, base);
      out[item.parameter] = Array.from({ length: draws }, () => triangular(random(), a, base, b));
    }
    return out;
  }

  // Net value of a frozen list for every row of drawn assumptions (python: reprice_frozen).
  function repriceFrozen(table, cfg, draws) {
    const picked = table.filter((r) => r.selected);
    const n = Object.values(draws)[0].length;
    const nets = new Float64Array(n);
    if (!picked.length) return nets;
    const factors = cfg.value.tenure_factors, spread0 = baseValue(cfg, "value.tenure_factor_spread"), q0 = defaultOffer(cfg).save_rate;
    const drawn = (key, i) => (key in draws ? draws[key][i] : Number(baseValue(cfg, key)));
    for (let i = 0; i < n; i++) {
      const shift = drawn("value.tenure_factor_spread", i) - spread0, monthly = Math.pow(1 + drawn("value.discount_rate_annual", i), 1 / 12) - 1;
      const horizon = drawn("value.base_horizon_months", i), margin = drawn("value.margin", i), contact = drawn("contact_cost", i);
      const costMultiplier = drawn("offer_cost_multiplier", i), qShift = drawn("save_rate", i) - q0;
      let net = 0;
      for (const r of picked) {
        const factor = Math.max(0, r.tenure_segment === "new" ? factors.new - shift : r.tenure_segment === "loyal" ? factors.loyal + shift : factors.developing);
        const months = Math.min(cfg.value.horizon_cap_months, horizon * factor);
        const annuity = monthly > 0 ? (1 - Math.pow(1 + monthly, -months)) / monthly : months;
        const q = Math.min(1, Math.max(0, r.assumed_save_rate + qShift));
        net += r.churn_probability * q * r.MonthlyCharges * margin * annuity - r.offer_cost * costMultiplier - contact;
      }
      nets[i] = net;
    }
    return nets;
  }

  // ---- Scoring new customers with the deployed model (python: data.validate + modeling.score_frame) ------------
  function parseCsv(text) {
    const out = [];
    let row = [], field = "", quoted = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (quoted) {
        if (ch === '"') { if (text[i + 1] === '"') { field += '"'; i++; } else quoted = false; } else field += ch;
      } else if (ch === '"') quoted = true;
      else if (ch === ",") { row.push(field); field = ""; }
      else if (ch === "\n" || ch === "\r") { if (ch === "\r" && text[i + 1] === "\n") i++; row.push(field); out.push(row); row = []; field = ""; }
      else field += ch;
    }
    if (field !== "" || row.length) { row.push(field); out.push(row); }
    return out.filter((r) => r.length > 1 || r[0] !== "");
  }

  function validateUpload(text, model) {
    const errors = [];
    const table = parseCsv(text.replace(/^\uFEFF/, ""));
    if (!table.length) return { errors: [[0, "file", "A UTF-8, comma-separated CSV is required"]] };
    const header = table[0].map((h) => h.trim()), body = table.slice(1);
    if (body.length > 50000) return { errors: [[0, "file", "Limit is 50,000 customers"]] };
    const required = model.schema.filter((c) => !model.optional.includes(c));
    for (const col of required.filter((c) => !header.includes(c)).sort()) errors.push([0, col, "Required column missing"]);
    if (errors.length) return { errors };
    if (!body.length) return { errors: [[0, "file", "CSV contains no customers"]] };
    const ignored = header.filter((h) => !model.schema.includes(h)).sort();
    const records = body.map((cells) => Object.fromEntries(header.map((h, j) => [h, (cells[j] ?? "").trim()])));
    const ids = new Map();
    records.forEach((r, i) => { ids.set(r.customerID, (ids.get(r.customerID) || 0) + 1); });
    records.forEach((r, i) => {
      const line = i + 2;
      if (!r.customerID) errors.push([line, "customerID", "Empty ID"]);
      else if (ids.get(r.customerID) > 1) errors.push([line, "customerID", "Duplicate ID"]);
      for (const col of ["tenure", "MonthlyCharges", "TotalCharges"]) {
        if (r[col] === "" || r[col] == null) { r[col] = null; continue; }
        const v = Number(r[col]);
        if (!isFinite(v) || v < 0 || (col === "tenure" && v % 1 !== 0)) errors.push([line, col, "Must be a finite, non-negative number; tenure must be an integer"]);
        r[col] = v;
      }
      if (r.tenure === 0 && r.TotalCharges == null) r.TotalCharges = 0;
      if ("SeniorCitizen" in r && ["0.0", "1.0"].includes(r.SeniorCitizen)) r.SeniorCitizen = r.SeniorCitizen[0];
      for (const [col, allowed] of Object.entries(model.domains)) {
        if (!(col in r)) continue;
        if (!allowed.includes(r[col])) errors.push([line, col, "Value outside allowed domain: " + allowed.join(", ")]);
      }
      const deps = [["PhoneService", "No", "MultipleLines", "No phone service"],
        ...["OnlineSecurity", "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies"].map((c) => ["InternetService", "No", c, "No internet service"])];
      for (const [parent, absent, child, unavailable] of deps) {
        if ((r[parent] === absent) !== (r[child] === unavailable)) errors.push([line, child, `Service contradiction: ${child}='${unavailable}' if and only if ${parent}='${absent}'`]);
      }
    });
    return { errors, records, ignored };
  }

  function score(records, model) {
    const linear = model.linear;
    return records.map((r) => {
      let logit = linear.intercept;
      for (const t of linear.terms) {
        if (t.kind === "num") logit += t.coef * (((r[t.column] == null ? t.median : r[t.column]) - t.mean) / t.scale);
        else if (t.kind === "flag") logit += t.coef * (r[t.column] === "Yes" ? 1 : 0);
        else logit += t.coef * (r[t.column] === t.level ? 1 : 0);
      }
      const p = 1 / (1 + Math.exp(-logit));
      const split = model.reference_splits[r.customerID];
      const origin = { t: "uploaded_matches_train_do_not_evaluate", v: "uploaded_matches_validation", s: "uploaded_matches_test" }[split] || "uploaded_not_in_reference";
      const out = { ...r, customer_id: r.customerID, churn_probability: p, risk_band: p <= 0.25 ? "low" : p <= 0.5 ? "medium" : "high", prediction_origin: origin };
      for (const t of linear.terms) if (t.kind === "num" && out[t.column] == null) out[t.column] = t.median; // training medians, as score_frame fills them
      if (r.Churn === "Yes" || r.Churn === "No") out.churn = r.Churn === "Yes" ? 1 : 0;
      return out;
    });
  }

  return { SEGMENTS, QUADRANTS, STRATEGY_LABELS, COMPARED, rows, tenureSegment, defaultOffer, valueCustomers, offerOptions, contactLimit, selectOptions,
    campaign, strategyOffers, runStrategy, campaignBudget, applyOverrides, baseValue, fixedCampaign, breakEven, quadrant, tornado, scenarioTable,
    sensitivity, shareGrid, profitCurve, drawAssumptions, repriceFrozen, parseCsv, validateUpload, score };
})();
if (typeof module !== "undefined") module.exports = Engine;
