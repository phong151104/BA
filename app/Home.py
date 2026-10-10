from __future__ import annotations

import io
import json
import time
import zipfile
from copy import deepcopy
import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from telco_retention.common import ROOT, latest_run, read_json, jsonable
from telco_retention.data import SEGMENTS, parse_upload, tenure_segment, DataValidationError
from telco_retention.modeling import score_frame
from telco_retention.business import STRATEGY_LABELS, campaign, default_offer, offer_options, value_customers
from telco_retention.analysis import (QUADRANTS, apply_overrides, break_even, campaign_budget, fixed_campaign, profit_curve, quadrant,
                                      scenario_table, sensitivity, strategy_offers, tornado)

BLUE, ORANGE, AQUA, GREY, INK, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#b9b8b2", "#0b0b0b", "#898781"
PAGES = ["Overview", "Campaign builder", "Scenarios & budget", "Model & data"]
MODES = {"ev": "Single standard offer", "segment_offers": "Segment-specific offers"}
KPI_LABELS = ["Expected net value", "ROI", "Customers contacted", "Precision among contacted", "High-risk/high-value coverage"]

st.set_page_config(page_title="Retention Lab", page_icon="◈", layout="wide")
st.markdown("""<style>
.stApp {background:#f9f9f7;} .block-container {padding-top:3.2rem; max-width:1480px;}
h1,h2,h3 {color:#0b0b0b;} [data-testid="stMetric"] {background:#fcfcfb;border:1px solid rgba(11,11,11,.10);border-radius:12px;padding:14px 16px;}
[data-testid="stSidebar"] {background:#f1f0ec;}
.strip {background:#fcfcfb;border:1px solid rgba(11,11,11,.10);border-radius:10px;padding:8px 14px;margin:2px 0 14px;font-size:13px;color:#52514e;line-height:1.6;}
.strip b {color:#0b0b0b;font-weight:600;}
.hero h2 {margin:0 0 4px;} .hero p {color:#52514e;margin:0 0 10px;font-size:15px;}
</style>""", unsafe_allow_html=True)


@st.cache_resource
def load_bundle(run_name):
    return joblib.load(ROOT / "artifacts/runs" / run_name / "model.joblib")


@st.cache_data
def artifact(run_name, name):
    path = ROOT / "artifacts/runs" / run_name / name
    if not path.exists():
        st.error(f"Missing result file {name}. Run `python -m telco_retention run-all` first.")
        st.stop()
    return pd.read_csv(path) if name.endswith(".csv") else read_json(path)


@st.cache_data(show_spinner=False)
def calculate(scores, budget, settings, offers, strategy, thresholds):
    return campaign(scores, budget, settings, offers, strategy, thresholds)


@st.cache_data(show_spinner=False)
def scenario_bundle(scores, budget, settings, strategy, thresholds):
    curve = profit_curve(scores, settings, [strategy, "risk"], thresholds)
    return {"tornado": tornado(scores, budget, settings, strategy, thresholds), "scenarios": scenario_table(scores, budget, settings, strategy, thresholds),
            "sensitivity": sensitivity(scores, budget, settings, strategy, thresholds), "curve": curve}


def control(key, default):
    # Native persistence keeps Python state and remounted browser widgets in sync across pages.
    st.session_state.campaign_controls.setdefault(key, default)
    if key not in st.session_state:
        st.session_state[key] = default
    return {"key": key, "persist_state": "session"}


def usd(x, digits=0):
    return "n/a" if x is None else (f"-${abs(x):,.{digits}f}" if x < 0 else f"${x:,.{digits}f}")


def pct(x, digits=1):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{digits}%}"


def metric_cards(stats, baseline, labelled):
    delta = stats["expected_net_value"] - baseline["expected_net_value"]
    precision = stats["precision_contacted"] if labelled else stats["expected_precision"]
    values = [usd(stats["expected_net_value"]), pct(stats["roi"]), f"{stats['selected_count']:,}", pct(precision), pct(stats.get("high_risk_high_value_coverage"))]
    deltas = [f"{usd(delta)} vs risk-only", None, f"{usd(stats['cost'])} spent", None if labelled else "expected (no labels)",
              f"risk-only: {pct(baseline.get('high_risk_high_value_coverage'))}"]
    helps = ["Sum of p(churn) x save rate x customer value - offer and contact cost, for the contacted list. Delta: same budget, highest-risk rule.",
             "Expected net value / campaign cost.", "Customers that receive an offer within the budget and contact cap.",
             "Share of contacted customers who actually churned (labelled data) or their mean predicted churn probability (unlabelled).",
             "Share of high-risk and high-value customers (validation 75th percentiles) that the list reaches."]
    for col, label, value, d, h in zip(st.columns(5), KPI_LABELS, values, deltas, helps):
        col.metric(label, value, d, help=h, delta_color="off" if label != "Expected net value" else "normal")


