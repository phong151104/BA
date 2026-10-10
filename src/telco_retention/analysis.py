from __future__ import annotations

from copy import deepcopy
from itertools import product
import json
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.stats import norm
from .common import config, get_param, latest_run, read_json, save_csv, set_param, write_json
from .business import campaign, default_offer, fixed_campaign, value_customers
from .data import tenure_segment

COMPARED = ["none", "risk", "risk_positive_ev", "value", "ev", "segment_offers"]
QUADRANTS = ["High risk / High value", "High risk / Low value", "Low risk / High value", "Low risk / Low value"]


def campaign_budget(n, cfg=None, share=None):
    """Budget that funds the default offer for `share` of `n` customers (config budget_share by default)."""
    cfg = cfg or config()
    share = cfg["campaign"]["budget_share"] if share is None else share
    offer = default_offer(cfg)
    return int(np.floor(share * n + 1e-9)) * (offer["offer_cost"] + offer["contact_cost"])


def strategy_offers(cfg, strategy):
    return deepcopy(cfg["offers"]) if strategy == "segment_offers" else [deepcopy(default_offer(cfg))]


def run_strategy(scores, budget, cfg, strategy, thresholds=None, seed=None):
    rule = "ev" if strategy == "segment_offers" else strategy
    return campaign(scores, budget, cfg, strategy_offers(cfg, strategy), rule, thresholds, seed)


def flat(stats):
    return {**{k: v for k, v in stats.items() if k not in ["solver", "scenario"]}, "solver_status": stats.get("solver", {}).get("status")}


def apply_overrides(cfg, overrides):
    """Scenario keys: `save_rate` (default offer level; other offers move by the same points),
    `offer_cost_multiplier` and `contact_cost` (all offers), or any dotted config path."""
    out = deepcopy(cfg)
    for key, value in overrides.items():
        if key == "save_rate":
            shift = value - default_offer(cfg)["save_rate"]
            for offer in out["offers"]:
                offer["save_rate"] = float(np.clip(offer["save_rate"] + shift, 0, 1))
        elif key == "offer_cost_multiplier":
            for offer, base in zip(out["offers"], cfg["offers"]):
                offer["offer_cost"] = base["offer_cost"] * value
        elif key == "contact_cost":
            for offer in out["offers"]:
                offer["contact_cost"] = float(value)
        else:
            out = set_param(out, key, value)
    return out


def base_value(cfg, key):
    if key == "save_rate":
        return default_offer(cfg)["save_rate"]
    if key == "offer_cost_multiplier":
        return 1.0
    if key == "contact_cost":
        return default_offer(cfg)["contact_cost"]
    return get_param(cfg, key)


def risk_value_thresholds(validation, cfg):
    values = value_customers(validation, cfg)
    seg = cfg["segments"]
    return {"risk": float(values.churn_probability.quantile(seg["high_risk_quantile"])),
            "value": float(values.customer_value.quantile(seg["high_value_quantile"])), "fitted_on": "validation"}


def quadrant(frame, thresholds):
    high_risk = frame.churn_probability.ge(thresholds["risk"])
    high_value = frame.customer_value.ge(thresholds["value"])
    return pd.Categorical(np.select([high_risk & high_value, high_risk, high_value], QUADRANTS[:3], QUADRANTS[3]), QUADRANTS, ordered=True)


def risk_value_matrix(details, thresholds, strategies=("risk", "ev", "segment_offers")):
    base = details["ev"].copy()
    base["quadrant"] = quadrant(base, thresholds)
    rows = []
    total_var = float((base.churn_probability * base.customer_value).sum())
    for name, part in base.groupby("quadrant", observed=False):
        var = float((part.churn_probability * part.customer_value).sum())
        row = {"quadrant": name, "customers": len(part), "customer_share": len(part) / len(base),
               "observed_churn": part.churn.mean() if "churn" in part and len(part) else None,
               "mean_probability": part.churn_probability.mean() if len(part) else None,
               "mean_customer_value": part.customer_value.mean() if len(part) else None,
               "value_at_risk": var, "value_at_risk_share": var / total_var if total_var else None}
        for strategy in strategies:
            if strategy in details:
                chosen = details[strategy].set_index("customer_id").selected.reindex(part.customer_id).fillna(False)
                row[f"selected_{strategy}"] = int(chosen.sum())
        rows.append(row)
    return pd.DataFrame(rows)


