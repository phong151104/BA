from __future__ import annotations

from copy import deepcopy
from itertools import product
import numpy as np
import pandas as pd
from .common import ROOT, config, latest_run, read_json, save_csv, write_json
from .business import SEGMENTS, campaign, fixed_campaign, value_customers
from .modeling import metrics


def default_budget(n, cfg=None):
    cfg = cfg or config()
    offer = cfg["offers"][1]
    return int(n * .1) * (offer["offer_cost"] + offer["contact_cost"])


def eda(run):
    train = pd.read_csv(run / "customers.csv").query("split == 'train'").copy()
    train["tenure_segment"] = pd.cut(train.tenure, [-np.inf, 12, 24, np.inf], labels=SEGMENTS)
    train["charges_band"] = pd.qcut(train.MonthlyCharges, 4, duplicates="drop").astype(str)
    rows = []
    for col in ["Contract", "tenure_segment", "charges_band", "InternetService", "PaymentMethod", "OnlineSecurity", "TechSupport"]:
        for group, part in train.groupby(col, observed=True):
            rows.append({"attribute": col, "group": group, "n": len(part), "churn_rate": part.churn.mean(), "mean_monthly_charges": part.MonthlyCharges.mean(), "mean_tenure": part.tenure.mean()})
    save_csv(pd.DataFrame(rows), run / "eda_segments.csv")
    save_csv(train[["tenure", "MonthlyCharges", "TotalCharges", "churn"]].corr().reset_index(names="feature"), run / "correlations.csv")
    save_csv(train.describe(include="all").reset_index(names="statistic"), run / "eda_descriptive.csv")


def sensitivity(scores, budget, cfg, thresholds=None):
    reference, _ = campaign(scores, budget, cfg, thresholds=thresholds)
    reference_ids = set(reference.loc[reference.selected, "customer_id"])
    cases = []
    for q, multiplier in product([.05, .10, .20, .30, .40, .50], [.5, .75, 1, 1.25, 1.5]):
        offer = {**cfg["offers"][1], "save_rate": q, "offer_cost": cfg["offers"][1]["offer_cost"] * multiplier}
        cases.append(("cost_save_rate", q, multiplier, deepcopy(cfg), offer))
    for margin in [.2, .3, .4]:
        setting = {**deepcopy(cfg), "margin": margin}
        cases.append(("margin", margin, 1, setting, cfg["offers"][1]))
    for horizon in [6, 12, 18]:
        setting = {**deepcopy(cfg), "base_horizon": horizon}
        cases.append(("horizon", horizon, 1, setting, cfg["offers"][1]))
    uniform = {**deepcopy(cfg), "tenure_factors": {s: 1 for s in SEGMENTS}}
    cases.append(("uniform_tenure", 1, 1, uniform, cfg["offers"][1]))
    rows = []
    for axis, param, cost_multiplier, settings, offer in cases:
        picked, retarget = campaign(scores, budget, settings, [offer], thresholds=thresholds)
        _, fixed = fixed_campaign(scores, reference, budget, settings, offer, thresholds)
        ids = set(picked.loc[picked.selected, "customer_id"])
        turnover = len(ids.symmetric_difference(reference_ids)) / len(ids.union(reference_ids)) if ids.union(reference_ids) else 0
        for mode, stats in [("fixed", fixed), ("retarget", retarget)]:
            rows.append({"axis": axis, "parameter": param, "cost_multiplier": cost_multiplier, "mode": mode,
                         "turnover": 0 if mode == "fixed" else turnover, "budget_feasible": stats["cost"] <= budget + 1e-7,
                         **{k: v for k, v in stats.items() if k not in ["solver", "scenario"]}})
    return pd.DataFrame(rows)


def budget_curve(scores, cfg, thresholds=None):
    maximum = len(scores) * max(o["offer_cost"] + o["contact_cost"] for o in cfg["offers"])
    rows = []
    for budget in np.linspace(0, maximum, 21):
        for strategy in ["risk", "value", "ev"]:
            _, stats = campaign(scores, float(budget), cfg, strategy=strategy, thresholds=thresholds)
            rows.append({"budget": budget, "strategy": strategy, **{k: v for k, v in stats.items() if k not in ["solver", "scenario"]}})
        _, stats = campaign(scores, float(budget), cfg, offers=cfg["offers"], thresholds=thresholds)
        rows.append({"budget": budget, "strategy": "multi_offer", **{k: v for k, v in stats.items() if k not in ["solver", "scenario"]}, "solver_status": stats["solver"]["status"]})
    return pd.DataFrame(rows)


