from copy import deepcopy
from itertools import product
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from telco_retention.common import config
from telco_retention.business import annuity_months, campaign, contact_limit, default_offer, fixed_campaign, offer_options, value_customers, offer_by_id


def scores():
    return pd.DataFrame({"customer_id": ["a", "b", "c"], "churn_probability": [.4, .8, .2], "tenure": [20, 20, 20], "MonthlyCharges": [100, 100, 100],
                         "Contract": ["Month-to-month", "One year", "Month-to-month"], "model_version": "test"})


def simple_offers():
    return [{"offer_id": "light", "label": "Light", "offer_cost": 10.0, "contact_cost": 2.0, "save_rate": 0.10, "eligibility": {}},
            {"offer_id": "standard", "label": "Standard", "offer_cost": 20.0, "contact_cost": 2.0, "save_rate": 0.20, "eligibility": {}},
            {"offer_id": "intensive", "label": "Intensive", "offer_cost": 40.0, "contact_cost": 2.0, "save_rate": 0.30, "eligibility": {}}]


def settings():
    cfg = config()
    cfg["value"].update(margin=.25, base_horizon_months=12, discount_rate_annual=0.0)
    cfg["offers"] = simple_offers()
    cfg["campaign"]["default_offer"] = "standard"
    cfg["campaign"]["max_contact_share"] = None
    return cfg


def test_hand_calculation():
    target, stats = campaign(scores().iloc[:1], 22, settings())
    row = target.iloc[0]
    assert row.customer_value == 300
    assert row.expected_retained_value == pytest.approx(24)
    assert row.expected_net_value == pytest.approx(2)
    assert row.break_even_save_rate == pytest.approx(22 / (0.4 * 300))
    assert row.break_even_probability == pytest.approx(22 / (0.2 * 300))
    assert stats["cost"] == 22 and stats["expected_saved"] == pytest.approx(.08)
    assert stats["roi"] == pytest.approx(2 / 22)


def test_discounted_value():
    cfg = settings()
    cfg["value"]["discount_rate_annual"] = 0.12
    monthly = 1.12 ** (1 / 12) - 1
    expected = 100 * 0.25 * sum(1 / (1 + monthly) ** t for t in range(1, 13))
    assert value_customers(scores(), cfg).customer_value.iloc[0] == pytest.approx(expected)
    assert annuity_months(12, 0.0) == 12
    assert annuity_months(12, 0.12) < 12


@pytest.mark.parametrize("budget", [0, 1, 21.99])
def test_insufficient_budget(budget):
    target, stats = campaign(scores(), budget, settings())
    assert not target.selected.any() and stats["cost"] == 0 and stats["roi"] is None


@pytest.mark.parametrize("change", ["margin", "save_rate", "expensive"])
def test_no_positive_ev(change):
    cfg = settings()
    if change == "margin":
        cfg["value"]["margin"] = 0
    elif change == "save_rate":
        offer_by_id(cfg, "standard")["save_rate"] = 0
    else:
        offer_by_id(cfg, "standard")["offer_cost"] = 1000
    target, stats = campaign(scores(), 5000, cfg)
    assert stats["selected_count"] == 0 and stats["expected_net_value"] == 0


def test_default_offer_is_found_by_id_not_position():
    cfg = settings()
    cfg["offers"] = cfg["offers"][::-1]
    assert default_offer(cfg)["offer_id"] == "standard"
    _, stats = campaign(scores(), 22, cfg)
    assert stats["scenario"]["offers"][0]["offer_id"] == "standard"


def test_free_offers_zero_budget():
    cfg = settings()
    offer_by_id(cfg, "standard").update(offer_cost=0, contact_cost=0)
    target, stats = campaign(scores(), 0, cfg)
    assert target.selected.all() and stats["roi"] is None and stats["cost"] == 0


def test_tie_breaker():
    data = scores()
    data.churn_probability = .8
    data.customer_id = ["c", "a", "b"]
    target, _ = campaign(data, 22, settings())
    assert target.loc[target.selected, "customer_id"].tolist() == ["a"]


def test_no_labels_needed_or_used():
    data = scores()
    first, one = campaign(data, 22, settings())
    data["churn"] = [0, 0, 1]
    second, two = campaign(data, 22, settings())
    assert first.loc[first.selected, "customer_id"].tolist() == second.loc[second.selected, "customer_id"].tolist()
    assert one["precision_contacted"] is None and one["expected_precision"] == pytest.approx(.8)
    assert two["precision_contacted"] == 0


def brute_force(options, budget, max_contacts=None):
    best = 0.0
    choices = [[None] + options.index[options.customer_index.eq(c)].tolist() for c in sorted(options.customer_index.unique())]
    for pick in product(*choices):
        rows = options.loc[[p for p in pick if p is not None]]
        if rows.total_cost.sum() <= budget + 1e-9 and (max_contacts is None or len(rows) <= max_contacts):
            best = max(best, rows.expected_net_value.sum())
    return best


@pytest.mark.parametrize("budget,cap", [(55, None), (55, 0.30), (80, 0.60), (30, None)])
def test_solver_equals_bruteforce_with_eligibility_and_cap(budget, cap):
    cfg = settings()
    offer_by_id(cfg, "intensive")["eligibility"] = {"Contract": ["Month-to-month"]}
    cfg["campaign"]["max_contact_share"] = cap
    data = scores()
    target, stats = campaign(data, budget, cfg, cfg["offers"])
    options = offer_options(value_customers(data, cfg), cfg["offers"])
    options = options.loc[options.expected_net_value.gt(0)]
    max_contacts = contact_limit(len(data), cap)
    assert stats["expected_net_value"] == pytest.approx(brute_force(options, budget, max_contacts))
    assert stats["cost"] <= budget and target.customer_id.is_unique
    picked = target.loc[target.selected]
    assert (picked.expected_net_value > 0).all()
    assert not ((picked.offer_id == "intensive") & (picked.Contract != "Month-to-month")).any()
    assert max_contacts is None or len(picked) <= max_contacts