def threshold_business(scores, cfg, threshold, budget):
    """Contrast a fixed probability cut-off with the EV rule on the same customers (no budget, then budget)."""
    customers = value_customers(scores, cfg)
    offer = default_offer(cfg)
    q, cost = offer["save_rate"], offer["offer_cost"] + offer["contact_cost"]
    ev = customers.churn_probability * q * customers.customer_value - cost
    rules = {f"Probability >= {threshold:.2f} (F1 threshold)": customers.churn_probability.ge(threshold),
             "Expected value > 0 (no budget limit)": ev.gt(0)}
    _, within = campaign(scores, budget, cfg)
    rows = []
    for name, mask in rules.items():
        picked = customers.loc[mask]
        rows.append({"rule": name, "customers": int(mask.sum()), "cost": float(mask.sum() * cost), "expected_net_value": float(ev[mask].sum()),
                     "precision": float(picked.churn.mean()) if "churn" in picked and len(picked) else None,
                     "recall": float(picked.churn.sum() / customers.churn.sum()) if "churn" in customers and customers.churn.sum() else None})
    rows.append({"rule": "Expected value, ranked within the fixed budget", "customers": within["selected_count"], "cost": within["cost"],
                 "expected_net_value": within["expected_net_value"], "precision": within["precision_contacted"],
                 "recall": None})
    p_star = (cost / (q * customers.customer_value)).replace(np.inf, np.nan)
    quantiles = {f"p{int(k * 100)}": float(p_star.quantile(k)) for k in [0.1, 0.25, 0.5, 0.75, 0.9]}
    return pd.DataFrame(rows), quantiles


def break_even(target, cfg, population_options=None):
    """Break-even assumptions for a frozen list; with no list, the save rate below which nobody is worth contacting."""
    picked = target.loc[target.selected]
    out = {"selected_count": len(picked)}
    if len(picked):
        pqv = float((picked.churn_probability * picked.assumed_save_rate * picked.customer_value).sum())
        cost, offer_cost, contact = float(picked.total_cost.sum()), float(picked.offer_cost.sum()), float(picked.contact_cost.sum())
        multiplier = cost / pqv if pqv > 0 else None
        out.update({"save_rate_multiplier": multiplier,
                    "break_even_default_save_rate": default_offer(cfg)["save_rate"] * multiplier if multiplier is not None else None,
                    "offer_cost_multiplier": (pqv - contact) / offer_cost if offer_cost > 0 else None,
                    "break_even_default_offer_cost": default_offer(cfg)["offer_cost"] * (pqv - contact) / offer_cost if offer_cost > 0 else None})
    if population_options is not None:
        out["minimum_viable_save_rate"] = float(population_options.break_even_save_rate.min())
    return out


def tornado(scores, budget, cfg, strategy, thresholds=None):
    reference, base = run_strategy(scores, budget, cfg, strategy, thresholds)
    rows = []
    for item in cfg["assumption_register"]:
        row = {k: item[k] for k in ["id", "parameter", "label", "unit", "low", "high"]}
        row["base"] = base_value(cfg, item["parameter"])
        for end in ["low", "high"]:
            changed = apply_overrides(cfg, {item["parameter"]: item[end]})
            _, retarget = run_strategy(scores, budget, changed, strategy, thresholds)
            _, frozen = fixed_campaign(scores, reference, budget, changed, strategy_offers(changed, strategy), thresholds)
            row[f"net_{end}_retarget"], row[f"net_{end}_fixed"] = retarget["expected_net_value"], frozen["expected_net_value"]
        row["base_net"] = base["expected_net_value"]
        row["swing_retarget"] = abs(row["net_high_retarget"] - row["net_low_retarget"])
        rows.append(row)
    return pd.DataFrame(rows).sort_values("swing_retarget", ascending=False).reset_index(drop=True)