def compare(scores, budget, cfg, thresholds=None, random_iterations=100):
    rows, detail, scenarios = [], {}, {}
    for strategy in ["none", "risk", "value", "ev", "multi_offer"]:
        offers = cfg["offers"] if strategy == "multi_offer" else [cfg["offers"][1]]
        target, summary = campaign(scores, budget, cfg, offers, "ev" if strategy == "multi_offer" else strategy, thresholds=thresholds)
        detail[strategy] = target
        scenarios[strategy] = summary
        rows.append({"strategy": strategy, **{k: v for k, v in summary.items() if k not in ["solver", "scenario"]}, "solver_status": summary["solver"]["status"]})
    random_rows = []
    for seed in range(cfg["seed"], cfg["seed"] + random_iterations):
        _, summary = campaign(scores, budget, cfg, strategy="random", thresholds=thresholds, seed=seed)
        random_rows.append({k: v for k, v in summary.items() if k not in ["solver", "scenario", "scenario_id"]})
    random_frame = pd.DataFrame(random_rows)
    rows.append({"strategy": "random_mean", **random_frame.mean(numeric_only=True).to_dict(), "solver_status": "100 seeded random campaigns" if random_iterations == 100 else "seeded random campaigns"})
    return pd.DataFrame(rows), detail, scenarios, random_frame


def simulate(run=None):
    run = run or latest_run()
    cfg = read_json(run / "manifest.json")["config"]
    scores = pd.read_csv(run / "scorecard.csv")
    validation, test = scores.query("split == 'validation'"), scores.query("split == 'test'")
    values = value_customers(validation, cfg)
    thresholds = {"risk": float(values.churn_probability.quantile(.75)), "value": float(values.customer_value.quantile(.75))}
    write_json(run / "targeting_thresholds.json", thresholds)
    budget = default_budget(len(test), cfg)
    print("Simulating comparable campaigns", flush=True)
    comparison, details, scenarios, random_results = compare(test, budget, cfg, thresholds, cfg["random_campaign_iterations"])
    save_csv(random_results, run / "random_campaigns.csv")
    for name, detail in details.items():
        save_csv(detail, run / f"targeting_{name}.csv")
    write_json(run / "campaign_scenarios.json", scenarios)
    policy_rows = []
    print("Selecting tenure policy on validation only (27 alternatives)", flush=True)
    for ids in product([o["offer_id"] for o in cfg["offers"]], repeat=3):
        policy = dict(zip(SEGMENTS, ids))
        _, stats = campaign(validation, default_budget(len(validation), cfg), cfg, cfg["offers"], policy=policy, thresholds=thresholds)
        policy_rows.append({**policy, "expected_net_value": stats["expected_net_value"], "cost": stats["cost"], "solver_status": stats["solver"]["status"]})
    policy_frame = pd.DataFrame(policy_rows).sort_values(["expected_net_value", *SEGMENTS], ascending=[False, True, True, True])
    policy = policy_frame.iloc[0][SEGMENTS].to_dict()
    save_csv(policy_frame, run / "validation_policy_search.csv")
    write_json(run / "segment_policy.json", {"policy": policy, "chosen_on": "validation", "validation_budget": default_budget(len(validation), cfg)})
    policy_table, policy_stats = campaign(test, budget, cfg, cfg["offers"], policy=policy, thresholds=thresholds)
    save_csv(policy_table, run / "targeting_segment_policy.csv")
    write_json(run / "segment_policy_test.json", policy_stats)
    comparison = pd.concat([comparison, pd.DataFrame([{"strategy": "segment_policy", **{k: v for k, v in policy_stats.items() if k not in ["solver", "scenario"]}, "solver_status": policy_stats["solver"]["status"]}])], ignore_index=True)
    save_csv(comparison, run / "strategy_comparison.csv")
    print("Sensitivity and profit curves", flush=True)
    save_csv(sensitivity(test, budget, cfg, thresholds), run / "sensitivity.csv")
    save_csv(budget_curve(test, cfg, thresholds), run / "budget_curve.csv")
    fairness = []
    threshold = read_json(run / "manifest.json")["threshold"]
    for strategy, targeted in {"ev": details["ev"], "segment_policy": policy_table}.items():
        for col in ["gender", "SeniorCitizen", "tenure_segment"]:
            for group, part in targeted.groupby(col):
                fairness.append({"strategy": strategy, "attribute": col, "group": group, "n": len(part), "small_sample": len(part) < 50,
                                 "selection_rate": part.selected.mean(), "mean_probability": part.churn_probability.mean(), "observed_churn": part.churn.mean(),
                                 "calibration_gap": part.churn_probability.mean() - part.churn.mean(), **metrics(part.churn, part.churn_probability, threshold)})
    save_csv(pd.DataFrame(fairness), run / "fairness.csv")
    save_csv(pd.DataFrame(cfg["offers"]), run / "synthetic_offers.csv")
    eda(run)
    write_json(run / "simulation_manifest.json", {"run_id": run.name, "budget": budget, "thresholds": thresholds, "config": cfg, "population": "test", "assumptions_not_estimated": True})
    return run