def strip(cfg, budget, n, mode, sid, offers):
    offer = default_offer(cfg)
    v = cfg["value"]
    factors = "/".join(f"{v['tenure_factors'][s]:g}" for s in SEGMENTS)
    extra = f" · {len(offers)} offers in catalog" if mode == "segment_offers" else ""
    st.markdown(f"""<div class="strip"><b>Assumptions</b> · Budget <b>{usd(budget)}</b> for {n:,} customers · Offer <b>{offer['label']}</b>:
    {usd(offer['offer_cost'])} + {usd(offer['contact_cost'])} contact, save rate <b>{offer['save_rate']:.0%}</b>{extra} · Margin <b>{v['margin']:.0%}</b> ·
    Value horizon <b>{v['base_horizon_months']:g} months</b> (x{factors} by tenure) · Discount <b>{v['discount_rate_annual']:.0%}/yr</b> ·
    Scenario <code>{sid}</code></div>""", unsafe_allow_html=True)


def campaign_zip(target, stats, cfg):
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("targeting_all.csv", target.to_csv(index=False).encode("utf-8-sig"))
        archive.writestr("selected_customers.csv", target.loc[target.selected].to_csv(index=False).encode("utf-8-sig"))
        archive.writestr("assumptions.json", json.dumps(jsonable({"scenario_id": stats["scenario_id"], "value": cfg["value"], "offers": stats["scenario"]["offers"],
                                                                    "budget": stats["scenario"]["budget"], "strategy": stats["scenario"]["strategy"]}), indent=2))
        archive.writestr("summary.json", json.dumps(jsonable({k: v for k, v in stats.items() if k != "scenario"}), indent=2))
    return memory.getvalue()


st.sidebar.markdown("## ◈ Retention Lab")
st.sidebar.caption("Profit-aware churn & retention targeting")
page = st.sidebar.radio("Navigate", PAGES, key="page")
try:
    run = latest_run()
    if not (run / "simulation_manifest.json").exists():
        raise FileNotFoundError("The pipeline has not finished the simulate step")
    bundle = load_bundle(run.name)
    demo = artifact(run.name, "scorecard.csv").query("split == 'test'").copy()
    thresholds = read_json(run / "targeting_thresholds.json")
    decisions = read_json(run / "validation_decisions.json")
except (FileNotFoundError, KeyError) as exc:
    st.error("Analysis results are not ready. Run `python -m telco_retention run-all`, then reopen the app.")
    st.caption(str(exc))
    st.stop()

if st.session_state.get("controls_run") != run.name:
    for key in st.session_state.get("campaign_controls", {}):
        st.session_state.pop(key, None)
    st.session_state.campaign_controls = {}
    st.session_state.controls_run = run.name
    st.session_state.pop("scenario_results", None)

sources = ["Demo: held-out test customers"]
if "uploaded_scores" in st.session_state:
    sources.append("Uploaded CSV")
source = st.sidebar.selectbox("Customer list", sources, key="source")
scores = demo if source == sources[0] else st.session_state.uploaded_scores
labelled = "churn" in scores
st.sidebar.caption(f"{len(scores):,} customers · deployed model: calibrated {bundle['metadata']['selected_model'].replace('_', ' ')} · run {run.name[:15]}")
st.sidebar.markdown("---")
st.sidebar.caption("All money figures are expected values under the visible assumptions (USD of the sample company). They are not realised profit and not causal uplift estimates.")

# ---- Assumptions (one set of controls shared by every page) -------------------------------------------
cfg = deepcopy(bundle["metadata"]["config"])
standard = default_offer(cfg)
recommended = decisions["strategy_selection"]["strategy"]
show_controls = page in ["Campaign builder", "Scenarios & budget", "Overview"]
panel = st.expander("Budget and assumptions", expanded=page == "Campaign builder") if show_controls else None


def widget(kind, column, label, key, default, **kwargs):
    if panel is None:
        st.session_state.campaign_controls.setdefault(key, default)
        return st.session_state.get(key, default)
    return getattr(column, kind)(label, **kwargs, **control(key, default))