def scenario_table(scores, budget, cfg, strategy, thresholds=None):
    reference, _ = run_strategy(scores, budget, cfg, strategy, thresholds)
    rows = []
    for name, overrides in cfg["sensitivity"]["scenarios"].items():
        changed = apply_overrides(cfg, overrides)
        _, retarget = run_strategy(scores, budget, changed, strategy, thresholds)
        _, frozen = fixed_campaign(scores, reference, budget, changed, strategy_offers(changed, strategy), thresholds)
        rows.append({"scenario": name, "overrides": json.dumps(overrides), **{k: retarget[k] for k in ["selected_count", "cost", "expected_net_value", "roi", "expected_saved"]},
                     "fixed_expected_net_value": frozen["expected_net_value"], "fixed_roi": frozen["roi"]})
    return pd.DataFrame(rows)


def sensitivity(scores, budget, cfg, strategy="ev", thresholds=None):
    """Save rate x offer cost grid plus one-way axes, each as a frozen list (fixed) and re-optimised (retarget)."""
    grids = cfg["sensitivity"]
    reference, reference_stats = run_strategy(scores, budget, cfg, strategy, thresholds)
    reference_ids = set(reference.loc[reference.selected, "customer_id"])
    cases = [("save_rate x offer_cost", q, m, {"save_rate": q, "offer_cost_multiplier": m}) for q, m in product(grids["save_rate"], grids["offer_cost_multiplier"])]
    for axis in ["contact_cost", "value.margin", "value.base_horizon_months", "value.discount_rate_annual"]:
        cases += [(axis, v, 1.0, {axis: v}) for v in grids[axis]]
    rows = []
    for axis, param, multiplier, overrides in cases:
        changed = apply_overrides(cfg, overrides)
        picked, retarget = run_strategy(scores, budget, changed, strategy, thresholds)
        _, frozen = fixed_campaign(scores, reference, budget, changed, strategy_offers(changed, strategy), thresholds)
        ids = set(picked.loc[picked.selected, "customer_id"])
        union = ids | reference_ids
        turnover = len(ids ^ reference_ids) / len(union) if union else 0.0
        for mode, stats in [("fixed", frozen), ("retarget", retarget)]:
            rows.append({"axis": axis, "parameter": param, "cost_multiplier": multiplier, "mode": mode, "strategy": strategy,
                         "reference_scenario_id": reference_stats["scenario_id"], "turnover": 0.0 if mode == "fixed" else turnover,
                         "budget_feasible": stats["cost"] <= budget + 1e-7, **flat(stats)})
    return pd.DataFrame(rows)


def share_grid(cfg):
    grid = cfg["campaign"]["recommendation"]["share_grid"]
    return np.round(np.arange(grid["start"], grid["stop"] + grid["step"] / 2, grid["step"]), 6)


def profit_curve(scores, cfg, strategies, thresholds=None, shares=None, population="test"):
    shares = share_grid(cfg) if shares is None else shares
    rows = []
    for share, strategy in product(shares, strategies):
        budget = campaign_budget(len(scores), cfg, share)
        _, stats = run_strategy(scores, budget, cfg, strategy, thresholds)
        rows.append({"population": population, "budget_share": float(share), "budget": budget, "strategy": strategy, **flat(stats)})
    curve = pd.DataFrame(rows).sort_values(["strategy", "budget_share"]).reset_index(drop=True)
    step_net = curve.groupby("strategy").expected_net_value.diff()
    step_cost = curve.groupby("strategy").cost.diff()
    curve["marginal_net"] = step_net
    curve["marginal_cost"] = step_cost
    curve["marginal_roi"] = np.where(step_cost > 1e-9, step_net / step_cost.where(step_cost > 1e-9), np.nan)
    return curve


