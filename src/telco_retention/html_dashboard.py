"""Single-file HTML dashboard: the Streamlit dashboard's pages in one file that opens in any browser, offline.

The run's results (scores of the held-out test customers, model evidence, the deployed model's linear form) are
embedded as data; the decision engine (customer value, expected value, budget optimiser, rules, break-even,
scenarios) runs in the browser from templates/dashboard/engine.js, which mirrors business.py and analysis.py.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
import joblib
import pandas as pd
from .common import ROOT, latest_run, read_json
from .data import BINARY, DOMAINS, OPTIONAL, SCHEMA
from .templating import TEMPLATES

HTML_DASHBOARD = "reports/dashboard/retention-dashboard.html"
FOLDER = TEMPLATES / "dashboard"
# Customer columns the engine needs: scores, value inputs, eligibility rules and the profile of the list.
CUSTOMER_COLUMNS = ["customer_id", "churn_probability", "churn", "tenure", "MonthlyCharges", "Contract", "InternetService", "TechSupport", "PaymentMethod", "SeniorCitizen"]


def _clean(value):
    """JSON-safe: NaN and infinities become null, numpy scalars plain numbers."""
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _records(frame, columns=None):
    frame = frame if columns is None else frame[columns]
    return _clean(frame.astype(object).where(frame.notna(), None).to_dict("records"))


def model_terms(bundle):
    """The deployed logistic model as additive terms on raw inputs (scaling and sigmoid calibration folded in), or None."""
    from .modeling import _terms, deployed_linear
    if deployed_linear(bundle) is None:
        return None
    meta = bundle["metadata"]
    coef, intercept, means, scales = _terms(bundle)
    imputer = deployed_linear(bundle)[0].named_steps["prep"].named_transformers_["num"].named_steps["impute"]
    medians = dict(zip(meta["continuous_features"], imputer.statistics_))
    terms = []
    for name, c in coef.items():
        if name in meta["continuous_features"]:
            terms.append({"kind": "num", "column": name, "mean": means[name], "scale": scales[name], "median": medians[name], "coef": c})
        elif name in BINARY:
            terms.append({"kind": "flag", "column": name, "coef": c})
        else:
            column = next(col for col in meta["categorical_features"] if name.startswith(col + "_"))
            terms.append({"kind": "cat", "column": column, "level": name[len(column) + 1:], "coef": c})
    return _clean({"intercept": intercept, "terms": terms})


def dashboard_data(run=None):
    run = Path(run or latest_run())
    bundle = joblib.load(run / "model.joblib")
    meta = bundle["metadata"]
    cfg = meta["config"]
    scores = pd.read_csv(run / "scorecard.csv", dtype={"customer_id": str, "customerID": str, "SeniorCitizen": str}).query("split == 'test'")
    decisions = read_json(run / "validation_decisions.json")
    scorecard_meta = read_json(run / "scorecard_meta.json")
    csv = lambda name: pd.read_csv(run / name)  # noqa: E731
    splits = bundle.get("reference_splits") or {}
    return _clean({
        "run_id": run.name,
        "model_name": f"calibrated {meta['selected_model'].replace('_', ' ')}",
        "selected_model": meta["selected_model"],
        "config": {k: cfg[k] for k in ["seed", "currency", "value", "campaign", "offers", "sensitivity", "assumption_register"]},
        "thresholds": read_json(run / "targeting_thresholds.json"),
        "recommended_strategy": decisions["strategy_selection"]["strategy"],
        "budget_recommendation": decisions["budget_recommendation"],
        "customers": {c: scores[c].tolist() for c in CUSTOMER_COLUMNS},
        "model": {"linear": model_terms(bundle), "schema": SCHEMA, "optional": sorted(OPTIONAL), "domains": DOMAINS,
                  "reference_splits": {k: {"train": "t", "validation": "v", "test": "s"}[v] for k, v in splits.items()}},
        "template_csv": (ROOT / "data/examples/customers_unlabeled.csv").read_text(encoding="utf-8-sig"),
        "evidence": {
            "test_metrics": _records(csv("test_metrics.csv"), ["model", "average_precision", "roc_auc", "brier", "ece", "calibration_slope"]),
            "intervals": _records(csv("bootstrap_intervals.csv")),
            "calibration": _records(csv("calibration.csv")),
            "gains": _records(csv("gains_test.csv"), ["cumulative_customer_share", "cumulative_churner_capture", "lift"]),
            "odds_ratios": _records(csv("odds_ratios.csv"), ["variable", "comparison", "odds_ratio"]) if scorecard_meta.get("available") else [],
            "scorecard_meta": scorecard_meta,
            "scorecard_points": _records(csv("scorecard_points.csv"), ["characteristic", "attribute", "points"]),
            "scorecard_bands": _records(csv("scorecard_bands.csv"), ["band", "customers", "card_probability", "observed_churn"]),
            "shap_global": _records(csv("shap_global.csv").head(12)),
            "shap_local": _records(csv("shap_local.csv")),
            "profit_check": _records(csv("model_profit_check.csv"), ["population", "model", "selected_count", "expected_net_value", "label_based_net", "precision_contacted"]),
            "error_profiles": _records(csv("error_profiles.csv"), ["outcome", "customers", "mean_probability", "mean_tenure", "median_monthly_charges", "month_to_month_share", "fibre_share"]),
            "segment_errors": _records(csv("segment_errors.csv"), ["attribute", "group", "n", "average_precision", "roc_auc", "ece", "calibration_slope"]),
            "source": read_json(run / "dataset_source.json"),
            "quality": {k: v for k, v in read_json(run / "data_quality.json").items() if k in ["total_charges_filled_zero", "duplicates_removed", "joins"]},
            "reasons": read_json(run / "churn_reasons_summary.json"),
            "stress": _records(csv("stress_test.csv"), ["economy", "mean_probability", "positive_ev_customers", "positive_ev_share", "net_no_budget_limit", "pilot_per_arm"]),
        },
    })


def _script(text):
    """Text placed inside <script>: never close the element early."""
    return re.sub(r"</(script)", r"<\\/\1", text, flags=re.I)


def build_html_dashboard(run=None, out=None):
    """Write the single-file dashboard for a run; Plotly comes from the installed plotly package, so it works offline."""
    import plotly
    run = Path(run or latest_run())
    out = Path(out or ROOT / HTML_DASHBOARD)
    read = lambda path: path.read_text(encoding="utf-8").replace("\r\n", "\n")  # noqa: E731 - templates may be checked out with CRLF
    parts = {"PLOTLY": read(Path(plotly.__file__).parent / "package_data/plotly.min.js"),
             "DATA": json.dumps(dashboard_data(run), ensure_ascii=False, allow_nan=False, separators=(",", ":")),
             "ENGINE": read(FOLDER / "engine.js"), "APP": read(FOLDER / "app.js")}
    page = read(FOLDER / "dashboard.html")
    page = page.replace("<!--HEADER-->", f"<!-- Generated by src/telco_retention/html_dashboard.py for run {run.name}. Edit the templates in templates/dashboard, not this file. -->")
    # One pass, so text inside an inserted part is never mistaken for a placeholder.
    page = re.sub(r"/\*@(PLOTLY|DATA|ENGINE|APP)@\*/", lambda m: _script(parts[m[1]]), page)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8", newline="\n")
    return out
