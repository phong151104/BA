from copy import deepcopy
import numpy as np
import pandas as pd
import pytest
from telco_retention.analysis import sensitivity, budget_curve, compare, economic_uncertainty
from telco_retention.business import campaign
from telco_retention.common import config
from telco_retention.reporting import assumption_summary, eda_findings


def sample():
    return pd.DataFrame({"customer_id": ["a", "b", "c"], "churn_probability": [.4, .8, .2],
                         "tenure": [3, 20, 40], "MonthlyCharges": [100., 100., 100.], "churn": [0, 1, 1]})


@pytest.mark.parametrize("policy", [None, {"new": "light", "developing": "standard", "loyal": "intensive"}])
def test_sensitivity_matches_active_policy(policy):
    cfg = config()
    data = sample()
    reference, stats = campaign(data, 60, cfg, cfg["offers"], policy=policy)
    results = sensitivity(data, 60, cfg, offers=cfg["offers"], policy=policy)
    unchanged = results.query("axis == 'cost_save_rate' and parameter == 0.2 and cost_multiplier == 1")
    assert len(unchanged) == 2
    np.testing.assert_allclose(unchanged.expected_net_value, stats["expected_net_value"])
    assert set(results.reference_scenario_id) == {stats["scenario_id"]}
    assert results.query("mode == 'fixed'").turnover.eq(0).all()
    assert results.query("mode == 'retarget'").budget_feasible.all()
    assert results.scenario_id.notna().all()


def test_budget_curve_active_policy():
    cfg = config()
    policy = dict.fromkeys(["new", "developing", "loyal"], "light")
    result = budget_curve(sample(), cfg, offers=cfg["offers"], policy=policy)
    assert len(result) == 21 * 6
    for _, row in result.query("strategy == 'active_policy'").iterrows():
        _, stats = campaign(sample(), row.budget, cfg, cfg["offers"], policy=policy)
        assert row.expected_net_value == pytest.approx(stats["expected_net_value"])


def test_economic_bootstrap_paired_and_reproducible():
    _, details, _, _ = compare(sample(), 44, config(), random_iterations=2)
    first = economic_uncertainty(details, iterations=50)
    pd.testing.assert_frame_equal(first, economic_uncertainty(details, iterations=50))
    vals = first.set_index("strategy")
    assert vals.loc["ev_minus_risk_positive_ev", "label_based_simulated_net"] == pytest.approx(
        vals.loc["ev", "label_based_simulated_net"] - vals.loc["risk_positive_ev", "label_based_simulated_net"])
    same = {key: details["ev"] for key in ["ev", "risk", "risk_positive_ev"]}
    delta = economic_uncertainty(same, iterations=50).set_index("strategy").loc["ev_minus_risk_positive_ev"]
    assert delta.lower_95 == delta.upper_95 == 0


def test_report_assumptions_are_config_driven():
    cfg = config()
    cfg.update(margin=.45, base_horizon=6, horizon_cap=18)
    cfg["offers"][1].update(offer_cost=35, contact_cost=4, save_rate=.35)
    text = assumption_summary(cfg)
    assert all(value in text for value in ["45.0%", "6 tháng", "18 tháng", "35.0%", "35 + liên hệ 4"])
    assert "30.0%" not in text


def test_eda_narrative_uses_actual_data():
    data = pd.DataFrame({"attribute": ["Contract"] * 2, "group": ["A", "B"], "n": [100, 200], "churn_rate": [.5, .1]})
    text = eda_findings(data, "Contract")
    assert "50.0%" in text and "10.0%" in text and "40.0 điểm" in text