def recommend_budget(curve, cfg, strategy):
    """Largest budget share whose last step still earns the hurdle marginal ROI (chosen on validation)."""
    hurdle = cfg["campaign"]["recommendation"]["min_marginal_roi"]
    part = curve.loc[curve.strategy.eq(strategy)].sort_values("budget_share")
    passing = part.loc[part.marginal_roi.ge(hurdle)]
    best = part.loc[part.expected_net_value.idxmax()]
    chosen = passing.iloc[-1] if len(passing) else part.iloc[0]
    return {"strategy": strategy, "population": str(chosen.population), "hurdle_marginal_roi": hurdle,
            "recommended_share": float(chosen.budget_share), "recommended_budget": float(chosen.budget),
            "expected_net_value": float(chosen.expected_net_value), "roi": chosen.roi, "marginal_roi": chosen.marginal_roi,
            "net_maximising_share": float(best.budget_share), "net_maximising_value": float(best.expected_net_value)}


def select_strategy(validation, budget, cfg, thresholds):
    rule = cfg["campaign"]["strategy_selection"]
    stats = {s: flat(run_strategy(validation, budget, cfg, s, thresholds)[1]) for s in rule["candidates"]}
    base, catalog = stats["ev"]["expected_net_value"], stats.get("segment_offers", {}).get("expected_net_value", -np.inf)
    chosen = "segment_offers" if base > 0 and catalog >= base * (1 + rule["min_relative_gain"]) else "ev"
    return {"strategy": chosen, "rule": f"segment_offers only if it beats ev by >= {rule['min_relative_gain']:.0%} on validation",
            "relative_gain": (catalog - base) / base if base > 0 else None, "validation_budget": budget, "validation": stats}


def compare(scores, budget, cfg, thresholds=None, random_iterations=100):
    rows, detail, scenarios = [], {}, {}
    for strategy in COMPARED:
        target, summary = run_strategy(scores, budget, cfg, strategy, thresholds)
        detail[strategy], scenarios[strategy] = target, summary
        rows.append({"strategy": strategy, **flat(summary)})
    random_rows = [flat(run_strategy(scores, budget, cfg, "random", thresholds, seed)[1]) for seed in range(cfg["seed"], cfg["seed"] + random_iterations)]
    random_frame = pd.DataFrame(random_rows).drop(columns=["scenario_id", "solver_status"])
    rows.append({"strategy": "random_mean", **random_frame.mean(numeric_only=True).to_dict(), "solver_status": f"mean of {random_iterations} seeded random campaigns"})
    return pd.DataFrame(rows), detail, scenarios, random_frame


def economic_uncertainty(details, iterations=1000, seed=42, pairs=(("ev", "risk"), ("ev", "risk_positive_ev"), ("segment_offers", "ev"))):
    """Paired customer bootstrap of frozen lists using historical labels; not a confidence bound on real profit."""
    reference = details["ev"].sort_values("customer_id")
    if "churn" not in reference:
        return pd.DataFrame()
    rng = np.random.default_rng(seed)
    contributions = {}
    for strategy, frame in details.items():
        frame = frame.sort_values("customer_id")
        if frame.customer_id.tolist() != reference.customer_id.tolist():
            raise ValueError("The bootstrap needs the same customers for every strategy")
        contributions[strategy] = np.where(frame.selected, frame.churn * frame.assumed_save_rate * frame.customer_value - frame.total_cost, 0)
    for a, b in pairs:
        if a in contributions and b in contributions:
            contributions[f"{a} minus {b}"] = contributions[a] - contributions[b]
    keys = list(contributions)
    matrix = np.vstack([contributions[k] for k in keys])
    samples = np.empty((iterations, len(keys)))
    for i in range(iterations):
        samples[i] = matrix[:, rng.integers(0, matrix.shape[1], matrix.shape[1])].sum(axis=1)
    return pd.DataFrame({"strategy": keys, "label_based_simulated_net": matrix.sum(axis=1),
                         "lower_95": np.quantile(samples, .025, axis=0), "upper_95": np.quantile(samples, .975, axis=0),
                         "iterations": iterations, "seed": seed, "population": "test",
                         "method": "paired customer bootstrap of frozen lists; assumed save rate; historical labels"})


