from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix, vstack, csr_matrix
from .common import config, jsonable

SEGMENTS = ["new", "developing", "loyal"]


def scenario_id(settings):
    return hashlib.sha256(json.dumps(jsonable(settings), sort_keys=True).encode()).hexdigest()[:12]


def value_customers(scores, settings=None):
    cfg = config() if settings is None else settings
    if not 0 <= cfg["margin"] <= 1 or cfg["base_horizon"] < 0 or cfg["horizon_cap"] < 0:
        raise ValueError("Margin phải trong [0,1], horizon không âm")
    if any(not np.isfinite(x) or x < 0 for x in cfg["tenure_factors"].values()):
        raise ValueError("Hệ số tenure phải hữu hạn và không âm")
    out = scores.copy().reset_index(drop=True)
    out["tenure_segment"] = pd.cut(out.tenure, [-np.inf, 12, 24, np.inf], labels=SEGMENTS).astype(str)
    if out[["tenure", "MonthlyCharges", "churn_probability"]].isna().any().any():
        raise ValueError("Scoring phải điền missing số bằng median train trước khi tính giá trị")
    if not out.churn_probability.between(0, 1).all():
        raise ValueError("Xác suất ngoài [0,1]")
    out["remaining_months"] = np.minimum(cfg["horizon_cap"], cfg["base_horizon"] * out.tenure_segment.map(cfg["tenure_factors"]))
    out["customer_value"] = out.MonthlyCharges * cfg["margin"] * out.remaining_months
    return out


def offer_options(customers, offers, policy=None):
    frames = []
    if not offers or len({o["offer_id"] for o in offers}) != len(offers):
        raise ValueError("Cần danh sách ưu đãi với ID duy nhất")
    for offer in offers:
        q, cost, contact = offer["save_rate"], offer["offer_cost"], offer["contact_cost"]
        if not all(np.isfinite(x) for x in [q, cost, contact]) or not 0 <= q <= 1 or min(cost, contact) < 0:
            raise ValueError("Save rate trong [0,1], chi phí hữu hạn và không âm")
        part = customers.copy()
        part["customer_index"] = np.arange(len(part))
        if policy:
            part = part.loc[part.tenure_segment.map(policy).eq(offer["offer_id"])].copy()
        part["offer_id"] = offer["offer_id"]
        part["assumed_save_rate"] = q
        part["offer_cost"], part["contact_cost"] = cost, contact
        part["total_cost"] = cost + contact
        part["expected_saved_probability"] = part.churn_probability * q
        part["expected_retained_value"] = part.expected_saved_probability * part.customer_value
        part["expected_net_value"] = part.expected_retained_value - part.total_cost
        part["break_even_save_rate"] = np.divide(part.total_cost, part.churn_probability * part.customer_value, out=np.full(len(part), np.nan), where=(part.churn_probability * part.customer_value).to_numpy() > 0)
        part["break_even_total_cost"] = part.expected_retained_value
        frames.append(part)
    return pd.concat(frames, ignore_index=True)


def _greedy(options, budget, key="expected_net_value", seed=42):
    candidates = options.copy()
    if key == "random":
        candidates["priority"] = np.random.default_rng(seed).random(len(candidates))
    elif key == "ratio":
        candidates["priority"] = np.where(candidates.total_cost > 0, candidates.expected_net_value / candidates.total_cost.replace(0, np.nan), np.inf)
    else:
        candidates["priority"] = candidates[key]
    candidates = candidates.sort_values(["priority", "customer_id", "offer_id"], ascending=[False, True, True])
    chosen, used, spent = [], set(), 0.0
    for idx, row in candidates.iterrows():
        if row.customer_index not in used and spent + row.total_cost <= budget + 1e-8:
            chosen.append(idx)
            used.add(row.customer_index)
            spent += row.total_cost
    return chosen


