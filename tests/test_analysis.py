import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm
from telco_retention.analysis import (apply_overrides, campaign_budget, compare, economic_uncertainty, fairness_audit, pilot_sample_size, profit_curve,
                                      recommend_budget, select_strategy, sensitivity, share_grid, tornado, break_even, risk_value_matrix)
from telco_retention.business import campaign, default_offer, offer_options, value_customers
from telco_retention.common import config


def cfg_small():
    cfg = config()
    cfg["campaign"]["max_contact_share"] = None
    return cfg


def sample(n=40, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"customer_id": [f"c{i:03d}" for i in range(n)], "churn_probability": rng.uniform(.05, .9, n), "tenure": rng.integers(0, 72, n),
                         "MonthlyCharges": rng.uniform(20, 110, n), "churn": rng.integers(0, 2, n), "Contract": rng.choice(["Month-to-month", "One year", "Two year"], n),
                         "InternetService": rng.choice(["DSL", "Fiber optic", "No"], n), "TechSupport": rng.choice(["Yes", "No"], n),
                         "gender": rng.choice(["Male", "Female"], n), "SeniorCitizen": rng.integers(0, 2, n)})


def test_campaign_budget_is_explicit_config():
    cfg = cfg_small()
    offer = default_offer(cfg)
    assert campaign_budget(1409, cfg) == int(np.floor(cfg["campaign"]["budget_share"] * 1409)) * (offer["offer_cost"] + offer["contact_cost"])
    cfg["campaign"]["budget_share"] = 0.2
    assert campaign_budget(100, cfg) == 20 * (offer["offer_cost"] + offer["contact_cost"])


def test_overrides_shift_all_offers_and_keep_base_config():
    cfg = cfg_small()
    changed = apply_overrides(cfg, {"save_rate": default_offer(cfg)["save_rate"] + .05, "offer_cost_multiplier": 2, "contact_cost": 7, "value.margin": .4})
    for before, after in zip(cfg["offers"], changed["offers"]):
        assert after["save_rate"] == pytest.approx(min(1, before["save_rate"] + .05))
        assert after["offer_cost"] == pytest.approx(2 * before["offer_cost"]) and after["contact_cost"] == 7
    assert changed["value"]["margin"] == .4 and cfg["value"]["margin"] != .4


def test_sensitivity_reference_case_matches_campaign():
    cfg = cfg_small()
    data = sample()
    budget = 220
    _, stats = campaign(data, budget, cfg)
    results = sensitivity(data, budget, cfg, "ev")
    base = results.query("axis == 'save_rate x offer_cost' and cost_multiplier == 1 and parameter == @default_offer(@cfg)['save_rate']")
    assert len(base) == 2
    np.testing.assert_allclose(base.expected_net_value, stats["expected_net_value"])
    assert set(results.reference_scenario_id) == {stats["scenario_id"]}
    assert results.query("mode == 'retarget'").budget_feasible.all()
    grids = cfg["sensitivity"]
    expected = len(grids["save_rate"]) * len(grids["offer_cost_multiplier"]) + sum(len(grids[a]) for a in ["contact_cost", "value.margin", "value.base_horizon_months", "value.discount_rate_annual"])
    assert len(results) == 2 * expected


def test_tornado_directions():
    cfg = cfg_small()
    result = tornado(sample(), 220, cfg, "ev").set_index("parameter")
    assert result.loc["save_rate", "net_high_retarget"] >= result.loc["save_rate", "net_low_retarget"]
    assert result.loc["offer_cost_multiplier", "net_low_retarget"] >= result.loc["offer_cost_multiplier", "net_high_retarget"]
    assert result.loc["value.margin", "net_high_fixed"] >= result.loc["value.margin", "net_low_fixed"]
    assert len(result) == len(cfg["assumption_register"])