def fairness_audit(details, cfg, strategies=("risk", "ev", "segment_offers"), iterations=1000, seed=42):
    """Selection-rate ratios vs a reference group, with bootstrap CI and a risk-adjusted ratio."""
    guard = cfg["guardrails"]
    low, high = guard["selection_ratio_alert"]
    rng = np.random.default_rng(seed)
    base = details["ev"]
    n = len(base)
    draws = [rng.integers(0, n, n) for _ in range(iterations)]
    deciles = pd.qcut(base.churn_probability.rank(method="first"), 10, labels=False).to_numpy()
    weights = np.bincount(deciles, minlength=10) / n
    rows = []
    for strategy in [s for s in strategies if s in details]:
        frame = details[strategy].set_index("customer_id").loc[base.customer_id].reset_index()
        selected = frame.selected.to_numpy(dtype=float)
        for attribute in guard["audit_attributes"]:
            values = frame[attribute].astype(str)
            groups = sorted(values.unique())
            codes = pd.Categorical(values, groups).codes
            reference = str(guard["reference_groups"][attribute])
            boot = np.array([np.bincount(codes[d], weights=selected[d], minlength=len(groups)) / np.maximum(np.bincount(codes[d], minlength=len(groups)), 1) for d in draws])
            adjusted = []
            for g in range(len(groups)):
                rate_by_decile, w = [], []
                for d in range(10):
                    mask = (codes == g) & (deciles == d)
                    if mask.any():
                        rate_by_decile.append(selected[mask].mean())
                        w.append(weights[d])
                adjusted.append(np.dot(rate_by_decile, w) / np.sum(w) if w else np.nan)
            if reference == "overall":
                # Business segments are compared with the overall selection rate.
                ref_rate, ref_boot, ref_adjusted = selected.mean(), np.array([selected[d].mean() for d in draws])[:, None], selected.mean()
            else:
                ref = groups.index(reference)
                ref_rate, ref_boot, ref_adjusted = frame.loc[codes == ref].selected.mean(), boot[:, [ref]], adjusted[ref]
            ratios = boot / np.where(ref_boot > 0, ref_boot, np.nan)
            for g, group in enumerate(groups):
                part = frame.loc[codes == g]
                rate = float(part.selected.mean())
                ratio = rate / ref_rate if ref_rate > 0 else None
                adj_ratio = adjusted[g] / ref_adjusted if ref_adjusted > 0 else None
                lo, hi = (np.nanquantile(ratios[:, g], [.025, .975]) if np.isfinite(ratios[:, g]).any() else (np.nan, np.nan))
                small = len(part) < guard["min_group_size"]
                outside = ratio is not None and not low <= ratio <= high
                churners = part.loc[part.churn.eq(1)] if "churn" in part else part.iloc[0:0]
                rows.append({"strategy": strategy, "attribute": attribute, "group": group, "reference_group": reference, "customers": len(part),
                             "small_sample": small, "selection_rate": rate, "ratio_to_reference": ratio, "ratio_lower_95": lo, "ratio_upper_95": hi,
                             "risk_adjusted_ratio": adj_ratio, "selection_rate_among_churners": float(churners.selected.mean()) if len(churners) else None,
                             "observed_churn": float(part.churn.mean()) if "churn" in part else None, "mean_probability": float(part.churn_probability.mean()),
                             "calibration_gap": float(part.churn_probability.mean() - part.churn.mean()) if "churn" in part else None,
                             "mean_customer_value": float(part.customer_value.mean()),
                             # Flag only gaps that are material, statistically clear and not from a tiny group.
                             "review_flag": bool(outside and not small and (lo > 1 or hi < 1)),
                             "explained_by_risk": bool(outside and adj_ratio is not None and low <= adj_ratio <= high)})
    return pd.DataFrame(rows)