def test_contact_cap_limits_single_offer_list():
    cfg = settings()
    cfg["campaign"]["max_contact_share"] = 0.30
    data = pd.concat([scores()] * 2, ignore_index=True).assign(customer_id=list("abcdef"))
    _, stats = campaign(data, 1000, cfg)
    assert stats["selected_count"] == contact_limit(6, 0.30) == 2
    assert contact_limit(3, 0.30) == 1 and contact_limit(1409, 0.30) == 423


def test_missing_eligibility_column_raises():
    cfg = settings()
    offer_by_id(cfg, "standard")["eligibility"] = {"PaymentMethod": ["Electronic check"]}
    with pytest.raises(ValueError, match="PaymentMethod"):
        campaign(scores(), 22, cfg)


def test_solver_fallback(monkeypatch):
    monkeypatch.setattr("telco_retention.business.milp", lambda *a, **k: SimpleNamespace(x=None, status=1))
    cfg = settings()
    target, stats = campaign(scores(), 55, cfg, cfg["offers"])
    assert stats["solver"]["status"] == "heuristic_fallback"
    assert stats["cost"] <= 55 and target.customer_id.is_unique


def test_invalid_solver_incumbent_falls_back(monkeypatch):
    monkeypatch.setattr("telco_retention.business.milp", lambda c, **k: SimpleNamespace(x=np.full(len(c), .4), status=1))
    cfg = settings()
    _, stats = campaign(scores(), 55, cfg, cfg["offers"])
    assert stats["solver"]["status"] == "heuristic_fallback"


def test_fixed_vs_retarget():
    cfg = settings()
    initial, _ = campaign(scores(), 22, cfg)
    offer = {**default_offer(cfg), "offer_cost": 100}
    fixed, fs = fixed_campaign(scores(), initial, 22, cfg, offer)
    new, ns = campaign(scores(), 22, cfg, [offer])
    assert fixed.selected.sum() == 1 and not fs["budget_feasible"]
    assert new.selected.sum() == 0 and ns["cost"] <= 22


def test_threshold_coverage():
    _, stats = campaign(scores(), 100, settings(), thresholds={"risk": .7, "value": 250})
    assert stats["high_risk_high_value_count"] == 1
    assert stats["high_risk_high_value_coverage"] == 1


@pytest.mark.parametrize("budget", [-1, np.inf, np.nan])
def test_invalid_budget(budget):
    with pytest.raises(ValueError):
        campaign(scores(), budget, settings())


def test_cost_and_value_monotonic():
    cfg = settings()
    a, _ = campaign(scores(), 100, cfg)
    offer_by_id(cfg, "standard")["offer_cost"] += 10
    b, _ = campaign(scores(), 100, cfg)
    assert np.allclose(b.expected_net_value, a.expected_net_value - 10)
    cfg["value"]["margin"] = .5
    assert np.allclose(value_customers(scores(), cfg).customer_value, 600)


def test_csv_totals():
    from io import StringIO
    target, stats = campaign(scores(), 44, settings())
    restored = pd.read_csv(StringIO(target.to_csv(index=False)))
    selected = restored.loc[restored.selected]
    assert selected.total_cost.sum() == pytest.approx(stats["cost"])
    assert selected.expected_net_value.sum() == pytest.approx(stats["expected_net_value"])


def test_risk_positive_ev_baseline():
    data = scores()
    data.loc[0, ["churn_probability", "MonthlyCharges"]] = [.99, 1]
    raw, _ = campaign(data, 22, settings(), strategy="risk")
    filtered, _ = campaign(data, 22, settings(), strategy="risk_positive_ev")
    assert raw.loc[raw.selected, "customer_id"].tolist() == ["a"]
    assert filtered.loc[filtered.selected, "customer_id"].tolist() == ["b"]
    assert filtered.loc[filtered.selected, "expected_net_value"].gt(0).all()


def test_fixed_multi_offer_keeps_assignments():
    cfg = settings()
    data = scores()
    data.tenure = [3, 20, 40]
    reference, _ = campaign(data, 100, cfg, cfg["offers"])
    changed = deepcopy(cfg["offers"])
    for offer in changed:
        offer["offer_cost"] *= 2
    fixed, stats = fixed_campaign(data, reference, 100, cfg, changed)
    a, b = reference.sort_values("customer_id"), fixed.sort_values("customer_id")
    assert a.offer_id.tolist() == b.offer_id.tolist() and a.selected.tolist() == b.selected.tolist()
    np.testing.assert_allclose(b.expected_net_value, a.expected_net_value - a.offer_cost)
    assert stats["cost"] == pytest.approx(b.loc[b.selected, "total_cost"].sum())


def test_scenario_id_ignores_int_float_spelling():
    cfg = settings()
    _, a = campaign(scores(), 22, cfg)
    cfg["value"]["base_horizon_months"] = 12.0
    cfg["value"]["tenure_factors"] = {k: float(v) for k, v in cfg["value"]["tenure_factors"].items()}
    _, b = campaign(scores(), 22.0, cfg)
    assert a["scenario_id"] == b["scenario_id"]
    cfg["value"]["margin"] = .26
    assert campaign(scores(), 22, cfg)[1]["scenario_id"] != a["scenario_id"]


def test_customer_explanation_contains_economics():
    target, _ = campaign(scores().iloc[:1], 22, settings())
    assert "EV 2.00 USD" in target.decision_detail.iloc[0]
    assert "break-even save rate" in target.decision_detail.iloc[0]