def select_options(options, budget, strategy="ev", seed=42, time_limit=30):
    if not np.isfinite(budget) or budget < 0:
        raise ValueError("Ngân sách phải hữu hạn và không âm")
    if options.empty or strategy == "none":
        return [], {"status": "empty", "gap": 0.0}
    # Baselines intentionally do not inspect EV: they emulate the stated simple rule.
    eligible = options.loc[options.expected_net_value.gt(0)].copy() if strategy == "ev" else options.copy()
    if eligible.empty:
        return [], {"status": "no_positive_ev", "gap": 0.0}
    if strategy != "ev":
        key = {"risk": "churn_probability", "value": "customer_value", "random": "random"}[strategy]
        return _greedy(eligible, budget, key, seed), {"status": "baseline", "gap": None}
    if eligible.customer_index.is_unique and eligible.total_cost.nunique() == 1:
        return _greedy(eligible, budget), {"status": "optimal_sort", "gap": 0.0}
    n = len(eligible)
    rows, inv = np.unique(eligible.customer_index, return_inverse=True)
    matrix = coo_matrix((np.ones(n), (inv, np.arange(n))), shape=(len(rows), n)).tocsr()
    matrix = vstack([matrix, csr_matrix(eligible.total_cost.to_numpy().reshape(1, -1))], format="csr")
    upper = np.r_[np.ones(len(rows)), budget]
    result = milp(-eligible.expected_net_value.to_numpy(), integrality=np.ones(n), bounds=Bounds(0, 1), constraints=LinearConstraint(matrix, np.zeros(len(upper)), upper), options={"time_limit": time_limit, "mip_rel_gap": 0.0})
    if result.x is not None:
        mask = result.x > 0.5
        picked = eligible.loc[mask]
        valid = np.allclose(result.x, np.round(result.x), atol=1e-5) and picked.customer_index.is_unique and picked.total_cost.sum() <= budget + 1e-7
        if valid:
            return picked.index.tolist(), {"status": "optimal" if result.status == 0 else "feasible_time_limit", "gap": getattr(result, "mip_gap", None)}
    return _greedy(eligible, budget, "ratio"), {"status": "heuristic_fallback", "gap": None}


def summarize(table, budget, thresholds=None):
    picked = table.loc[table.selected]
    spent = float(picked.total_cost.sum())
    net = float(picked.expected_net_value.sum())
    result = {
        "selected_count": len(picked), "cost": spent, "remaining_budget": float(budget - spent),
        "expected_saved": float(picked.expected_saved_probability.sum()),
        "expected_retained_value": float(picked.expected_retained_value.sum()), "expected_net_value": net,
        "roi": net / spent if spent > 0 else None,
        "precision_contacted": float(picked.churn.mean()) if "churn" in table and len(picked) else None,
    }
    if "churn" in table:
        result["label_based_simulated_net"] = float((picked.churn * picked.assumed_save_rate * picked.customer_value - picked.total_cost).sum())
    if thresholds:
        high = table.churn_probability.ge(thresholds["risk"]) & table.customer_value.ge(thresholds["value"])
        result["high_risk_high_value_coverage"] = float((high & table.selected).sum() / high.sum()) if high.sum() else None
    return result


def campaign(scores, budget, settings=None, offers=None, strategy="ev", policy=None, thresholds=None, seed=42):
    cfg = deepcopy(config() if settings is None else settings)
    chosen_offers = offers if offers is not None else [cfg["offers"][1]]
    customers = value_customers(scores, cfg)
    options = offer_options(customers, chosen_offers, policy)
    selected, solver = select_options(options, budget, strategy, seed, cfg["solver_time_limit"])
    options["selected"] = options.index.isin(selected)
    # One row per customer: chosen offer, otherwise best potential offer.
    result = options.sort_values(["selected", "expected_net_value", "offer_id"], ascending=[False, False, True]).drop_duplicates("customer_id").sort_values("customer_id").reset_index(drop=True)
    result["selection_reason"] = np.select([result.selected, result.expected_net_value.le(0)], ["Được ưu tiên theo chiến lược " + strategy, "EV không dương"], default="Không được chọn trong giới hạn ngân sách/tổ hợp tối ưu")
    scenario = {"settings": cfg, "offers": chosen_offers, "budget": budget, "strategy": strategy, "policy": policy, "seed": seed, "population_hash": hashlib.sha256(customers[["customer_id", "churn_probability", "customer_value"]].to_csv(index=False).encode()).hexdigest()}
    sid = scenario_id(scenario)
    result["scenario_id"] = sid
    return result, {**summarize(result, budget, thresholds), "scenario_id": sid, "solver": solver, "scenario": scenario}


def fixed_campaign(scores, selected_table, budget, settings, offer, thresholds=None):
    result = offer_options(value_customers(scores, settings), [offer])
    result["selected"] = result.customer_id.isin(selected_table.loc[selected_table.selected, "customer_id"])
    stats = summarize(result, budget, thresholds)
    stats["budget_feasible"] = stats["cost"] <= budget + 1e-7
    return result, stats