def pilot_sample_size(p_control, save_rate, alpha=0.05, power=0.80):
    """Customers per arm for a two-sided two-proportion z-test on churn (control vs offered)."""
    p_treat = p_control * (1 - save_rate)
    if p_control <= p_treat:
        return np.inf
    z_a, z_b = norm.ppf(1 - alpha / 2), norm.ppf(power)
    p_bar = (p_control + p_treat) / 2
    n = (z_a * np.sqrt(2 * p_bar * (1 - p_bar)) + z_b * np.sqrt(p_control * (1 - p_control) + p_treat * (1 - p_treat))) ** 2 / (p_control - p_treat) ** 2
    return float(np.ceil(n))


def pilot_decision(p_control, save_rate, arm, break_even_rate, alpha=0.05, draws=20000, seed=42):
    """Monte Carlo probabilities of go / extend / stop after one wave with `arm` customers per arm.

    q = 1 - churn(offered) / churn(holdout) with a delta-method interval. Go: interval above 0 and
    q >= break-even. Stop: q <= 0 or interval entirely below break-even. Extend otherwise.
    """
    rng = np.random.default_rng(seed)
    control = rng.binomial(arm, p_control, draws) / arm
    offered = rng.binomial(arm, p_control * (1 - save_rate), draws) / arm
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = offered / control
        q = 1 - ratio
        se = ratio * np.sqrt((1 - offered) / (arm * offered) + (1 - control) / (arm * control))
    z = norm.ppf(1 - alpha / 2)
    se = np.where(np.isfinite(se), se, np.inf)
    go = (q - z * se > 0) & (q >= break_even_rate)
    stop = ~go & ((q <= 0) | (q + z * se < break_even_rate))
    return {"p_go": float(go.mean()), "p_extend": float((~go & ~stop).mean()), "p_stop": float(stop.mean())}


def pilot_plan(target, cfg, recommended_share, break_even_rate):
    """Pilot on the recommended list scaled to the customer base; sample sizes and the go/stop rule's error rates."""
    pilot = cfg["pilot"]
    picked = target.loc[target.selected]
    p_control = float(picked.churn_probability.mean())
    contacted_share = len(picked) / len(target)
    list_size = int(round(contacted_share * pilot["base_population"]))
    arm = int(np.floor(list_size * pilot["holdout_share"]))
    rows = []
    marks = {round(break_even_rate, 4)} if break_even_rate is not None else set()
    for q in sorted(set(pilot["save_rate_grid"]) | marks):
        n = pilot_sample_size(p_control, q, pilot["alpha"], pilot["power"])
        rows.append({"assumed_save_rate": q, "is_break_even": q in marks, "control_churn": p_control, "treated_churn": p_control * (1 - q),
                     "customers_per_arm": n, "total_customers": 2 * n, "arm_size_per_wave": arm,
                     "waves_needed": int(np.ceil(n / arm)) if arm > 0 and np.isfinite(n) else None,
                     **(pilot_decision(p_control, q, arm, break_even_rate, pilot["alpha"], seed=cfg["seed"]) if arm > 0 and marks else {})})
    mde = None
    if arm > 0 and pilot_sample_size(p_control, 0.999, pilot["alpha"], pilot["power"]) <= arm:
        mde = float(brentq(lambda q: pilot_sample_size(p_control, q, pilot["alpha"], pilot["power"]) - arm, 1e-4, 0.999))
    summary = {"control_churn_expected": p_control, "observed_churn_test_list": float(picked.churn.mean()) if "churn" in picked and len(picked) else None,
               "recommended_share": recommended_share, "contacted_share": contacted_share, "base_population": pilot["base_population"],
               "list_size_per_wave": list_size, "arm_size_per_wave": arm, "break_even_save_rate": break_even_rate,
               "per_arm_break_even": pilot_sample_size(p_control, break_even_rate, pilot["alpha"], pilot["power"]) if marks else None,
               "minimum_detectable_save_rate_one_wave": mde,
               "decision_rule": "go if the 95% interval of q is above 0 and q >= break-even; stop if q <= 0 or the interval is below break-even; otherwise extend",
               **{k: pilot[k] for k in ["alpha", "power", "holdout_share", "outcome_window_days"]}}
    return pd.DataFrame(rows), summary


