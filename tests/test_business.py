from copy import deepcopy
from itertools import product
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from telco_retention.common import config
from telco_retention.business import campaign, value_customers, offer_options, fixed_campaign


def scores():
    return pd.DataFrame({"customer_id": ["a", "b", "c"], "churn_probability": [.4, .8, .2], "tenure": [20, 20, 20], "MonthlyCharges": [100, 100, 100], "model_version": "test"})


def settings():
    cfg = config()
    cfg["margin"], cfg["base_horizon"] = .25, 12
    return cfg


def test_hand_calculation():
    target, stats = campaign(scores().iloc[:1], 22, settings())
    row = target.iloc[0]
    assert row.customer_value == 300
    assert row.expected_retained_value == pytest.approx(24)
    assert row.expected_net_value == pytest.approx(2)
    assert stats["cost"] == 22 and stats["expected_saved"] == pytest.approx(.08)
    assert stats["roi"] == pytest.approx(2 / 22)


@pytest.mark.parametrize("budget", [0, 1, 21.99])
def test_insufficient_budget(budget):
    target, stats = campaign(scores(), budget, settings())
    assert not target.selected.any() and stats["cost"] == 0 and stats["roi"] is None


@pytest.mark.parametrize("change", ["margin", "save_rate", "expensive"])
def test_no_positive_ev(change):
    cfg = settings()
    if change == "margin":
        cfg["margin"] = 0
    elif change == "save_rate":
        cfg["offers"][1]["save_rate"] = 0
    else:
        cfg["offers"][1]["offer_cost"] = 1000
    target, stats = campaign(scores(), 5000, cfg)
    assert stats["selected_count"] == 0 and stats["expected_net_value"] == 0


def test_free_offers_zero_budget():
    cfg = settings()
    cfg["offers"][1].update(offer_cost=0, contact_cost=0)
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
    assert one["precision_contacted"] is None
    assert two["precision_contacted"] == 0


def test_solver_equals_bruteforce():
    cfg = settings()
    data = scores()
    offers = cfg["offers"]
    budget = 55
    target, stats = campaign(data, budget, cfg, offers)
    opts = offer_options(value_customers(data, cfg), offers)
    best = 0
    for assignment in product([-1, 0, 1, 2], repeat=len(data)):
        cost, value = 0, 0
        for i, j in enumerate(assignment):
            if j >= 0:
                row = opts.loc[opts.customer_index.eq(i) & opts.offer_id.eq(offers[j]["offer_id"])].iloc[0]
                cost += row.total_cost
                value += row.expected_net_value
        if cost <= budget:
            best = max(best, value)
    assert stats["expected_net_value"] == pytest.approx(best)
    assert stats["cost"] <= budget and target.customer_id.is_unique
    assert (target.loc[target.selected, "expected_net_value"] > 0).all()


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
    offer = {**cfg["offers"][1], "offer_cost": 100}
    fixed, fs = fixed_campaign(scores(), initial, 22, cfg, offer)
    new, ns = campaign(scores(), 22, cfg, [offer])
    assert fixed.selected.sum() == 1 and not fs["budget_feasible"]
    assert new.selected.sum() == 0 and ns["cost"] <= 22


def test_policy_and_threshold_coverage():
    cfg = settings()
    policy = {"new": "light", "developing": "standard", "loyal": "intensive"}
    target, stats = campaign(scores(), 100, cfg, cfg["offers"], policy=policy, thresholds={"risk": .7, "value": 250})
    assert set(target.offer_id) == {"standard"}
    assert stats["high_risk_high_value_coverage"] == 1


@pytest.mark.parametrize("budget", [-1, np.inf, np.nan])
def test_invalid_budget(budget):
    with pytest.raises(ValueError):
        campaign(scores(), budget, settings())


def test_cost_and_value_monotonic():
    cfg = settings()
    a, _ = campaign(scores(), 100, cfg)
    cfg["offers"][1]["offer_cost"] += 10
    b, _ = campaign(scores(), 100, cfg)
    assert np.allclose(b.expected_net_value, a.expected_net_value - 10)
    cfg["margin"] = .5
    c = value_customers(scores(), cfg)
    assert np.allclose(c.customer_value, 600)


def test_csv_totals():
    from io import StringIO
    target, stats = campaign(scores(), 44, settings())
    restored = pd.read_csv(StringIO(target.to_csv(index=False)))
    selected = restored.loc[restored.selected]
    assert selected.total_cost.sum() == pytest.approx(stats["cost"])
    assert selected.expected_net_value.sum() == pytest.approx(stats["expected_net_value"])
