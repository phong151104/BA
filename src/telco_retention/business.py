from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix, vstack, csr_matrix
from .common import canonical, config
from .data import SEGMENTS, tenure_segment

STRATEGY_LABELS = {
    "none": "No campaign", "random": "Random contact", "random_mean": "Random contact (mean of runs)",
    "risk": "Highest churn risk", "risk_positive_ev": "Highest risk, positive EV only", "value": "Highest customer value",
    "ev": "Expected value (single offer)", "segment_offers": "Expected value + segment offers",
}


def scenario_id(scenario):
    return hashlib.sha256(json.dumps(canonical(scenario), sort_keys=True).encode()).hexdigest()[:12]


def offer_by_id(cfg, offer_id):
    for offer in cfg["offers"]:
        if offer["offer_id"] == offer_id:
            return offer
    raise KeyError(f"Unknown offer_id: {offer_id}")


def default_offer(cfg):
    return offer_by_id(cfg, cfg["campaign"]["default_offer"])


def annuity_months(months, discount_rate_annual):
    """Present value, in months of margin, of `months` of future payments (end of month)."""
    months = np.asarray(months, dtype=float)
    monthly = (1 + discount_rate_annual) ** (1 / 12) - 1
    if monthly <= 0:
        return months
    return (1 - (1 + monthly) ** -months) / monthly


def value_customers(scores, settings=None):
    cfg = config() if settings is None else settings
    value = cfg["value"]
    if not 0 <= value["margin"] <= 1 or value["base_horizon_months"] < 0 or value["horizon_cap_months"] < 0:
        raise ValueError("Margin must be in [0,1]; horizons must be non-negative")
    if not 0 <= value["discount_rate_annual"] < 1:
        raise ValueError("Annual discount rate must be in [0,1)")
    if any(not np.isfinite(x) or x < 0 for x in value["tenure_factors"].values()):
        raise ValueError("Tenure factors must be finite and non-negative")
    out = scores.copy().reset_index(drop=True)
    out["tenure_segment"] = tenure_segment(out.tenure)
    if out[["tenure", "MonthlyCharges", "churn_probability"]].isna().any().any():
        raise ValueError("Fill missing numbers with training medians before valuing customers")
    if not out.churn_probability.between(0, 1).all():
        raise ValueError("Probabilities must be in [0,1]")
    factors = out.tenure_segment.astype(str).map(value["tenure_factors"]).astype(float)
    out["remaining_months"] = np.minimum(value["horizon_cap_months"], value["base_horizon_months"] * factors)
    out["discounted_months"] = annuity_months(out.remaining_months, value["discount_rate_annual"])
    out["customer_value"] = out.MonthlyCharges * value["margin"] * out.discounted_months
    return out


def eligible(customers, rules):
    mask = np.ones(len(customers), dtype=bool)
    for column, allowed in (rules or {}).items():
        if column not in customers:
            raise ValueError(f"Eligibility column missing from customer data: {column}")
        mask &= customers[column].astype(str).isin([str(v) for v in allowed]).to_numpy()
    return mask


def offer_options(customers, offers):
    frames = []
    if not offers or len({o["offer_id"] for o in offers}) != len(offers):
        raise ValueError("Offers must be a non-empty list with unique IDs")
    for offer in offers:
        q, cost, contact = offer["save_rate"], offer["offer_cost"], offer["contact_cost"]
        if not all(np.isfinite(x) for x in [q, cost, contact]) or not 0 <= q <= 1 or min(cost, contact) < 0:
            raise ValueError("Save rate must be in [0,1]; costs must be finite and non-negative")
        part = customers.copy()
        part["customer_index"] = np.arange(len(part))
        part = part.loc[eligible(part, offer.get("eligibility"))].copy()
        part["offer_id"] = offer["offer_id"]
        part["assumed_save_rate"] = q
        part["offer_cost"], part["contact_cost"] = cost, contact
        part["total_cost"] = cost + contact
        part["expected_saved_probability"] = part.churn_probability * q
        part["expected_retained_value"] = part.expected_saved_probability * part.customer_value
        part["expected_net_value"] = part.expected_retained_value - part.total_cost
        pv = (part.churn_probability * part.customer_value).to_numpy()
        qv = (q * part.customer_value).to_numpy()
        part["break_even_save_rate"] = np.divide(part.total_cost, pv, out=np.full(len(part), np.nan), where=pv > 0)
        part["break_even_probability"] = np.divide(part.total_cost, qv, out=np.full(len(part), np.nan), where=qv > 0)
        frames.append(part)
    return pd.concat(frames, ignore_index=True)