def model_profit_check(run, cfg, scores):
    """Money check of the model choice: every calibrated candidate ranks the same customers for the same budget and standard offer."""
    import joblib
    from .data import features
    models = joblib.load(run / "candidates.joblib")
    columns = read_json(run / "manifest.json")["feature_columns"]
    rows = []
    for population in ["validation", "test"]:
        part = scores.loc[scores.split.eq(population)]
        budget = campaign_budget(len(part), cfg)
        X = features(part)[columns]
        for name, model in models.items():
            if name.endswith("_calibrated"):
                _, stats = run_strategy(part.assign(churn_probability=model.predict_proba(X)[:, 1]), budget, cfg, "ev")
                rows.append({"population": population, "model": name.removesuffix("_calibrated"), "budget": budget, "selected_count": stats["selected_count"],
                             "expected_net_value": stats["expected_net_value"], "label_based_net": stats["label_based_simulated_net"],
                             "precision_contacted": stats["precision_contacted"]})
    return pd.DataFrame(rows)


def offer_mix(target):
    picked = target.loc[target.selected]
    if picked.empty:
        return pd.DataFrame(columns=["tenure_segment", "Contract", "offer_id", "customers"])
    return picked.groupby(["tenure_segment", "Contract", "offer_id"], observed=True).size().reset_index(name="customers")


def eda(run):
    train = pd.read_csv(run / "customers.csv").query("split == 'train'").copy()
    train["tenure_segment"] = tenure_segment(train.tenure)
    train["charges_band"] = pd.qcut(train.MonthlyCharges, 4, duplicates="drop").astype(str)
    rows = []
    for col in ["Contract", "tenure_segment", "charges_band", "InternetService", "PaymentMethod", "OnlineSecurity", "TechSupport", "SeniorCitizen"]:
        for group, part in train.groupby(col, observed=True):
            rows.append({"attribute": col, "group": str(group), "n": len(part), "churn_rate": part.churn.mean(), "mean_monthly_charges": part.MonthlyCharges.mean(), "mean_tenure": part.tenure.mean()})
    save_csv(pd.DataFrame(rows), run / "eda_segments.csv")
    save_csv(train[["tenure", "MonthlyCharges", "TotalCharges", "churn"]].corr().reset_index(names="feature"), run / "correlations.csv")
    save_csv(train.describe(include="all").reset_index(names="statistic"), run / "eda_descriptive.csv")