cols = panel.columns(4) if panel else [None] * 4
budget = widget("number_input", cols[0], "Budget (USD)", "budget_" + ("demo" if source == sources[0] else "upload"), float(campaign_budget(len(scores), cfg)), min_value=0.0, step=100.0)
mode = widget("selectbox", cols[1], "Offer policy", "offer_mode", recommended, options=list(MODES), format_func=MODES.get)
standard["save_rate"] = widget("slider", cols[2], "Save rate of the standard offer", "save_rate", float(standard["save_rate"]), min_value=0.0, max_value=1.0, step=0.01)
standard["offer_cost"] = widget("number_input", cols[3], "Standard offer cost (USD)", "offer_cost", float(standard["offer_cost"]), min_value=0.0, step=1.0)
cols = panel.columns(4) if panel else [None] * 4
contact = widget("number_input", cols[0], "Contact cost per customer (USD)", "contact_cost", float(standard["contact_cost"]), min_value=0.0, step=0.5)
cfg["value"]["margin"] = widget("slider", cols[1], "Contribution margin", "margin", float(cfg["value"]["margin"]), min_value=0.0, max_value=1.0, step=0.01)
cfg["value"]["base_horizon_months"] = widget("number_input", cols[2], "Value horizon (months)", "horizon", float(cfg["value"]["base_horizon_months"]), min_value=0.0, step=1.0)
cfg["value"]["discount_rate_annual"] = widget("slider", cols[3], "Annual discount rate", "discount", float(cfg["value"]["discount_rate_annual"]), min_value=0.0, max_value=0.5, step=0.01)
cols = panel.columns(4) if panel else [None] * 4
for column, segment, label in zip(cols, SEGMENTS, ["Horizon factor: new (<=12 months)", "Horizon factor: developing (13-24)", "Horizon factor: loyal (>24)"]):
    cfg["value"]["tenure_factors"][segment] = widget("number_input", column, label, "tenure_" + segment, float(cfg["value"]["tenure_factors"][segment]), min_value=0.0, step=0.05)
segments = widget("multiselect", cols[3], "Eligible tenure segments", "eligible_segments", list(SEGMENTS), options=list(SEGMENTS))
for offer in cfg["offers"]:
    offer["contact_cost"] = contact
if mode == "segment_offers":
    if panel:
        panel.caption("Segment-specific offers: each customer can only receive offers whose eligibility rule they meet; the optimiser picks the best mix within budget.")
    for offer in cfg["offers"]:
        if offer["offer_id"] == standard["offer_id"]:
            continue
        cols = panel.columns([2, 1, 1]) if panel else [None] * 3
        if panel:
            rule = "; ".join(f"{k} in {v}" for k, v in offer.get("eligibility", {}).items()) or "all customers"
            cols[0].markdown(f"**{offer['label']}**  \n<span style='color:#52514e;font-size:13px'>Eligible: {rule}</span>", unsafe_allow_html=True)
        offer["offer_cost"] = widget("number_input", cols[1], f"Cost: {offer['offer_id']}", "cost_" + offer["offer_id"], float(offer["offer_cost"]), min_value=0.0, step=1.0)
        offer["save_rate"] = widget("slider", cols[2], f"Save rate: {offer['offer_id']}", "rate_" + offer["offer_id"], float(offer["save_rate"]), min_value=0.0, max_value=1.0, step=0.01)

population = scores.loc[tenure_segment(scores.tenure).astype(str).isin(segments)].copy()
if population.empty:
    st.info("No customers in the selected tenure segments.")
    st.stop()
offers = strategy_offers(cfg, mode)
rule = "ev"
start = time.perf_counter()
with st.spinner("Optimising the campaign..."):
    target, stats = calculate(population, budget, cfg, offers, rule, thresholds)
    _, baseline = calculate(population, budget, cfg, [default_offer(cfg)], "risk", thresholds)
st.session_state.last_compute_seconds = time.perf_counter() - start
strip(cfg, budget, len(population), mode, stats["scenario_id"], offers)