def test_profit_curve_and_recommendation():
    cfg = cfg_small()
    data = sample(60)
    curve = profit_curve(data, cfg, ["ev", "risk"])
    assert len(curve) == 2 * len(share_grid(cfg))
    ev = curve.query("strategy == 'ev'").sort_values("budget_share")
    assert ev.expected_net_value.is_monotonic_increasing
    reco = recommend_budget(curve, cfg, "ev")
    hurdle = cfg["campaign"]["recommendation"]["min_marginal_roi"]
    chosen = ev.loc[ev.budget_share.eq(reco["recommended_share"])].iloc[0]
    assert chosen.marginal_roi >= hurdle
    later = ev.loc[ev.budget_share.gt(reco["recommended_share"])]
    assert not later.marginal_roi.ge(hurdle).any()


def test_strategy_selection_prefers_simple_unless_clear_gain():
    cfg = cfg_small()
    data = sample(80)
    choice = select_strategy(data, 440, cfg, None)
    gain = choice["relative_gain"]
    assert choice["strategy"] == ("segment_offers" if gain is not None and gain >= cfg["campaign"]["strategy_selection"]["min_relative_gain"] else "ev")


def test_economic_bootstrap_paired_and_reproducible():
    _, details, _, _ = compare(sample(), 220, cfg_small(), random_iterations=2)
    first = economic_uncertainty(details, iterations=50)
    pd.testing.assert_frame_equal(first, economic_uncertainty(details, iterations=50))
    vals = first.set_index("strategy")
    assert vals.loc["ev minus risk", "label_based_simulated_net"] == pytest.approx(vals.loc["ev", "label_based_simulated_net"] - vals.loc["risk", "label_based_simulated_net"])
    same = {key: details["ev"] for key in ["ev", "risk"]}
    delta = economic_uncertainty(same, iterations=50, pairs=(("ev", "risk"),)).set_index("strategy").loc["ev minus risk"]
    assert delta.lower_95 == delta.upper_95 == 0


def test_fairness_identical_strategies_give_identical_ratios():
    cfg = cfg_small()
    _, details, _, _ = compare(sample(200), 1100, cfg, random_iterations=1)
    details["segment_offers"] = details["ev"]
    audit = fairness_audit(details, cfg, iterations=100).set_index(["strategy", "attribute", "group"])
    a, b = audit.loc["ev"], audit.loc["segment_offers"]
    np.testing.assert_allclose(a.selection_rate, b.selection_rate)
    reference = audit.loc[("ev", "gender", "Male")]
    assert reference.ratio_to_reference == pytest.approx(1)
    overall = audit.xs("Contract", level="attribute")
    assert overall.ratio_to_reference.notna().any()


def test_pilot_sample_size_matches_formula():
    p1, q = .6, .2
    p2 = p1 * (1 - q)
    z_a, z_b = norm.ppf(.975), norm.ppf(.8)
    pbar = (p1 + p2) / 2
    expected = np.ceil((z_a * np.sqrt(2 * pbar * (1 - pbar)) + z_b * np.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2 / (p1 - p2) ** 2)
    assert pilot_sample_size(p1, q) == expected
    assert pilot_sample_size(p1, .4) < pilot_sample_size(p1, .2) < pilot_sample_size(p1, .1)
    assert pilot_sample_size(p1, 0) == np.inf


def test_break_even_save_rate_zeroes_frozen_list():
    cfg = cfg_small()
    data = sample()
    target, stats = campaign(data, 220, cfg)
    be = break_even(target, cfg, offer_options(value_customers(data, cfg), [default_offer(cfg)]))
    changed = apply_overrides(cfg, {"save_rate": be["break_even_default_save_rate"]})
    picked = target.loc[target.selected]
    q = changed["offers"][[o["offer_id"] for o in changed["offers"]].index(cfg["campaign"]["default_offer"])]["save_rate"]
    assert (picked.churn_probability * q * picked.customer_value - picked.total_cost).sum() == pytest.approx(0, abs=1e-6)
    assert be["minimum_viable_save_rate"] <= be["break_even_default_save_rate"]


def test_risk_value_matrix_partitions_customers():
    cfg = cfg_small()
    _, details, _, _ = compare(sample(), 220, cfg, random_iterations=1)
    matrix = risk_value_matrix(details, {"risk": .5, "value": 300})
    assert matrix.customers.sum() == 40
    assert matrix.selected_ev.sum() == details["ev"].selected.sum()
    assert matrix.value_at_risk_share.sum() == pytest.approx(1)