def simulate(run=None):
    run = run or latest_run()
    manifest = read_json(run / "manifest.json")
    cfg = manifest["config"]
    scores = pd.read_csv(run / "scorecard.csv")
    validation, test = scores.query("split == 'validation'"), scores.query("split == 'test'")
    print("Validation phase: thresholds, strategy and budget recommendation", flush=True)
    thresholds = risk_value_thresholds(validation, cfg)
    write_json(run / "targeting_thresholds.json", thresholds)
    val_budget = campaign_budget(len(validation), cfg)
    choice = select_strategy(validation, val_budget, cfg, thresholds)
    strategy = choice["strategy"]
    val_curve = profit_curve(validation, cfg, [strategy], thresholds, population="validation")
    recommendation = recommend_budget(val_curve, cfg, strategy)
    write_json(run / "validation_decisions.json", {"thresholds": thresholds, "strategy_selection": choice, "budget_recommendation": recommendation})

    print("Test phase: comparisons, uncertainty, sensitivity, fairness", flush=True)
    budget = campaign_budget(len(test), cfg)
    comparison, details, scenarios, random_results = compare(test, budget, cfg, thresholds, cfg["random_campaign_iterations"])
    save_csv(comparison, run / "strategy_comparison.csv")
    save_csv(random_results, run / "random_campaigns.csv")
    for name, detail in details.items():
        save_csv(detail, run / f"targeting_{name}.csv")
    write_json(run / "campaign_scenarios.json", scenarios)
    save_csv(economic_uncertainty(details, cfg["bootstrap_iterations"], cfg["seed"]), run / "economic_uncertainty.csv")
    save_csv(risk_value_matrix(details, thresholds), run / "risk_value_matrix.csv")
    rules, p_star = threshold_business(test, cfg, manifest["threshold"], budget)
    save_csv(rules, run / "threshold_business.csv")
    from .business import offer_options
    population_options = offer_options(value_customers(test, cfg), [default_offer(cfg)])
    write_json(run / "break_even.json", {"strategy": strategy, **break_even(details[strategy], cfg, population_options), "break_even_probability_quantiles": p_star})
    save_csv(tornado(test, budget, cfg, strategy, thresholds), run / "tornado.csv")
    save_csv(scenario_table(test, budget, cfg, strategy, thresholds), run / "scenarios.csv")
    save_csv(sensitivity(test, budget, cfg, strategy, thresholds), run / "sensitivity.csv")
    print("Profit curves", flush=True)
    curve = pd.concat([val_curve, profit_curve(test, cfg, ["risk", "risk_positive_ev", "value", "ev", "segment_offers"], thresholds)], ignore_index=True)
    save_csv(curve, run / "budget_curve.csv")
    reco_budget = campaign_budget(len(test), cfg, recommendation["recommended_share"])
    reco_table, reco_stats = run_strategy(test, reco_budget, cfg, strategy, thresholds)
    save_csv(reco_table, run / "targeting_recommended.csv")
    reco_break = break_even(reco_table, cfg)
    write_json(run / "recommended_campaign.json", {"strategy": strategy, "budget_share": recommendation["recommended_share"], "budget": reco_budget, **flat(reco_stats),
                                                   "contacted_share": reco_stats["selected_count"] / len(test), "break_even": reco_break})
    print("Fairness and pilot design", flush=True)
    save_csv(fairness_audit(details, cfg, iterations=cfg["bootstrap_iterations"], seed=cfg["seed"]), run / "fairness.csv")
    power, pilot = pilot_plan(reco_table, cfg, recommendation["recommended_share"], reco_break.get("break_even_default_save_rate"))
    save_csv(power, run / "pilot_power.csv")
    write_json(run / "pilot_plan.json", pilot)
    save_csv(offer_mix(details["segment_offers"]), run / "segment_offer_mix.csv")
    save_csv(model_profit_check(run, cfg, scores), run / "model_profit_check.csv")
    offers = pd.DataFrame(cfg["offers"])
    offers["eligibility"] = offers.eligibility.map(lambda rule: "; ".join(f"{k} in {v}" for k, v in rule.items()) or "All customers")
    save_csv(offers, run / "offer_catalog.csv")
    eda(run)
    write_json(run / "simulation_manifest.json", {"run_id": run.name, "budget": budget, "thresholds": thresholds, "strategy": strategy,
                                                  "population": "test", "decisions_made_on": "validation", "assumptions_not_estimated": True})
    return run