# ---- Model & data -----------------------------------------------------------------------------------
if page == "Model & data":
    st.title("Model & data")
    metrics = artifact(run.name, "test_metrics.csv").set_index("model")
    intervals = artifact(run.name, "bootstrap_intervals.csv").set_index("metric")
    chosen = bundle["metadata"]["selected_model"] + "_calibrated"
    st.subheader(f"Deployed model: calibrated {bundle['metadata']['selected_model'].replace('_', ' ')}")
    st.caption("Chosen on the validation split by a pre-set rule (best average precision within 0.01, Brier within 0.002, prefer the simpler model). Metrics below are on the untouched test split.")
    row = metrics.loc[chosen]
    for col, (key, label) in zip(st.columns(5), [("roc_auc", "ROC-AUC"), ("average_precision", "PR-AUC (average precision)"), ("brier", "Brier score"), ("ece", "Expected calibration error"), ("calibration_slope", "Calibration slope")]):
        ci = f"95% CI {intervals.loc[key, 'lower_95']:.3f}-{intervals.loc[key, 'upper_95']:.3f}" if key in intervals.index else None
        col.metric(label, f"{row[key]:.3f}", ci, delta_color="off")
    a, b = st.columns(2)
    calibration = artifact(run.name, "calibration.csv")
    calibration = calibration.loc[calibration.model.isin([chosen, "xgboost_calibrated"])].replace({chosen: "Deployed (calibrated logistic)", "xgboost_calibrated": "Challenger (calibrated XGBoost)"})
    fig = px.line(calibration, x="predicted", y="observed", color="model", markers=True, title="Calibration on the test split",
                  labels={"predicted": "Predicted churn probability", "observed": "Observed churn rate", "model": ""}, color_discrete_sequence=[BLUE, ORANGE])
    fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", name="Perfect calibration", line={"color": GREY, "width": 1})
    a.plotly_chart(fig, width="stretch")
    gains = artifact(run.name, "gains_test.csv")
    fig = go.Figure([go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Random contact", line={"color": GREY, "width": 1}),
                     go.Scatter(x=np.r_[0, gains.cumulative_customer_share], y=np.r_[0, gains.cumulative_churner_capture], mode="lines+markers", name="By predicted risk", line={"color": BLUE})])
    fig.update_layout(title=f"Cumulative gains (top-decile lift {gains.lift.iloc[0]:.1f}x)", xaxis_title="Share of customers contacted", yaxis_title="Share of churners reached", xaxis_tickformat=".0%", yaxis_tickformat=".0%")
    b.plotly_chart(fig, width="stretch")
    coefficients = artifact(run.name, "logistic_coefficients.csv")
    picks = pd.concat([coefficients.nsmallest(6, "coefficient"), coefficients.nlargest(6, "coefficient")]).drop_duplicates().sort_values("coefficient")
    picks["direction"] = np.where(picks.coefficient > 0, "Raises churn risk", "Lowers churn risk")
    st.plotly_chart(px.bar(picks, x="coefficient", y="feature", orientation="h", color="direction", color_discrete_map={"Raises churn risk": ORANGE, "Lowers churn risk": BLUE},
                           title="What moves the deployed model's score (log-odds; associations, not causes)", labels={"coefficient": "Coefficient", "feature": "", "direction": ""}), width="stretch")
    with st.expander("All candidate models: validation and test metrics"):
        st.dataframe(artifact(run.name, "validation_metrics.csv"), hide_index=True, width="stretch")
        st.dataframe(metrics.reset_index(), hide_index=True, width="stretch")
        st.dataframe(artifact(run.name, "segment_errors.csv"), hide_index=True, width="stretch")
    st.subheader("Challenger: XGBoost (not deployed) - SHAP attribution")
    st.caption("TreeSHAP on 200 validation customers, log-odds scale. It explains the raw XGBoost challenger, not the deployed calibrated logistic model, and it is not causal.")
    shap = artifact(run.name, "shap_global.csv").head(12).sort_values("mean_abs_shap")
    st.plotly_chart(px.bar(shap, x="mean_abs_shap", y="feature", orientation="h", title="Mean |SHAP| by feature", color_discrete_sequence=[ORANGE], labels={"mean_abs_shap": "Mean |SHAP|", "feature": ""}), width="stretch")
    local = artifact(run.name, "shap_local.csv")
    customer = st.selectbox("Explain one validation customer (challenger model)", local.sort_values("raw_probability", ascending=False).customer_id.tolist())
    row = local.loc[local.customer_id.eq(customer)].iloc[0]
    contributions = row.drop(["customer_id", "base_value", "raw_probability"]).astype(float)
    top = contributions.abs().nlargest(10).index
    st.plotly_chart(px.bar(pd.DataFrame({"feature": top, "SHAP": contributions[top].values}), x="SHAP", y="feature", orientation="h", color_discrete_sequence=[ORANGE],
                           title=f"{customer}: challenger probability {row.raw_probability:.1%}"), width="stretch")
    st.subheader("Data source and quality")
    source_info, quality = artifact(run.name, "dataset_source.json"), artifact(run.name, "data_quality.json")
    st.markdown(f"IBM Telco Customer Churn sample, downloaded from [{source_info['source']}]({source_info['dataset_page']}) on {source_info['downloaded_at_utc'][:10]}; "
                f"{source_info['rows']:,} customers, SHA-256 `{source_info['sha256'][:16]}...`. {quality['total_charges_filled_zero']} blank TotalCharges for new customers (tenure 0) set to 0; "
                f"{quality['duplicates_removed']} duplicate rows. Split 60/20/20 train/validation/test, stratified, seed {cfg['seed']}.")
    st.subheader("Score new customers")
    st.write("Upload a CSV with the same columns as the template to score it with the trained model. Up to 10 MB / 50,000 rows, UTF-8, comma-separated.")
    st.download_button("Download the unlabelled CSV template", (ROOT / "data/examples/customers_unlabeled.csv").read_bytes(), "customers_template.csv", "text/csv")
    uploaded = st.file_uploader("Choose a customer CSV", type=["csv"])
    if uploaded is not None:
        try:
            frame, quality = parse_upload(uploaded.getvalue())
            with st.spinner("Validating and scoring..."):
                predicted = score_frame(frame, bundle)
            st.session_state.uploaded_scores = predicted
            st.success(f"Scored {len(predicted):,} customers. Choose 'Uploaded CSV' in the sidebar to build a campaign for them.")
            if quality["ignored_columns"]:
                st.info("Ignored columns: " + ", ".join(quality["ignored_columns"]))
            st.dataframe(predicted[["customer_id", "churn_probability", "risk_band", "prediction_origin"]], hide_index=True, width="stretch",
                         column_config={"customer_id": "Customer", "churn_probability": st.column_config.NumberColumn("Churn probability", format="%.3f"), "risk_band": "Risk band", "prediction_origin": "Origin"})
            if predicted.prediction_origin.str.contains("matches_").any():
                st.warning("Some IDs match the project's own data. Check 'Origin': IDs seen in training are not an independent evaluation, and an ID match does not verify content or timing.")
            st.download_button("Download scores", predicted.to_csv(index=False).encode("utf-8-sig"), "scores.csv", "text/csv")
        except DataValidationError as exc:
            st.error("The CSV is not valid; nothing was imported. The previous customer list is unchanged.")
            st.dataframe(exc.errors, hide_index=True, width="stretch")
    st.stop()

