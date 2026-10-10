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
from telco_retention.analysis import (QUADRANTS, break_even, campaign_budget, draw_assumptions, profit_curve, quadrant, reprice_frozen,
                                      scenario_table, sensitivity, strategy_offers, tornado)

BLUE, ORANGE, AQUA, GREY, INK, MUTED, RED = "#2a78d6", "#eb6834", "#1baf7a", "#b9b8b2", "#0b0b0b", "#898781", "#d03b3b"
PAGES = ["Decision", "Assumptions & sensitivity", "Model evidence"]
MODES = {"ev": "Single standard offer", "segment_offers": "Segment-specific offers"}
KPI_LABELS = ["Expected net value", "ROI", "Customers contacted", "Precision among contacted", "High-risk/high-value coverage"]
LIVE_DRAWS = 2000

st.set_page_config(page_title="Retention Lab", page_icon="◈", layout="wide")
st.markdown("""<style>
.stApp {background:#f9f9f7;} .block-container {padding-top:3.2rem; max-width:1480px;}
h1,h2,h3 {color:#0b0b0b;} [data-testid="stMetric"] {background:#fcfcfb;border:1px solid rgba(11,11,11,.10);border-radius:12px;padding:14px 16px;}
[data-testid="stSidebar"] {background:#f1f0ec;}
[data-testid="stMetricLabel"] * {white-space:normal !important; overflow:visible !important; text-overflow:clip !important;}
.strip {background:#fcfcfb;border:1px solid rgba(11,11,11,.10);border-radius:10px;padding:8px 14px;margin:2px 0 14px;font-size:13px;color:#52514e;line-height:1.6;}
.strip b {color:#0b0b0b;font-weight:600;}
.hero h2 {margin:0 0 4px;} .hero p {color:#52514e;margin:0 0 10px;font-size:15px;}
[data-testid="stToolbar"] {display:none;}
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


@st.cache_data(show_spinner=False)
def live_monte_carlo(target, settings, seed):
    """All register assumptions drawn at once around the current values; the current list is frozen."""
    return reprice_frozen(target, settings, draw_assumptions(settings, LIVE_DRAWS, seed))


def control(key, default):
    # Native persistence keeps Python state and remounted browser widgets in sync across pages.
    st.session_state.campaign_controls.setdefault(key, default)
    if key not in st.session_state:
        st.session_state[key] = default
    return {"key": key, "persist_state": "session"}


def usd(x, digits=0):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else (f"-${abs(x):,.{digits}f}" if x < 0 else f"${x:,.{digits}f}")


def md(text):
    """Escape dollar signs so Streamlit markdown does not render money as LaTeX."""
    return text.replace("$", r"\$")


def pct(x, digits=1):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{digits}%}"


def metric_cards(stats, baseline, labelled):
    delta = stats["expected_net_value"] - baseline["expected_net_value"]
    precision = stats["precision_contacted"] if labelled else stats["expected_precision"]
    values = [usd(stats["expected_net_value"]), pct(stats["roi"]), f"{stats['selected_count']:,}", pct(precision), pct(stats.get("high_risk_high_value_coverage"))]
    deltas = [f"{usd(delta)} vs risk-only", None, f"{usd(stats['cost'])} spent", None if labelled else "expected (no labels)",
              f"risk-only: {pct(baseline.get('high_risk_high_value_coverage'))}"]
    helps = ["Sum of p(churn) x save rate x customer value - offer and contact cost, for the contacted list. Delta: same budget spent on the highest-risk customers.",
             "Expected net value / campaign cost.", "Customers who receive an offer within the budget and contact cap.",
             "Share of contacted customers who actually churned (labelled data) or their mean predicted churn probability (unlabelled).",
             "Share of high-risk and high-value customers (validation 75th percentiles) that the list reaches."]
    for col, label, value, d, h in zip(st.columns(5), KPI_LABELS, values, deltas, helps):
        net = label == "Expected net value"
        col.metric(label, value, d, help=h, delta_color="normal" if net else "off", delta_arrow="auto" if net else "off")


def strip(cfg, budget, n, mode, offers):
    offer = default_offer(cfg)
    v = cfg["value"]
    factors = "/".join(f"{v['tenure_factors'][s]:g}" for s in SEGMENTS)
    extra = f" · {len(offers)} offers in catalog" if mode == "segment_offers" else ""
    st.markdown(f"""<div class="strip"><b>Assumptions</b> · Budget <b>{usd(budget)}</b> for {n:,} customers · Offer <b>{offer['label']}</b>:
    {usd(offer['offer_cost'])} + {usd(offer['contact_cost'])} contact, save rate <b>{offer['save_rate']:.0%}</b>{extra} · Margin <b>{v['margin']:.0%}</b> ·
    Value horizon <b>{v['base_horizon_months']:g} months</b> (x{factors} by tenure) · Discount <b>{v['discount_rate_annual']:.0%}/yr</b></div>""", unsafe_allow_html=True)


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
model_name = f"calibrated {bundle['metadata']['selected_model'].replace('_', ' ')}"
st.sidebar.caption(f"{len(scores):,} customers · model: {model_name}")
st.sidebar.markdown("---")
st.sidebar.caption("Money figures are expected values under the visible assumptions (USD of the sample company), not realised profit or measured uplift.")

# ---- Page headers ---------------------------------------------------------------------------------------
if page == "Decision":
    st.markdown("<div class='hero'><h2>Which customers should get a retention offer?</h2><p>Spend a fixed budget where churn risk and customer value together return the most - and know when not to spend.</p></div>", unsafe_allow_html=True)
elif page == "Assumptions & sensitivity":
    st.markdown("<div class='hero'><h2>What if the assumptions are wrong?</h2><p>Every number the decision rests on is set here. The list, KPIs and risk of a loss update at once.</p></div>", unsafe_allow_html=True)
else:
    st.markdown("<div class='hero'><h2>Can we trust the scores?</h2><p>How well the deployed model ranks and calibrates, what drives it, and where the data come from.</p></div>", unsafe_allow_html=True)

# ---- Assumptions: one set of controls shared by every page; each page draws the ones it needs -------------
cfg = deepcopy(bundle["metadata"]["config"])
standard = default_offer(cfg)
recommended = decisions["strategy_selection"]["strategy"]
offer_labels = {o["offer_id"]: o["label"] for o in cfg["offers"]}
show_main = page in ["Decision", "Assumptions & sensitivity"]
show_all = page == "Assumptions & sensitivity"


def widget(kind, column, label, key, default, **kwargs):
    if column is None:
        st.session_state.campaign_controls.setdefault(key, default)
        return st.session_state.get(key, default)
    return getattr(column, kind)(label, **kwargs, **control(key, default))


cols = st.columns(4) if show_main else [None] * 4
budget = widget("number_input", cols[0], "Budget (USD)", "budget_" + ("demo" if source == sources[0] else "upload"), float(campaign_budget(len(scores), cfg)), min_value=0.0, step=100.0)
mode = widget("selectbox", cols[1], "Offer policy", "offer_mode", recommended, options=list(MODES), format_func=MODES.get)
if not show_all:
    cols = [None] * 4
standard["save_rate"] = widget("slider", cols[2], "Save rate of the standard offer", "save_rate", float(standard["save_rate"]), min_value=0.0, max_value=1.0, step=0.01)
standard["offer_cost"] = widget("number_input", cols[3], "Standard offer cost (USD)", "offer_cost", float(standard["offer_cost"]), min_value=0.0, step=1.0)
cols = st.columns(4) if show_all else [None] * 4
contact = widget("number_input", cols[0], "Contact cost per customer (USD)", "contact_cost", float(standard["contact_cost"]), min_value=0.0, step=0.5)
cfg["value"]["margin"] = widget("slider", cols[1], "Contribution margin", "margin", float(cfg["value"]["margin"]), min_value=0.0, max_value=1.0, step=0.01)
cfg["value"]["base_horizon_months"] = widget("number_input", cols[2], "Value horizon (months)", "horizon", float(cfg["value"]["base_horizon_months"]), min_value=0.0, step=1.0)
cfg["value"]["discount_rate_annual"] = widget("slider", cols[3], "Annual discount rate", "discount", float(cfg["value"]["discount_rate_annual"]), min_value=0.0, max_value=0.5, step=0.01)
cols = st.columns(4) if show_all else [None] * 4
for column, segment, label in zip(cols, SEGMENTS, ["Horizon factor: new (<=12 months)", "Horizon factor: developing (13-24)", "Horizon factor: loyal (>24)"]):
    cfg["value"]["tenure_factors"][segment] = widget("number_input", column, label, "tenure_" + segment, float(cfg["value"]["tenure_factors"][segment]), min_value=0.0, step=0.05)
segments = widget("multiselect", st.columns([2, 2])[0] if show_all else None, "Eligible tenure segments", "eligible_segments", list(SEGMENTS), options=list(SEGMENTS))
for offer in cfg["offers"]:
    offer["contact_cost"] = contact
if mode == "segment_offers":
    if show_all:
        st.caption("Segment-specific offers: each customer can only receive offers whose eligibility rule they meet; the optimiser picks the best mix within budget.")
    for offer in cfg["offers"]:
        if offer["offer_id"] == standard["offer_id"]:
            continue
        cols = st.columns([2, 1, 1]) if show_all else [None] * 3
        if show_all:
            rule = "; ".join(f"{k}: {', '.join(map(str, v))}" for k, v in offer.get("eligibility", {}).items()) or "all customers"
            cols[0].markdown(f"**{offer['label']}**  \n<span style='color:#52514e;font-size:13px'>Eligible: {rule}</span>", unsafe_allow_html=True)
        offer["offer_cost"] = widget("number_input", cols[1], f"Cost (USD): {offer['label']}", "cost_" + offer["offer_id"], float(offer["offer_cost"]), min_value=0.0, step=1.0)
        offer["save_rate"] = widget("slider", cols[2], f"Save rate: {offer['label']}", "rate_" + offer["offer_id"], float(offer["save_rate"]), min_value=0.0, max_value=1.0, step=0.01)

# ---- Model evidence (no campaign is computed on this page) -------------------------------------------------
if page == "Model evidence":
    metrics = artifact(run.name, "test_metrics.csv").set_index("model")
    intervals = artifact(run.name, "bootstrap_intervals.csv").set_index("metric")
    chosen = bundle["metadata"]["selected_model"] + "_calibrated"
    performance, drivers, errors, data_tab = st.tabs(["Performance", "Drivers and scorecard", "Errors and money check", "Data and new customers"])
    with performance:
        st.subheader(f"Deployed model: {model_name}")
        st.caption("Chosen on the validation split by a rule fixed in advance (best average precision within 0.01, Brier within 0.002, prefer the simpler model). Metrics are on the untouched test split.")
        row = metrics.loc[chosen]
        for col, (key, label) in zip(st.columns(5), [("roc_auc", "ROC-AUC"), ("average_precision", "PR-AUC (average precision)"), ("brier", "Brier score"), ("ece", "Expected calibration error"), ("calibration_slope", "Calibration slope")]):
            ci = f"95% interval {intervals.loc[key, 'lower_95']:.3f}-{intervals.loc[key, 'upper_95']:.3f}" if key in intervals.index else None
            col.metric(label, f"{row[key]:.3f}", ci, delta_color="off", delta_arrow="off")
        a, b = st.columns(2)
        calibration = artifact(run.name, "calibration.csv")
        names = {chosen: f"Deployed ({model_name})", "xgboost_calibrated": "Challenger (calibrated XGBoost)"}
        calibration = calibration.loc[calibration.model.isin(names)].replace(names)
        fig = px.line(calibration, x="predicted", y="observed", color="model", markers=True, title="Calibration on the test split",
                      labels={"predicted": "Predicted churn probability", "observed": "Observed churn rate", "model": ""}, color_discrete_sequence=[BLUE, ORANGE])
        fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", name="Perfect calibration", line={"color": GREY, "width": 1})
        a.plotly_chart(fig, width="stretch")
        gains = artifact(run.name, "gains_test.csv")
        fig = go.Figure([go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Random contact", line={"color": GREY, "width": 1}),
                         go.Scatter(x=np.r_[0, gains.cumulative_customer_share], y=np.r_[0, gains.cumulative_churner_capture], mode="lines+markers", name="By predicted risk", line={"color": BLUE})])
        fig.update_layout(title=f"Cumulative gains (riskiest tenth: {gains.lift.iloc[0]:.1f}x the average churn rate)", xaxis_title="Share of customers contacted",
                          yaxis_title="Share of churners reached", xaxis_tickformat=".0%", yaxis_tickformat=".0%")
        b.plotly_chart(fig, width="stretch")
        table = metrics.reset_index()[["model", "average_precision", "roc_auc", "brier", "ece", "calibration_slope"]].round(3)
        st.dataframe(table, hide_index=True, width="stretch", column_config={"model": "Candidate (test split)", "average_precision": "PR-AUC", "roc_auc": "ROC-AUC",
                                                                             "brier": "Brier", "ece": "ECE", "calibration_slope": "Calibration slope"})
    with drivers:
        ratios = artifact(run.name, "odds_ratios.csv") if read_json(run / "scorecard_meta.json").get("available") else pd.DataFrame()
        if len(ratios):
            picks = pd.concat([ratios.nlargest(7, "odds_ratio"), ratios.nsmallest(5, "odds_ratio")]).drop_duplicates().sort_values("odds_ratio")
            picks["name"] = picks.variable + ": " + picks.comparison
            picks["direction"] = np.where(picks.odds_ratio > 1, "Higher churn odds", "Lower churn odds")
            fig = px.scatter(picks, x="odds_ratio", y="name", color="direction", log_x=True, color_discrete_map={"Higher churn odds": ORANGE, "Lower churn odds": BLUE},
                             title="What moves the deployed model's churn odds (associations, not causes)", labels={"odds_ratio": "Odds ratio (log scale)", "name": "", "direction": ""})
            fig.add_vline(x=1, line_color=MUTED, line_width=1)
            fig.update_traces(marker={"size": 11})
            st.plotly_chart(fig, width="stretch")
            st.caption("Categories are compared with their lowest-churn level, flags with not having the service, tenure per 12 months and charges per $10 a month.")
            meta = read_json(run / "scorecard_meta.json")
            st.subheader("Points scorecard for the call centre")
            st.markdown(md(f"Start at **{meta['base_points']} points** and add the points of each attribute. {meta['anchor_score']} points = 50% churn probability; every {meta['pdo']} points doubles the odds. "
                           f"On test the card stays within {meta['mean_abs_probability_gap'] * 100:.1f} percentage points of the model on average."))
            a, b = st.columns([1.2, 1])
            a.dataframe(artifact(run.name, "scorecard_points.csv")[["characteristic", "attribute", "points"]], hide_index=True, width="stretch", height=420,
                        column_config={"characteristic": "Characteristic", "attribute": "Attribute", "points": "Points"})
            bands = artifact(run.name, "scorecard_bands.csv")
            b.dataframe(bands[["band", "customers", "card_probability", "observed_churn"]], hide_index=True, width="stretch", column_config={
                "band": "Points", "customers": "Customers", "card_probability": st.column_config.NumberColumn("Card probability", format="percent"),
                "observed_churn": st.column_config.NumberColumn("Observed churn", format="percent")})
        st.subheader("Challenger: XGBoost (not deployed) - SHAP attribution")
        st.caption("TreeSHAP on 200 validation customers, log-odds scale. It explains the raw XGBoost challenger, not the deployed model, and it is not causal.")
        shap = artifact(run.name, "shap_global.csv").head(12).sort_values("mean_abs_shap")
        st.plotly_chart(px.bar(shap, x="mean_abs_shap", y="feature", orientation="h", title="Average size of each feature's contribution", color_discrete_sequence=[GREY],
                               labels={"mean_abs_shap": "Mean |SHAP| (log-odds)", "feature": ""}), width="stretch")
        local = artifact(run.name, "shap_local.csv")
        customer = st.selectbox("Explain one validation customer (challenger model)", local.sort_values("raw_probability", ascending=False).customer_id.tolist(), key="shap_customer")
        row = local.loc[local.customer_id.eq(customer)].iloc[0]
        contributions = row.drop(["customer_id", "base_value", "raw_probability"]).astype(float)
        top = contributions.abs().nlargest(10).index
        local_frame = pd.DataFrame({"feature": top, "SHAP": contributions[top].values})
        local_frame["effect"] = np.where(local_frame.SHAP > 0, "Raises churn risk", "Lowers churn risk")
        st.plotly_chart(px.bar(local_frame.iloc[::-1], x="SHAP", y="feature", orientation="h", color="effect", color_discrete_map={"Raises churn risk": ORANGE, "Lowers churn risk": BLUE},
                               title=f"{customer}: challenger probability {row.raw_probability:.1%}", labels={"SHAP": "Contribution (log-odds)", "feature": "", "effect": ""}), width="stretch")
    with errors:
        st.subheader("Model choice checked in money")
        profit = artifact(run.name, "model_profit_check.csv")
        st.dataframe(profit[["population", "model", "selected_count", "expected_net_value", "label_based_net", "precision_contacted"]], hide_index=True, width="stretch", column_config={
            "population": "Population", "model": "Candidate (calibrated)", "selected_count": "Contacted", "expected_net_value": st.column_config.NumberColumn("Expected net", format="dollar"),
            "label_based_net": st.column_config.NumberColumn("Net with actual churn", format="dollar"), "precision_contacted": st.column_config.NumberColumn("Precision", format="percent")})
        st.caption("Each candidate picks customers for the same budget and standard offer. The choice was made on validation; test is reported only.")
        st.subheader("Who the model gets wrong")
        profiles = artifact(run.name, "error_profiles.csv")
        st.dataframe(profiles[["outcome", "customers", "mean_probability", "mean_tenure", "median_monthly_charges", "month_to_month_share", "fibre_share"]], hide_index=True, width="stretch", column_config={
            "outcome": "Outcome (test, model threshold)", "customers": "Customers", "mean_probability": st.column_config.NumberColumn("Mean probability", format="percent"),
            "mean_tenure": st.column_config.NumberColumn("Mean tenure (months)", format="%.1f"), "median_monthly_charges": st.column_config.NumberColumn("Median bill", format="dollar"),
            "month_to_month_share": st.column_config.NumberColumn("Month-to-month", format="percent"), "fibre_share": st.column_config.NumberColumn("Fibre", format="percent")})
        st.subheader("Performance by segment")
        segment_errors = artifact(run.name, "segment_errors.csv")
        st.dataframe(segment_errors[["attribute", "group", "n", "average_precision", "roc_auc", "ece", "calibration_slope"]].round(3), hide_index=True, width="stretch", column_config={
            "attribute": "Segment", "group": "Group", "n": "Customers", "average_precision": "PR-AUC", "roc_auc": "ROC-AUC", "ece": "ECE", "calibration_slope": "Calibration slope"})
    with data_tab:
        st.subheader("Data source and quality")
        source_info, quality = artifact(run.name, "dataset_source.json"), artifact(run.name, "data_quality.json")
        st.markdown(md(f"IBM Telco Customer Churn sample, downloaded from [{source_info['source']}]({source_info['dataset_page']}) on {source_info['downloaded_at_utc'][:10]}; "
                       f"{source_info['rows']:,} customers. {quality['total_charges_filled_zero']} blank TotalCharges for new customers (tenure 0) set to 0; "
                       f"{quality['duplicates_removed']} duplicate rows. Split 60/20/20 train/validation/test, stratified, seed {cfg['seed']}. Join: {quality['joins']}."))
        reasons = artifact(run.name, "churn_reasons_summary.json")
        share = pd.DataFrame({"category": list(reasons["category_share"]), "All churners": list(reasons["category_share"].values()),
                              "Churners on the recommended list": [reasons["category_share_on_list"].get(c, 0) for c in reasons["category_share"]]})
        fig = px.bar(share.melt("category", var_name="group", value_name="share"), x="share", y="category", color="group", barmode="group", orientation="h",
                     color_discrete_map={"All churners": GREY, "Churners on the recommended list": BLUE},
                     title=f"Why churners left: only {reasons['addressable_share']:.0%} for price or a competitor's offer", labels={"share": "Share of churners", "category": "", "group": ""})
        fig.update_layout(xaxis_tickformat=".0%", yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width="stretch")
        st.caption("Reasons come from IBM's extended sample of the same customers and are recorded after customers left, so they are descriptive, never model inputs.")
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

# ---- Campaign for the current list and assumptions --------------------------------------------------------
population = scores.loc[tenure_segment(scores.tenure).astype(str).isin(segments)].copy()
if population.empty:
    st.info("No customers in the selected tenure segments.")
    st.stop()
offers = strategy_offers(cfg, mode)
start = time.perf_counter()
with st.spinner("Optimising the campaign..."):
    target, stats = calculate(population, budget, cfg, offers, "ev", thresholds)
    baseline_table, baseline = calculate(population, budget, cfg, [default_offer(cfg)], "risk", thresholds)
compute_seconds = time.perf_counter() - start
strip(cfg, budget, len(population), mode, offers)
if stats["selected_count"] == 0:
    st.info("Nobody is selected: no customer has positive expected value under these assumptions, or the budget is below one offer. Not running the campaign is the right decision here.")

# ---- Decision ---------------------------------------------------------------------------------------------
if page == "Decision":
    metric_cards(stats, baseline, labelled)
    options = offer_options(value_customers(population, cfg), [default_offer(cfg)])
    be = break_even(target, cfg, options)
    if stats["selected_count"]:
        st.success(md(f"**Recommended action:** offer **{stats['selected_count']:,} customers** a retention offer for **{usd(stats['cost'])}**. Expected net value **{usd(stats['expected_net_value'])}** "
                      f"(ROI {pct(stats['roi'], 0)}), **{usd(stats['expected_net_value'] - baseline['expected_net_value'])} more** than spending the same budget on the highest-risk customers. "
                      f"The list pays off only if the offer keeps at least **{pct(be.get('break_even_default_save_rate'))}** of would-be churners, so test it in a pilot before scaling."))

    st.subheader("Who gets an offer, and who does not")
    picked, rest = target.loc[target.selected], target.loc[~target.selected]
    traits = [("Fibre internet", lambda d: d.InternetService.eq("Fiber optic")), ("Month-to-month contract", lambda d: d.Contract.eq("Month-to-month")),
              ("Pays by electronic check", lambda d: d.PaymentMethod.eq("Electronic check")), ("Tenure 12 months or less", lambda d: d.tenure_segment.astype(str).eq("new"))]
    if "SeniorCitizen" in target:
        traits.append(("Senior", lambda d: d.SeniorCitizen.astype(str).eq("1")))
    profile = pd.DataFrame([{"Customers who...": name, "On the list": pct(f(picked).mean(), 0) if len(picked) else "n/a", "Not contacted": pct(f(rest).mean(), 0), "All": pct(f(target).mean(), 0)}
                            for name, f in traits]
                           + [{"Customers who...": "Median monthly bill", "On the list": usd(picked.MonthlyCharges.median()) if len(picked) else "n/a",
                               "Not contacted": usd(rest.MonthlyCharges.median()), "All": usd(target.MonthlyCharges.median())}])
    left, right = st.columns([1, 1.25])
    left.dataframe(profile, hide_index=True, width="stretch")
    target["quadrant"] = quadrant(target, thresholds)
    target["risk_selected"] = target.customer_id.map(baseline_table.set_index("customer_id").selected).fillna(False)
    target["value_at_risk"] = target.churn_probability * target.customer_value
    matrix = target.groupby("quadrant", observed=False).agg(customers=("customer_id", "size"), value_at_risk=("value_at_risk", "sum"),
                                                            contacted=("selected", "sum"), risk_only=("risk_selected", "sum")).reindex(QUADRANTS).reset_index()
    matrix["value_at_risk_share"] = matrix.value_at_risk / matrix.value_at_risk.sum()
    right.dataframe(matrix[["quadrant", "customers", "value_at_risk_share", "contacted", "risk_only"]], hide_index=True, width="stretch", column_config={
        "quadrant": st.column_config.TextColumn("Segment (validation cut-offs)", width="medium"), "customers": "Customers",
        "value_at_risk_share": st.column_config.NumberColumn("Value at risk", format="percent", help="Share of churn probability x customer value"),
        "contacted": st.column_config.NumberColumn("This plan"), "risk_only": st.column_config.NumberColumn("Risk-only")})
    st.caption("Low-risk customers get no offer: most would stay anyway. High-risk, low-value customers get few: their remaining value rarely repays an offer, which is where risk-only targeting spends its budget.")
    chart = target.assign(decision=np.where(target.selected, "Gets an offer", "No offer"))
    fig = px.scatter(chart, x="churn_probability", y="customer_value", color="decision", color_discrete_map={"Gets an offer": BLUE, "No offer": GREY}, opacity=.75,
                     hover_data={"customer_id": True, "tenure_segment": True, "expected_net_value": ":.2f", "offer_id": True}, title="Risk x value: who gets an offer",
                     labels={"churn_probability": "Predicted churn probability", "customer_value": "Customer value proxy (USD)", "decision": ""})
    fig.add_vline(x=thresholds["risk"], line_dash="dash", line_color=MUTED, line_width=1, annotation_text="high risk", annotation_position="top right")
    fig.add_hline(y=thresholds["value"], line_dash="dash", line_color=MUTED, line_width=1, annotation_text="high value", annotation_position="bottom right")
    st.plotly_chart(fig, width="stretch")

    with st.expander("Compare targeting rules at the same budget"):
        rows = []
        for strategy in ["none", "risk", "risk_positive_ev", "value", "ev", "segment_offers"]:
            _, item = calculate(population, budget, cfg, strategy_offers(cfg, strategy), "ev" if strategy == "segment_offers" else strategy, thresholds)
            precision = item.get("precision_contacted" if labelled else "expected_precision")
            rows.append({"Targeting rule": STRATEGY_LABELS[strategy], "Customers": f"{item['selected_count']:,}", "Cost": usd(item["cost"]), "Expected net value": usd(item["expected_net_value"]),
                         "ROI": pct(item.get("roi"), 0), "Precision among contacted" + ("" if labelled else " (expected)"): pct(precision, 0),
                         "High-risk/high-value coverage": pct(item.get("high_risk_high_value_coverage"), 0)})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption("Same customers, budget and assumptions. Risk and value rules ignore expected value; 'positive EV only' drops customers with non-positive EV, then ranks by risk.")

    st.subheader("Action list")
    a, b = st.columns([2, 1])
    query = a.text_input("Search customer ID (filters the view only)", key="search")
    selected_only = b.checkbox("Customers who get an offer only", value=True, key="selected_only")
    visible = target.loc[target.selected] if selected_only else target
    if query:
        visible = visible.loc[visible.customer_id.str.contains(query, case=False, regex=False)]
    view = visible.assign(offer=visible.offer_id.map(offer_labels).fillna(visible.offer_id))
    st.dataframe(view[["customer_id", "churn_probability", "customer_value", "offer", "total_cost", "expected_net_value", "selection_reason"]], hide_index=True, width="stretch", column_config={
        "customer_id": "Customer", "churn_probability": st.column_config.NumberColumn("Churn probability", format="percent"),
        "customer_value": st.column_config.NumberColumn("Value", format="dollar"), "offer": st.column_config.TextColumn("Offer", width="large"),
        "total_cost": st.column_config.NumberColumn("Cost", format="dollar"), "expected_net_value": st.column_config.NumberColumn("Expected net value", format="dollar"),
        "selection_reason": st.column_config.TextColumn("Why", width="medium")})
    if not visible.empty:
        with st.expander("Why is a customer in or out of the list?"):
            customer_id = st.selectbox("Customer", visible.customer_id.tolist(), key="explain_customer")
            detail = visible.loc[visible.customer_id.eq(customer_id)].iloc[0]
            st.write(detail.selection_reason)
            st.write(md(detail.decision_detail))
            st.caption("This is the economic formula, not a cause of churn or proof that the offer works. With several offers the optimiser maximises total value within budget, so a customer's individually best offer is not always chosen.")
    st.download_button("Export campaign (CSV + assumptions)", campaign_zip(target, stats, cfg), f"campaign_{stats['scenario_id']}.zip", "application/zip", type="primary")
    with st.expander("Technical details"):
        st.markdown(md(f"Run `{run.name}` · scenario ID `{stats['scenario_id']}` (also in the export) · model: {model_name} · solver: {stats['solver']['status']}"
                       f"{'' if stats['solver'].get('gap') in [None, 0, 0.0] else ' (gap ' + str(stats['solver']['gap']) + ')'} · computed in {compute_seconds:.2f}s · "
                       f"budget used {usd(stats['cost'])} of {usd(budget)} · expected customers saved {stats['expected_saved']:.1f}"))
        if stats["solver"]["status"] in ["feasible_time_limit", "heuristic_fallback"]:
            st.warning(f"Global optimality not proven. Solver gap: {stats['solver']['gap']}")

# ---- Assumptions & sensitivity ------------------------------------------------------------------------------
if page == "Assumptions & sensitivity":
    options = offer_options(value_customers(population, cfg), [default_offer(cfg)])
    be = break_even(target, cfg, options)
    nets = live_monte_carlo(target, cfg, int(cfg["seed"])) if stats["selected_count"] else np.zeros(LIVE_DRAWS)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Expected net value", usd(stats["expected_net_value"]), f"{stats['selected_count']:,} customers contacted", delta_color="off", delta_arrow="off")
    c2.metric("Break-even save rate (this list)", pct(be.get("break_even_default_save_rate")), help="Standard-offer save rate at which this frozen list's expected net value is zero.")
    c3.metric("Chance this list loses money", pct(float((nets < 0).mean()), 0), help=f"{LIVE_DRAWS:,} draws: every register assumption drawn at once from a triangular distribution over its tested range, centred on the values set above.")
    c4.metric("Minimum viable save rate", pct(be.get("minimum_viable_save_rate")), help="Below this save rate no customer has positive expected value: the best decision is no campaign.")
    if stats["selected_count"]:
        fig = px.histogram(pd.DataFrame({"net": nets}), x="net", nbins=60, color_discrete_sequence=[BLUE], title="Net value of this list when every assumption is uncertain",
                           labels={"net": "Expected net value of the frozen list (USD)"})
        fig.add_vline(x=0, line_color=RED, line_width=1, annotation_text="loss", annotation_position="top left")
        fig.update_layout(yaxis_title="Draws", height=320, bargap=0.05)
        st.plotly_chart(fig, width="stretch")

    st.subheader("Scenarios and budget size")
    st.caption("A frozen list keeps today's customers and offers when an assumption changes; a re-optimised list picks again within the same budget. These are scenarios, not confidence intervals.")
    if st.button("Run scenario analysis", type="primary"):
        with st.spinner("Computing tornado, scenarios, profit curve and grid..."):
            st.session_state.scenario_results = (scenario_bundle(population, budget, cfg, mode, thresholds), stats["scenario_id"])
    if "scenario_results" in st.session_state:
        results, sid = st.session_state.scenario_results
        if sid != stats["scenario_id"]:
            st.warning("Assumptions changed since this analysis. Run it again to refresh the charts.")
        tor = results["tornado"].iloc[::-1]
        fig = go.Figure()
        base_net = tor.base_net.iloc[0]
        fig.add_bar(y=tor.label, x=tor.net_low_retarget - base_net, base=base_net, orientation="h", name="Low end of range", marker_color=ORANGE,
                    customdata=tor[["low"]], hovertemplate="%{y}<br>low %{customdata[0]}: $%{x:,.0f} vs base<extra></extra>")
        fig.add_bar(y=tor.label, x=tor.net_high_retarget - base_net, base=base_net, orientation="h", name="High end of range", marker_color=BLUE,
                    customdata=tor[["high"]], hovertemplate="%{y}<br>high %{customdata[0]}: $%{x:,.0f} vs base<extra></extra>")
        fig.add_vline(x=base_net, line_color=INK, line_width=1)
        fig.update_layout(barmode="overlay", title=f"Tornado: one assumption at a time (base {usd(base_net)})", xaxis_title="Expected net value, list re-optimised (USD)", height=400)
        st.plotly_chart(fig, width="stretch")
        scen = results["scenarios"].copy()
        st.dataframe(pd.DataFrame({"Scenario": scen.scenario.str.capitalize(), "Customers (re-optimised)": scen.selected_count.map("{:,.0f}".format),
                                   "Net value, re-optimised": scen.expected_net_value.map(usd), "ROI": scen.roi.map(lambda v: pct(v, 0)),
                                   "Net value, frozen list": scen.fixed_expected_net_value.map(usd)}), hide_index=True, width="stretch")
        st.caption("Pessimistic and optimistic combine several register assumptions at once; see docs/assumption-register.md for the ranges and sources.")
        curve = results["curve"].copy()
        curve["rule"] = curve.strategy.map(STRATEGY_LABELS)
        current_share = budget / max(len(population) * (default_offer(cfg)["offer_cost"] + default_offer(cfg)["contact_cost"]), 1e-9)
        fig = px.line(curve, x="budget_share", y="expected_net_value", color="rule", markers=True,
                      color_discrete_map={STRATEGY_LABELS["ev"]: BLUE, STRATEGY_LABELS["risk"]: ORANGE, STRATEGY_LABELS["segment_offers"]: AQUA},
                      title="Profit curve: expected net value by budget size", labels={"budget_share": "Budget, as the share of customers the standard offer could reach", "expected_net_value": "Expected net value (USD)", "rule": ""})
        fig.add_vline(x=current_share, line_dash="dash", line_color=MUTED, annotation_text="current budget")
        fig.add_vline(x=decisions["budget_recommendation"]["recommended_share"], line_dash="dot", line_color=INK, annotation_text="recommended", annotation_position="bottom right")
        fig.update_layout(xaxis_tickformat=".0%")
        st.plotly_chart(fig, width="stretch")
        part = curve.loc[curve.strategy.eq(mode)]
        fig = px.bar(part, x="budget_share", y="marginal_roi", title="Return on each extra budget step (stop when it falls below the hurdle)", color_discrete_sequence=[BLUE],
                     labels={"budget_share": "Budget share", "marginal_roi": "Marginal ROI"})
        fig.add_hline(y=cfg["campaign"]["recommendation"]["min_marginal_roi"], line_color=ORANGE, annotation_text="hurdle")
        fig.update_layout(xaxis_tickformat=".0%", yaxis_tickformat=".0%", height=300)
        st.plotly_chart(fig, width="stretch")
        sens = results["sensitivity"]
        grid_view = st.radio("Grid view", ["retarget", "fixed"], format_func={"retarget": "Re-optimised list", "fixed": "Frozen list"}.get, horizontal=True, key="grid_view")
        grid = sens.query("axis == 'save_rate x offer_cost' and mode == @grid_view").pivot(index="parameter", columns="cost_multiplier", values="expected_net_value")
        grid.index = [f"{v:.0%}" for v in grid.index]
        grid.columns = [f"{v:g}x" for v in grid.columns]
        heat = px.imshow(grid, text_auto=".0f", aspect="auto", color_continuous_scale=[[0, RED], [0.5, "#f0efec"], [1, BLUE]], color_continuous_midpoint=0, origin="lower",
                         title="Expected net value: save rate x offer cost multiplier (USD)", labels={"x": "Offer cost multiplier", "y": "Save rate", "color": "USD"})
        st.plotly_chart(heat, width="stretch")
        st.download_button("Download the full sensitivity table", sens.to_csv(index=False).encode("utf-8-sig"), f"sensitivity_{sid}.csv", "text/csv")
    else:
        st.caption("Press the button to compute the analysis for the current list and assumptions; results are cached per scenario.")

    st.subheader("Outside the sample: lower churn and Vietnamese prices")
    stress = artifact(run.name, "stress_test.csv")
    st.dataframe(pd.DataFrame({"Prices": stress.economy, "Average churn": stress.mean_probability.map(lambda v: pct(v, 0)),
                               "Customers worth an offer": stress.positive_ev_customers.map("{:,.0f}".format), "Share": stress.positive_ev_share.map(lambda v: pct(v, 0)),
                               "Expected net (USD)": stress.net_no_budget_limit.map(usd), "Pilot customers per arm": stress.pilot_per_arm.map(lambda v: "n/a" if pd.isna(v) else f"{v:,.0f}")}),
                 hide_index=True, width="stretch")
    st.caption("From the pipeline, at the registered assumptions: probabilities shifted to lower average churn with the ranking unchanged; 'Vietnam-like' scales bills and offers to a home-fibre bill and contacts by SMS. See the analysis report.")