def _greedy(options, budget, key="expected_net_value", seed=42, max_contacts=None):
    candidates = options.copy()
    if key == "random":
        candidates["priority"] = np.random.default_rng(seed).random(len(candidates))
    elif key == "ratio":
        candidates["priority"] = np.where(candidates.total_cost > 0, candidates.expected_net_value / candidates.total_cost.replace(0, np.nan), np.inf)
    else:
        candidates["priority"] = candidates[key]
    candidates = candidates.sort_values(["priority", "customer_id", "offer_id"], ascending=[False, True, True])
    limit = len(candidates) if max_contacts is None else max_contacts
    chosen, used, spent = [], set(), 0.0
    for idx, customer, cost in zip(candidates.index, candidates.customer_index.to_numpy(), candidates.total_cost.to_numpy()):
        if len(chosen) >= limit:
            break
        if customer not in used and spent + cost <= budget + 1e-8:
            chosen.append(idx)
            used.add(customer)
            spent += cost
    return chosen


def select_options(options, budget, strategy="ev", seed=42, solver=None, max_contacts=None):
    solver = solver or {"time_limit_seconds": 30, "mip_rel_gap": 0.0}
    if not np.isfinite(budget) or budget < 0:
        raise ValueError("Budget must be finite and non-negative")
    if options.empty or strategy == "none" or max_contacts == 0:
        return [], {"status": "empty", "gap": 0.0}
    # Baselines intentionally do not inspect EV: they emulate the stated simple rule.
    pool = options.loc[options.expected_net_value.gt(0)].copy() if strategy in ["ev", "risk_positive_ev"] else options.copy()
    if pool.empty:
        return [], {"status": "no_positive_ev", "gap": 0.0}
    if strategy != "ev":
        key = {"risk": "churn_probability", "risk_positive_ev": "churn_probability", "value": "customer_value", "random": "random"}[strategy]
        return _greedy(pool, budget, key, seed, max_contacts), {"status": "baseline", "gap": None}
    if pool.customer_index.is_unique and pool.total_cost.nunique() == 1:
        # Equal costs: sorting by EV is exactly optimal for the budget and the contact cap.
        return _greedy(pool, budget, max_contacts=max_contacts), {"status": "optimal_sort", "gap": 0.0}
    n = len(pool)
    rows, inv = np.unique(pool.customer_index, return_inverse=True)
    blocks = [coo_matrix((np.ones(n), (inv, np.arange(n))), shape=(len(rows), n)).tocsr(), csr_matrix(pool.total_cost.to_numpy().reshape(1, -1))]
    upper = [np.ones(len(rows)), [budget]]
    if max_contacts is not None:
        blocks.append(csr_matrix(np.ones((1, n))))
        upper.append([max_contacts])
    upper = np.concatenate(upper)
    result = milp(-pool.expected_net_value.to_numpy(), integrality=np.ones(n), bounds=Bounds(0, 1),
                  constraints=LinearConstraint(vstack(blocks, format="csr"), np.zeros(len(upper)), upper),
                  options={"time_limit": solver["time_limit_seconds"], "mip_rel_gap": solver["mip_rel_gap"]})
    if result.x is not None:
        mask = result.x > 0.5
        picked = pool.loc[mask]
        valid = (np.allclose(result.x, np.round(result.x), atol=1e-5) and picked.customer_index.is_unique
                 and picked.total_cost.sum() <= budget + 1e-7 and (max_contacts is None or len(picked) <= max_contacts))
        if valid:
            return picked.index.tolist(), {"status": "optimal" if result.status == 0 else "feasible_time_limit", "gap": getattr(result, "mip_gap", None)}
    return _greedy(pool, budget, "ratio", max_contacts=max_contacts), {"status": "heuristic_fallback", "gap": None}