metric_cards(stats, baseline, labelled)
st.caption(f"Budget used {usd(stats['cost'])} of {usd(budget)} · expected customers saved {stats['expected_saved']:.1f} · solver: {stats['solver']['status']} · compute {st.session_state.last_compute_seconds:.2f}s")
if stats["solver"]["status"] in ["feasible_time_limit", "heuristic_fallback"]:
    st.warning(f"Global optimality not proven. Solver gap: {stats['solver']['gap']}")
if stats["selected_count"] == 0:
    st.info("Nobody is selected: no customer has positive expected value under these assumptions, or the budget is below one offer. Not running the campaign is the right decision here.")

# ---- Overview -----------------------------------------------------------------------------------------
if page == "Overview":
    st.markdown("<div class='hero'><h2>Which customers should get a retention offer?</h2><p>Spend a fixed budget where churn risk and customer value together return the most - and know when not to spend.</p></div>", unsafe_allow_html=True)
    options = offer_options(value_customers(population, cfg), [default_offer(cfg)])
    be = break_even(target, cfg, options)
    if stats["selected_count"]:
        st.success(f"**Recommended action:** offer **{stats['selected_count']:,} customers** a retention offer for **{usd(stats['cost'])}**. Expected net value **{usd(stats['expected_net_value'])}** "
                   f"(ROI {pct(stats['roi'])}), **{usd(stats['expected_net_value'] - baseline['expected_net_value'])} more** than calling the highest-risk customers with the same budget. "
                   f"The list stays profitable while the true save rate is above **{pct(be.get('break_even_default_save_rate'))}**; validate it with the pilot before scaling.")
    left, right = st.columns([1.45, 1])
    chart = target.assign(decision=np.where(target.selected, "Contacted", "Not contacted"))
    fig = px.scatter(chart, x="churn_probability", y="customer_value", color="decision", color_discrete_map={"Contacted": BLUE, "Not contacted": GREY}, opacity=.75,
                     hover_data={"customer_id": True, "tenure_segment": True, "expected_net_value": ":.2f", "offer_id": True}, title="Risk x value: who gets contacted",
                     labels={"churn_probability": "Predicted churn probability", "customer_value": "Customer value proxy (USD)", "decision": ""})
    fig.add_vline(x=thresholds["risk"], line_dash="dash", line_color=MUTED, line_width=1)
    fig.add_hline(y=thresholds["value"], line_dash="dash", line_color=MUTED, line_width=1)
    left.plotly_chart(fig, width="stretch")
    target["quadrant"] = quadrant(target, thresholds)
    baseline_table, _ = calculate(population, budget, cfg, [default_offer(cfg)], "risk", thresholds)
    risk_pick = baseline_table.set_index("customer_id").selected
    target["risk_selected"] = target.customer_id.map(risk_pick).fillna(False)
    matrix = target.groupby("quadrant", observed=False).agg(customers=("customer_id", "size"), value_at_risk=("customer_value", lambda s: float((s * target.loc[s.index, "churn_probability"]).sum())),
                                                            contacted=("selected", "sum"), risk_only=("risk_selected", "sum")).reindex(QUADRANTS).reset_index()
    matrix["value_at_risk_share"] = matrix.value_at_risk / matrix.value_at_risk.sum()
    right.markdown("**Risk x value segments** (cut-offs fitted on validation)")
    right.dataframe(matrix[["quadrant", "customers", "value_at_risk_share", "contacted", "risk_only"]], hide_index=True, width="stretch", column_config={
        "quadrant": "Segment", "customers": "Customers", "value_at_risk_share": st.column_config.NumberColumn("Share of value at risk", format="percent"),
        "contacted": "Contacted (this plan)", "risk_only": "Contacted (risk-only)"})
    right.caption("Value at risk = sum of churn probability x customer value. Risk-only targeting spends the budget on high-risk, low-value customers; the expected-value rule moves part of it to high-value customers.")
    st.subheader("Top 10 customers to call first")
    top10 = target.loc[target.selected].nlargest(10, "expected_net_value")
    st.dataframe(top10[["customer_id", "churn_probability", "customer_value", "offer_id", "expected_net_value", "tenure_segment", "Contract"]], hide_index=True, width="stretch", column_config={
        "customer_id": "Customer", "churn_probability": st.column_config.NumberColumn("Churn probability", format="%.2f"),
        "customer_value": st.column_config.NumberColumn("Value (USD)", format="$%.0f"), "offer_id": "Offer",
        "expected_net_value": st.column_config.NumberColumn("Expected net value", format="$%.2f"), "tenure_segment": "Tenure", "Contract": "Contract"})
    st.caption("The full, exportable action list is on the Campaign builder page.")
    with st.expander("How the decision works"):
        st.markdown(f"""
- **Customer value** = monthly charges x contribution margin x discounted remaining months (base horizon x tenure factor).
- **Expected net value of an offer** = p(churn) x save rate x customer value - (offer cost + contact cost).
- The optimiser picks the set of customers (and, for segment offers, the offer for each) with the highest total expected value within the budget and the contact cap ({cfg['campaign']['max_contact_share']:.0%} of customers). Customers with non-positive expected value are never contacted, even if budget is left.
- **Save rate** is an assumption, not measured from data: the dataset has no randomised campaign, so no causal uplift is estimated. The pilot design (docs/pilot-design.md) shows how to measure it.
- Model, thresholds, strategy and budget recommendation were chosen on the validation split; the demo list is the untouched test split.""")

