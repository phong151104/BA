"""Load a run's artifacts once and derive every number the documents quote."""
from __future__ import annotations

import json
import numpy as np
import pandas as pd
from .common import ROOT, read_json, write_json
from .business import STRATEGY_LABELS, annuity_months, default_offer
from .data import DOMAINS, NUMERIC, SCHEMA

MODEL_LABELS = {"logistic": "Logistic Regression", "random_forest": "Random Forest", "xgboost": "XGBoost (gradient boosting)", "dummy": "Prior-only baseline"}
QUADRANT_KEYS = {"High risk / High value": "hrhv", "High risk / Low value": "hrlv", "Low risk / High value": "lrhv", "Low risk / Low value": "lrlv"}
SHORT_NAMES = {"save_rate": "save rate", "offer_cost_multiplier": "offer cost", "contact_cost": "contact cost", "value.margin": "margin",
               "value.base_horizon_months": "value horizon", "value.discount_rate_annual": "discount rate"}


def records(frame):
    clean = frame.astype(object).where(pd.notna(frame), None)
    return [{k: (v.item() if isinstance(v, np.generic) else v) for k, v in row.items()} for row in clean.to_dict("records")]


def param_text(value, unit):
    """Assumption value in its register unit, e.g. 10%, x1.25, $8, 9 months."""
    value = float(value)
    if unit == "share":
        return f"{value:.0%}" if abs(value * 100 - round(value * 100)) < 1e-9 else f"{value:.1%}"
    if unit == "USD":
        return f"${value:,.0f}" if value.is_integer() else f"${value:,.2f}"
    if unit == "x":
        return f"x{value:g}"
    return f"{value:g} months" if unit == "months" else f"{value:g}"


def describe_overrides(overrides, units):
    items = json.loads(overrides) if isinstance(overrides, str) else overrides
    return ", ".join(f"{SHORT_NAMES.get(k, k)} {param_text(v, units.get(k))}" for k, v in items.items()) or "assumptions as registered"


def by_key(frame, key):
    return {row[key]: row for row in records(frame)}