def summarize(table, budget, thresholds=None):
    picked = table.loc[table.selected]
    spent = float(picked.total_cost.sum())
    net = float(picked.expected_net_value.sum())
    result = {
        "selected_count": len(picked), "cost": spent, "remaining_budget": float(budget - spent),
        "expected_saved": float(picked.expected_saved_probability.sum()),
        "expected_retained_value": float(picked.expected_retained_value.sum()), "expected_net_value": net,
        "roi": net / spent if spent > 0 else None,
        # Without labels, precision among contacted is the mean predicted churn probability of the list.
        "expected_precision": float(picked.churn_probability.mean()) if len(picked) else None,
        "precision_contacted": float(picked.churn.mean()) if "churn" in table and len(picked) else None,
    }
    if "churn" in table:
        result["label_based_simulated_net"] = float((picked.churn * picked.assumed_save_rate * picked.customer_value - picked.total_cost).sum())
    if thresholds:
        high = table.churn_probability.ge(thresholds["risk"]) & table.customer_value.ge(thresholds["value"])
        result["high_risk_high_value_count"] = int(high.sum())
        result["high_risk_high_value_coverage"] = float((high & table.selected).sum() / high.sum()) if high.sum() else None
    return result


def explain_rows(result, strategy, budget, currency="USD"):
    reason = np.select(
        [result.selected, np.full(len(result), strategy == "none"), result.expected_net_value.le(0), result.total_cost.gt(budget)],
        [f"Selected by rule: {STRATEGY_LABELS.get(strategy, strategy)}", "No campaign is run", "Expected value is not positive", "Budget is below the offer cost"],
        default="Positive EV but outranked within the budget")
    detail = result.apply(lambda r:
        f"p={r.churn_probability:.1%} x save rate {r.assumed_save_rate:.0%} x value {r.customer_value:,.2f}"
        f" - cost {r.total_cost:,.2f} = EV {r.expected_net_value:,.2f} {currency}; "
        + (f"break-even save rate {r.break_even_save_rate:.1%}" if pd.notna(r.break_even_save_rate) else "no finite break-even save rate")
        + ("; a baseline rule selected it despite non-positive EV" if r.selected and r.expected_net_value <= 0 else ""), axis=1) if len(result) else pd.Series(dtype=str)
    return reason, detail


def contact_limit(n, share):
    """Customer-experience cap on contacts; rounded up so small lists can still be contacted."""
    return None if share is None else int(np.ceil(share * n - 1e-9))


def campaign(scores, budget, settings=None, offers=None, strategy="ev", thresholds=None, seed=None):
    cfg = deepcopy(config() if settings is None else settings)
    seed = cfg["seed"] if seed is None else seed
    chosen_offers = deepcopy(offers) if offers is not None else [default_offer(cfg)]
    customers = value_customers(scores, cfg)
    options = offer_options(customers, chosen_offers)
    max_contacts = contact_limit(len(customers), cfg["campaign"].get("max_contact_share"))
    selected, solver = select_options(options, budget, strategy, seed, cfg["solver"], max_contacts)
    options["selected"] = options.index.isin(selected)
    # One row per customer: the chosen offer, otherwise the best potential offer.
    result = options.sort_values(["selected", "expected_net_value", "offer_id"], ascending=[False, False, True]).drop_duplicates("customer_id").sort_values("customer_id").reset_index(drop=True)
    result["selection_reason"], result["decision_detail"] = explain_rows(result, strategy, budget, cfg.get("currency", "USD"))
    scenario = {"value": cfg["value"], "offers": chosen_offers, "budget": budget, "strategy": strategy, "max_contacts": max_contacts,
                "seed": seed if strategy == "random" else None,
                "population_hash": hashlib.sha256(customers[["customer_id", "churn_probability", "MonthlyCharges", "tenure"]].round(10).to_csv(index=False).encode()).hexdigest()}
    sid = scenario_id(scenario)
    result["scenario_id"] = sid
    return result, {**summarize(result, budget, thresholds), "scenario_id": sid, "solver": solver, "scenario": scenario}


def fixed_campaign(scores, selected_table, budget, settings, offers, thresholds=None):
    """Re-price a frozen list (same customers and offers) under changed assumptions."""
    offers = [offers] if isinstance(offers, dict) else offers
    options = offer_options(value_customers(scores, settings), [{**o, "eligibility": {}} for o in offers])
    assignments = selected_table[["customer_id", "offer_id", "selected"]]
    result = options.merge(assignments, on=["customer_id", "offer_id"], how="inner", validate="one_to_one")
    if len(result) != len(selected_table):
        raise ValueError("A fixed list must keep every customer and offer of the reference list")
    stats = summarize(result, budget, thresholds)
    stats["budget_feasible"] = stats["cost"] <= budget + 1e-7
    return result, stats
