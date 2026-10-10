import joblib
import numpy as np
import pandas as pd
import pytest
from telco_retention.common import ROOT, latest_run, read_json
from telco_retention.modeling import score_frame, choose_model, calibration_stats, gains_table, precision_at_k
from telco_retention.data import features, validate


def test_model_roundtrip_and_probability(tmp_path):
    bundle = joblib.load(latest_run() / "model.joblib")
    df = pd.read_csv(ROOT / "data/processed/customers.csv").query("split == 'test'").head(20)
    expected = score_frame(df, bundle).churn_probability.to_numpy()
    joblib.dump(bundle, tmp_path / "model.joblib")
    actual = score_frame(df, joblib.load(tmp_path / "model.joblib")).churn_probability.to_numpy()
    assert np.isfinite(actual).all() and ((actual >= 0) & (actual <= 1)).all()
    np.testing.assert_allclose(expected, actual, rtol=0, atol=1e-12)


def test_model_does_not_use_label():
    df = pd.read_csv(ROOT / "data/processed/customers.csv").head(10)
    a = score_frame(df).churn_probability
    df.Churn = "Yes"
    df.churn = 1
    b = score_frame(df).churn_probability
    np.testing.assert_array_equal(a, b)


def test_numeric_medians_only_train():
    df = pd.read_csv(ROOT / "data/processed/customers.csv")
    bundle = joblib.load(latest_run() / "model.joblib")
    for col, value in bundle["metadata"]["numeric_medians"].items():
        assert value == df.loc[df.split.eq("train"), col].median()
    fitted = bundle["model"].calibrated_classifiers_[0].estimator
    imputer = fitted.named_steps["prep"].named_transformers_["num"].named_steps["impute"]
    numeric = features(df.loc[df.split.eq("train")]).select_dtypes(include="number")
    np.testing.assert_allclose(imputer.statistics_, numeric.median().values)


def test_uploaded_missing_numeric_uses_training_median():
    df = pd.read_csv(ROOT / "data/examples/customers_unlabeled.csv").head(1)
    df.loc[0, "MonthlyCharges"] = np.nan
    clean, _ = validate(df)
    scored = score_frame(clean)
    assert scored.MonthlyCharges.iloc[0] == read_json(latest_run() / "manifest.json")["numeric_medians"]["MonthlyCharges"]


def test_selection_rule():
    frame = pd.DataFrame([
        {"model": "logistic", "variant": "calibrated", "average_precision": .66, "brier": .132},
        {"model": "random_forest", "variant": "calibrated", "average_precision": .665, "brier": .131},
        {"model": "xgboost", "variant": "calibrated", "average_precision": .667, "brier": .1305},
    ])
    assert choose_model(frame) == "logistic"


def test_uploaded_ids_not_assumed_unseen():
    source = pd.read_csv(latest_run() / "customers.csv")
    sample = source.groupby("split").head(1)
    expected = dict(zip(sample.customerID, sample.split))
    from telco_retention.data import SCHEMA
    clean, _ = validate(sample[SCHEMA].reset_index(drop=True))
    scored = score_frame(clean)
    assert scored.set_index("customerID").reference_split.to_dict() == expected
    assert "uploaded_matches_train_do_not_evaluate" in scored.prediction_origin.values
    clean.customerID = [f"NEW-ID-{i}" for i in range(len(clean))]
    assert set(score_frame(clean).prediction_origin) == {"uploaded_not_in_reference"}


def test_test_metrics_and_shap_consistency():
    run = latest_run()
    scores = pd.read_csv(run / "scorecard.csv")
    assert set(scores.loc[scores.split.eq("train"), "prediction_origin"]) == {"in_sample_do_not_evaluate"}
    local = pd.read_csv(run / "shap_local.csv")
    values = local.drop(columns=["customer_id", "base_value", "raw_probability"]).sum(axis=1) + local.base_value
    np.testing.assert_allclose(1 / (1 + np.exp(-values)), local.raw_probability, atol=1e-6)
    assert len(local) == 200
    metrics = pd.read_csv(run / "test_metrics.csv")
    assert {"ece", "calibration_slope", "calibration_intercept"} <= set(metrics.columns)
    assert set(metrics.model) == {"dummy_raw", "logistic_raw", "logistic_calibrated", "random_forest_raw", "random_forest_calibrated", "xgboost_raw", "xgboost_calibrated"}


def test_calibration_stats_on_calibrated_and_miscalibrated_data():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.02, 0.98, 20000)
    y = rng.random(20000) < p
    good = calibration_stats(y, p)
    assert good["ece"] < 0.02 and good["calibration_slope"] == pytest.approx(1, abs=0.08) and abs(good["calibration_intercept"]) < 0.05
    overconfident = calibration_stats(y, np.clip(p ** 0.5, 0, 1))
    assert overconfident["ece"] > good["ece"] and overconfident["calibration_intercept"] < 0
    assert calibration_stats([1, 1, 1], [.2, .5, .7])["ece"] is None
    assert calibration_stats([0, 1, 0, 1], [.3] * 4)["calibration_slope"] is None


def test_gains_and_precision_at_k():
    y = np.array([1, 1, 0, 1, 0, 0, 0, 0, 0, 1])
    p = np.linspace(1, 0.1, 10)
    gains = gains_table(y, p, n_bins=5)
    assert gains.customers.sum() == 10 and gains.churners.sum() == 4
    assert gains.cumulative_churner_capture.iloc[-1] == pytest.approx(1)
    assert gains.lift.iloc[0] == pytest.approx(1.0 / 0.4)
    top = precision_at_k(y, p, shares=(0.2,)).iloc[0]
    assert top.customers == 2 and top.precision == 1 and top.recall == 0.5