# ---- Campaign builder -------------------------------------------------------------------------------
if page == "Campaign builder":
    st.subheader("Same budget, different rules")
    rows = []
    for strategy in ["none", "risk", "risk_positive_ev", "value", "ev", "segment_offers"]:
        offers_s = strategy_offers(cfg, strategy)
        _, item = calculate(population, budget, cfg, offers_s, "ev" if strategy == "segment_offers" else strategy, thresholds)
        rows.append({"rule": STRATEGY_LABELS[strategy], **{k: item.get(k) for k in ["selected_count", "cost", "expected_net_value", "roi", "precision_contacted" if labelled else "expected_precision", "high_risk_high_value_coverage"]}})
    table = pd.DataFrame(rows).rename(columns={"expected_precision": "precision_contacted"})
    st.dataframe(table, hide_index=True, width="stretch", column_config={
        "rule": "Targeting rule", "selected_count": "Customers", "cost": st.column_config.NumberColumn("Cost", format="$%.0f"),
        "expected_net_value": st.column_config.NumberColumn("Expected net value", format="$%.0f"), "roi": st.column_config.NumberColumn("ROI", format="percent"),
        "precision_contacted": st.column_config.NumberColumn("Precision among contacted" + ("" if labelled else " (expected)"), format="percent"),
        "high_risk_high_value_coverage": st.column_config.NumberColumn("High-risk/high-value coverage", format="percent")})
    st.caption("All rules use the same customers, budget and assumptions. Risk and value rules ignore expected value; 'positive EV only' first drops customers with non-positive EV, then ranks by risk.")
    st.subheader("Action list")
    a, b = st.columns([2, 1])
    query = a.text_input("Search customer ID (filters the view only)")
    selected_only = b.checkbox("Contacted customers only", value=True)
    visible = target.loc[target.selected] if selected_only else target
    if query:
        visible = visible.loc[visible.customer_id.str.contains(query, case=False, regex=False)]
    st.dataframe(visible[["customer_id", "churn_probability", "tenure_segment", "Contract", "customer_value", "offer_id", "assumed_save_rate", "total_cost", "expected_net_value", "selected", "selection_reason"]],
                 hide_index=True, width="stretch", column_config={
        "customer_id": "Customer", "churn_probability": st.column_config.NumberColumn("Churn probability", format="%.3f"), "tenure_segment": "Tenure",
        "customer_value": st.column_config.NumberColumn("Value (USD)", format="$%.2f"), "offer_id": "Offer", "assumed_save_rate": st.column_config.NumberColumn("Save rate", format="percent"),
        "total_cost": st.column_config.NumberColumn("Cost", format="$%.2f"), "expected_net_value": st.column_config.NumberColumn("Expected net value", format="$%.2f"),
        "selected": "Contact", "selection_reason": "Reason"})
    if not visible.empty:
        with st.expander("Why is a customer in or out of the list?"):
            customer_id = st.selectbox("Customer", visible.customer_id.tolist())
            detail = visible.loc[visible.customer_id.eq(customer_id)].iloc[0]
            st.write(detail.selection_reason)
            st.write(detail.decision_detail)
            st.caption("This is the economic formula, not a cause of churn or proof that the offer works. With several offers the optimiser maximises total value within budget, so a customer's individually best offer is not always chosen.")
    st.download_button("Export campaign (CSV + assumptions)", campaign_zip(target, stats, cfg), f"campaign_{stats['scenario_id']}.zip", "application/zip", type="primary")