def build_facts(run):
    run = ROOT / "artifacts/runs" / run.name
    csv = lambda name: pd.read_csv(run / name)
    rel = lambda name: str((run / name).relative_to(ROOT)).replace("\\", "/")
    manifest = read_json(run / "manifest.json")
    cfg = manifest["config"]
    offer = default_offer(cfg)
    source, metadata, quality = read_json(run / "dataset_source.json"), read_json(run / "dataset_metadata.json"), read_json(run / "data_quality.json")
    customers = csv("customers.csv")
    decisions = read_json(run / "validation_decisions.json")
    strategy = decisions["strategy_selection"]["strategy"]
    comparison = by_key(csv("strategy_comparison.csv"), "strategy")
    for key, row in comparison.items():
        row["label"] = STRATEGY_LABELS.get(key, key)
    n_test = int(manifest["split_counts"]["test"])
    budget = read_json(run / "simulation_manifest.json")["budget"]
    chosen, risk, ev = comparison[strategy], comparison["risk"], comparison["ev"]
    uncertainty = by_key(csv("economic_uncertainty.csv"), "strategy")
    recommended = read_json(run / "recommended_campaign.json")
    recommendation = decisions["budget_recommendation"]
    base_population = cfg["pilot"]["base_population"]
    scale = base_population / n_test

    curve = csv("budget_curve.csv")
    test_curve = curve.query("population == 'test'")
    sens = csv("sensitivity.csv")
    grid = sens.query("axis == 'save_rate x offer_cost'")
    tornado = csv("tornado.csv")
    scenarios = by_key(csv("scenarios.csv"), "scenario")
    matrix = csv("risk_value_matrix.csv")
    matrix_rows = records(matrix)
    for row in matrix_rows:
        row["key"] = QUADRANT_KEYS[row["quadrant"]]
    fairness = csv("fairness.csv")
    pilot, power = read_json(run / "pilot_plan.json"), records(csv("pilot_power.csv"))
    units = {item["parameter"]: item["unit"] for item in cfg["assumption_register"]}
    tornado_rows = records(tornado)
    for row in tornado_rows:
        row["low_text"], row["high_text"], row["base_text"] = (param_text(row[k], row["unit"]) for k in ["low", "high", "base"])
    for row in scenarios.values():
        row["overrides_text"] = describe_overrides(row["overrides"], units)

    test_metrics = csv("test_metrics.csv")
    selected_model = manifest["selected_model"]
    selected_row = test_metrics.loc[test_metrics.model.eq(selected_model + "_calibrated")].iloc[0]
    intervals = by_key(csv("bootstrap_intervals.csv"), "metric")
    coefficients = csv("logistic_coefficients.csv").assign(odds_ratio=lambda d: np.exp(d.coefficient))
    eda = csv("eda_segments.csv")
    eda_groups = {attribute: records(part.sort_values("churn_rate", ascending=False)) for attribute, part in eda.groupby("attribute")}
    train = customers.query("split == 'train'")

    facts = {
        "run": {"id": run.name, "created_at": manifest["created_at"], "python": manifest["python"], "source_sha256": manifest["source_sha256"]},
        "cfg": cfg, "currency": cfg["currency"], "default_offer": offer,
        "data": {"rows": int(source["rows"]), "columns": len(source["columns"]), "source": source, "metadata": metadata, "quality": quality,
                 "churn_rate": float(customers.churn.mean()), "churners": int(customers.churn.sum()), "splits": manifest["split_counts"],
                 "train_churn_rate": float(train.churn.mean()), "mean_monthly_charges": float(customers.MonthlyCharges.mean()),
                 "median_tenure": float(customers.tenure.median())},
        "eda": eda_groups,
        "model": {"selected": selected_model, "label": MODEL_LABELS[selected_model], "threshold": manifest["threshold"], "selection_rule": manifest["selection_rule"],
                  "features": manifest["feature_columns"], "best_parameters": manifest["best_parameters"],
                  "validation": records(csv("validation_metrics.csv")), "test": records(test_metrics),
                  "selected_test": {k: (None if pd.isna(v) else v) for k, v in selected_row.to_dict().items()}, "intervals": intervals,
                  "gains": records(csv("gains_test.csv")), "precision_at_k": records(csv("precision_at_k.csv")),
                  "top_positive": records(coefficients.nlargest(6, "coefficient")), "top_negative": records(coefficients.nsmallest(6, "coefficient")),
                  "shap_top": records(csv("shap_global.csv").head(8)), "segment_errors": records(csv("segment_errors.csv"))},
        "thresholds": read_json(run / "targeting_thresholds.json"),
        "decisions": decisions, "strategy": strategy, "strategy_label": STRATEGY_LABELS[strategy],
        "budget": {"base": budget, "share": cfg["campaign"]["budget_share"], "n_test": n_test, "per_customer": offer["offer_cost"] + offer["contact_cost"],
                   "per_base_customer": budget / n_test, "recommended_per_base_customer": recommended["budget"] / n_test},
        "comparison": comparison,
        "headline": {"chosen": chosen, "risk": risk, "ev": ev,
                     "delta_vs_risk": chosen["expected_net_value"] - risk["expected_net_value"],
                     "delta_vs_risk_pct": (chosen["expected_net_value"] - risk["expected_net_value"]) / abs(risk["expected_net_value"]) if risk["expected_net_value"] else None,
                     "targeting_effect": ev["expected_net_value"] - risk["expected_net_value"],
                     "offer_design_effect": comparison["segment_offers"]["expected_net_value"] - ev["expected_net_value"]},
        "uncertainty": uncertainty,
        "recommendation": recommendation,
        "recommended": recommended,
        "scaled": {"factor": scale, "base_population": base_population,
                   "recommended_customers": recommended["selected_count"] * scale, "recommended_budget": recommended["cost"] * scale,
                   "recommended_net": recommended["expected_net_value"] * scale,
                   "base_customers": chosen["selected_count"] * scale, "base_budget": chosen["cost"] * scale, "base_net": chosen["expected_net_value"] * scale},
        "curve": {"test": records(test_curve), "validation": records(curve.query("population == 'validation'")),
                  "positive_ev_customers": int(test_curve.query("strategy == @strategy").selected_count.max()),
                  "positive_ev_share": float(test_curve.query("strategy == @strategy").selected_count.max() / n_test),
                  "positive_ev_cost": float(test_curve.query("strategy == @strategy").cost.max())},
        "break_even": read_json(run / "break_even.json"),
        "tornado": tornado_rows, "scenarios": scenarios,
        "sensitivity": {"retarget_min": float(grid.query("mode == 'retarget'").expected_net_value.min()), "retarget_max": float(grid.query("mode == 'retarget'").expected_net_value.max()),
                        "fixed_min": float(grid.query("mode == 'fixed'").expected_net_value.min()), "fixed_max": float(grid.query("mode == 'fixed'").expected_net_value.max()),
                        "rows": len(sens)},
        "matrix": matrix_rows, "quadrant": {row["key"]: row for row in matrix_rows},
        "threshold_rules": records(csv("threshold_business.csv")),
        "fairness": records(fairness), "fairness_flags": records(fairness.query("review_flag and strategy == @strategy")),
        "fairness_by": {f"{r['strategy']}|{r['attribute']}|{r['group']}": r for r in records(fairness)},
        "pilot": {**pilot, "cost_per_contact": recommended["cost"] / recommended["selected_count"] if recommended["selected_count"] else None,
                  "wave_cost": pilot["arm_size_per_wave"] * (recommended["cost"] / recommended["selected_count"]) if recommended["selected_count"] else None,
                  "required_per_arm_at_base": next((r["customers_per_arm"] for r in power if abs(r["assumed_save_rate"] - offer["save_rate"]) < 1e-9), None),
                  "at_assumed": next((r for r in power if abs(r["assumed_save_rate"] - offer["save_rate"]) < 1e-9), None),
                  "at_break_even": next((r for r in power if r["is_break_even"]), None)},
        "pilot_power": power,
        "schema": [{"field": c, "domain": "; ".join(DOMAINS[c]) if c in DOMAINS else ("non-negative number" if c in NUMERIC else "unique, non-empty text"),
                    "role": "target" if c == "Churn" else "audit only" if c in ["gender", "SeniorCitizen"] else "key" if c == "customerID" else "feature"} for c in SCHEMA],
        "offers": records(csv("offer_catalog.csv")), "offer_mix": records(csv("segment_offer_mix.csv")),
        "register": cfg["assumption_register"],
        "figures": {item["file"].removesuffix(".png"): item for item in read_json(ROOT / "reports/figures/catalog.json")} if (ROOT / "reports/figures/catalog.json").exists() else {},
    }
    months = float(annuity_months(cfg["value"]["base_horizon_months"] * cfg["value"]["tenure_factors"]["developing"], cfg["value"]["discount_rate_annual"]))
    value = 70.0 * cfg["value"]["margin"] * months
    cost = offer["offer_cost"] + offer["contact_cost"]
    facts["worked_example"] = {"monthly_charges": 70.0, "tenure": 20, "p": 0.6, "discounted_months": months, "value": value,
                               "ev": 0.6 * offer["save_rate"] * value - cost, "cost": cost, "min_value": cost / (0.6 * offer["save_rate"])}
    facts["sources"] = {
        "comparison": rel("strategy_comparison.csv"), "uncertainty": rel("economic_uncertainty.csv"), "recommendation": rel("validation_decisions.json"),
        "recommended": rel("recommended_campaign.json"), "curve": rel("budget_curve.csv"), "break_even": rel("break_even.json"), "tornado": rel("tornado.csv"),
        "scenarios": rel("scenarios.csv"), "sensitivity": rel("sensitivity.csv"), "matrix": rel("risk_value_matrix.csv"), "threshold_rules": rel("threshold_business.csv"),
        "fairness": rel("fairness.csv"), "pilot": rel("pilot_plan.json"), "pilot_power": rel("pilot_power.csv"), "model.test": rel("test_metrics.csv"),
        "model.validation": rel("validation_metrics.csv"), "model.intervals": rel("bootstrap_intervals.csv"), "model.gains": rel("gains_test.csv"),
        "eda": rel("eda_segments.csv"), "data.quality": rel("data_quality.json"), "data.source": rel("dataset_source.json"), "cfg": rel("manifest.json"),
        "offers": rel("offer_catalog.csv"), "offer_mix": rel("segment_offer_mix.csv"),
    }
    return facts


def write_facts(facts, path=None):
    path = path or ROOT / "reports/facts.json"
    write_json(path, {k: v for k, v in facts.items() if k != "figures"})
    return path
