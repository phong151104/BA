import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm
from telco_retention.analysis import (apply_overrides, campaign_budget, compare, economic_uncertainty, fairness_audit, pilot_decision, pilot_plan, pilot_sample_size, profit_curve,
                                      recommend_budget, select_strategy, sensitivity, share_grid, tornado, break_even, risk_value_matrix, prior_shift, stress_test,
                                      draw_assumptions, reprice_frozen)
from telco_retention.business import campaign, default_offer, fixed_campaign, offer_options, value_customers
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



def test_pilot_rule_error_rates_follow_the_true_save_rate():
    outcomes = [pilot_decision(.6, q, 800, .14, draws=5000, seed=1) for q in [0, .1, .14, .2, .3]]
    for o in outcomes:
        assert o["p_go"] + o["p_extend"] + o["p_stop"] == pytest.approx(1)
    go = [o["p_go"] for o in outcomes]
    assert go == sorted(go) and go[0] < .01 and go[-1] > .99
    assert outcomes[0]["p_stop"] > .5 and abs(outcomes[2]["p_go"] - .5) < .1


def test_pilot_is_sized_from_customers_contacted_not_budget_share():
    cfg = cfg_small()
    target = sample(200).assign(selected=lambda d: d.index < 44)
    power, plan = pilot_plan(target, cfg, recommended_share=.24, break_even_rate=.14)
    assert plan["list_size_per_wave"] == round(44 / 200 * cfg["pilot"]["base_population"])
    assert plan["arm_size_per_wave"] == int(plan["list_size_per_wave"] * cfg["pilot"]["holdout_share"])
    assert power.is_break_even.sum() == 1 and power.loc[power.is_break_even, "assumed_save_rate"].item() == .14
    assert plan["per_arm_break_even"] == pilot_sample_size(plan["control_churn_expected"], .14)


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


def test_vectorised_repricing_matches_fixed_campaign():
    cfg = cfg_small()
    data = sample()
    target, _ = campaign(data, 220, cfg)
    draws = draw_assumptions(cfg, 4, 3)
    fast = reprice_frozen(target, cfg, draws)
    for i in range(len(draws)):
        changed = apply_overrides(cfg, draws.iloc[i].to_dict())
        _, stats = fixed_campaign(data, target, 1e9, changed, [default_offer(changed)])
        assert fast[i] == pytest.approx(stats["expected_net_value"], rel=1e-10, abs=1e-8)
    assert (draw_assumptions(cfg, 4, 3).to_numpy() == draws.to_numpy()).all()
    assert apply_overrides(cfg, {"value.tenure_factor_spread": 0.4})["value"]["tenure_factors"] == {"new": 0.6, "developing": 1.0, "loyal": 1.4}


def test_prior_shift_hits_the_target_and_keeps_the_ranking():
    p = np.random.default_rng(1).uniform(0.02, 0.9, 500)
    shifted, delta = prior_shift(p, 0.10)
    assert shifted.mean() == pytest.approx(0.10, abs=1e-9) and delta < 0
    assert (np.argsort(shifted, kind="mergesort") == np.argsort(p, kind="mergesort")).all()


def test_stress_test_rows_and_sample_row_match_an_unlimited_campaign():
    cfg = cfg_small()
    data = sample()
    table = stress_test(data, cfg, "ev", 0.10)
    assert len(table) == 2 * (1 + len(cfg["stress_test"]["target_churn"]))
    base = table.loc[table.economy.str.startswith("Sample") & table.target_churn.isna()].iloc[0]
    _, stats = campaign(data, 10 ** 6, cfg)
    assert base.positive_ev_customers == stats["selected_count"] and base.net_no_budget_limit == pytest.approx(stats["expected_net_value"])
    sample_rows = table.loc[table.economy.str.startswith("Sample")]
    assert sample_rows.positive_ev_customers.is_monotonic_decreasing
    vn = table.loc[table.economy.str.startswith("Vietnam")].iloc[0]
    assert vn.mean_monthly_bill == pytest.approx(cfg["vietnam_scenario"]["monthly_bill_vnd"] / cfg["vietnam_scenario"]["usd_vnd"])


def test_risk_value_matrix_partitions_customers():
    cfg = cfg_small()
    _, details, _, _ = compare(sample(), 220, cfg, random_iterations=1)
    matrix = risk_value_matrix(details, {"risk": .5, "value": 300})
    assert matrix.customers.sum() == 40
    assert matrix.selected_ev.sum() == details["ev"].selected.sum()
    assert matrix.value_at_risk_share.sum() == pytest.approx(1)