# ---- Scenarios & budget -----------------------------------------------------------------------------
if page == "Scenarios & budget":
    st.subheader("How robust is the plan?")
    st.caption("A frozen list keeps today's customers and offers when an assumption changes; a re-optimised list picks again within the same budget. Figures are scenarios, not confidence intervals.")
    if st.button("Run scenario analysis", type="primary"):
        with st.spinner("Computing tornado, scenarios, profit curve and grid..."):
            st.session_state.scenario_results = (scenario_bundle(population, budget, cfg, mode, thresholds), stats["scenario_id"])
    if "scenario_results" in st.session_state:
        results, sid = st.session_state.scenario_results
        if sid != stats["scenario_id"]:
            st.warning("Assumptions changed since this analysis. Run it again to refresh the charts.")
        options = offer_options(value_customers(population, cfg), [default_offer(cfg)])
        be = break_even(target, cfg, options)
        c1, c2, c3 = st.columns(3)
        c1.metric("Break-even save rate (this list)", pct(be.get("break_even_default_save_rate")), help="Standard-offer save rate at which the frozen list's expected net value is zero.")
        c2.metric("Break-even offer cost (this list)", usd(be.get("break_even_default_offer_cost"), 2), help="Standard-offer cost at which the frozen list breaks even.")
        c3.metric("Minimum viable save rate", pct(be.get("minimum_viable_save_rate")), help="Below this save rate no customer has positive expected value: the best decision is no campaign.")
        tor = results["tornado"].iloc[::-1]
        fig = go.Figure()
        base_net = tor.base_net.iloc[0]
        fig.add_bar(y=tor.label, x=tor.net_low_retarget - base_net, base=base_net, orientation="h", name="Low end of range", marker_color=ORANGE,
                    customdata=tor[["low"]], hovertemplate="%{y}<br>low %{customdata[0]}: $%{x:,.0f} vs base<extra></extra>")
        fig.add_bar(y=tor.label, x=tor.net_high_retarget - base_net, base=base_net, orientation="h", name="High end of range", marker_color=BLUE,
                    customdata=tor[["high"]], hovertemplate="%{y}<br>high %{customdata[0]}: $%{x:,.0f} vs base<extra></extra>")
        fig.add_vline(x=base_net, line_color=INK, line_width=1)
        fig.update_layout(barmode="overlay", title=f"Tornado: one assumption at a time (base {usd(base_net)})", xaxis_title="Expected net value, list re-optimised (USD)", height=380)
        st.plotly_chart(fig, width="stretch")
        scen = results["scenarios"].copy()
        st.dataframe(scen[["scenario", "selected_count", "cost", "expected_net_value", "roi", "fixed_expected_net_value"]], hide_index=True, width="stretch", column_config={
            "scenario": "Scenario", "selected_count": "Customers (re-optimised)", "cost": st.column_config.NumberColumn("Cost", format="$%.0f"),
            "expected_net_value": st.column_config.NumberColumn("Net value, re-optimised", format="$%.0f"), "roi": st.column_config.NumberColumn("ROI", format="percent"),
            "fixed_expected_net_value": st.column_config.NumberColumn("Net value, frozen list", format="$%.0f")})
        st.caption("Pessimistic / optimistic combine several register assumptions at once; see docs/assumption-register.md for the ranges and sources.")
        curve = results["curve"].copy()
        curve["rule"] = curve.strategy.map(STRATEGY_LABELS)
        current_share = budget / max(len(population) * (default_offer(cfg)["offer_cost"] + default_offer(cfg)["contact_cost"]), 1e-9)
        fig = px.line(curve, x="budget_share", y="expected_net_value", color="rule", markers=True, color_discrete_sequence=[BLUE, ORANGE],
                      title="Profit curve: expected net value by budget size", labels={"budget_share": "Budget as share of customers x standard offer cost", "expected_net_value": "Expected net value (USD)", "rule": ""})
        fig.add_vline(x=current_share, line_dash="dash", line_color=MUTED, annotation_text="current budget")
        fig.add_vline(x=decisions["budget_recommendation"]["recommended_share"], line_dash="dot", line_color=INK, annotation_text="recommended (validation, default assumptions)", annotation_position="bottom right")
        fig.update_layout(xaxis_tickformat=".0%")
        st.plotly_chart(fig, width="stretch")
        part = curve.loc[curve.strategy.eq(mode)]
        fig = px.bar(part, x="budget_share", y="marginal_roi", title="Marginal ROI of each budget step (stop adding budget when it falls below the hurdle)", color_discrete_sequence=[BLUE],
                     labels={"budget_share": "Budget share", "marginal_roi": "Marginal ROI"})
        fig.add_hline(y=cfg["campaign"]["recommendation"]["min_marginal_roi"], line_color=ORANGE, annotation_text="hurdle")
        fig.update_layout(xaxis_tickformat=".0%", yaxis_tickformat=".0%", height=300)
        st.plotly_chart(fig, width="stretch")
        sens = results["sensitivity"]
        view = st.radio("Grid view", ["retarget", "fixed"], format_func={"retarget": "Re-optimised list", "fixed": "Frozen list"}.get, horizontal=True, key="grid_view")
        grid = sens.query("axis == 'save_rate x offer_cost' and mode == @view").pivot(index="parameter", columns="cost_multiplier", values="expected_net_value")
        grid.index = [f"{v:.0%}" for v in grid.index]
        grid.columns = [f"{v:g}x" for v in grid.columns]
        heat = px.imshow(grid, text_auto=".0f", aspect="auto", color_continuous_scale=[[0, "#d03b3b"], [0.5, "#f0efec"], [1, BLUE]], color_continuous_midpoint=0, origin="lower",
                         title="Expected net value: save rate x offer cost multiplier (USD)", labels={"x": "Offer cost multiplier", "y": "Save rate", "color": "USD"})
        st.plotly_chart(heat, width="stretch")
        st.download_button("Download the full sensitivity table", sens.to_csv(index=False).encode("utf-8-sig"), f"sensitivity_{sid}.csv", "text/csv")
    else:
        st.caption("Press the button to compute the analysis for the current list and assumptions; results are cached per scenario.")
