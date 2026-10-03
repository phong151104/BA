from __future__ import annotations

import platform
import importlib.metadata
import time
from datetime import datetime, timezone
import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss, log_loss, precision_score, recall_score, f1_score, confusion_matrix, precision_recall_curve, roc_curve
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.inspection import permutation_importance
from xgboost import XGBClassifier
from .common import ROOT, config, digest, latest_run, now, read_json, save_csv, write_json
from .data import features, NUMERIC, prepare


def metrics(y, p, threshold=0.5):
    hard = np.asarray(p) >= threshold
    return {"average_precision": average_precision_score(y, p), "roc_auc": roc_auc_score(y, p) if len(np.unique(y)) > 1 else None,
            "brier": brier_score_loss(y, p), "log_loss": log_loss(y, p, labels=[0, 1]),
            "precision": precision_score(y, hard, zero_division=0), "recall": recall_score(y, hard, zero_division=0), "f1": f1_score(y, hard, zero_division=0)}


def preprocessing(X):
    nums = X.select_dtypes(include="number").columns.tolist()
    cats = [c for c in X if c not in nums]
    return ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), nums),
        ("cat", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), cats),
    ], verbose_feature_names_out=False)


def choose_model(rows):
    candidates = rows.loc[rows.variant.eq("calibrated")].copy()
    candidates = candidates.loc[candidates.average_precision >= candidates.average_precision.max() - 0.01]
    candidates = candidates.loc[candidates.brier < candidates.brier.min() + 0.002]
    order = {"logistic": 0, "random_forest": 1, "xgboost": 2}
    return candidates.assign(complexity=candidates.model.map(order)).sort_values("complexity").iloc[0].model


def train():
    cfg = config()
    df = prepare()
    seed = cfg["seed"]
    X = features(df.loc[df.split.eq("train")])
    y = df.loc[df.split.eq("train"), "churn"]
    Xv, yv = features(df.loc[df.split.eq("validation")]), df.loc[df.split.eq("validation"), "churn"]
    source = read_json(ROOT / "data/raw/source.json")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + source["sha256"][:8]
    run = ROOT / "artifacts/runs" / run_id
    run.mkdir(parents=True)
    save_csv(df, run / "customers.csv")
    write_json(run / "dataset_source.json", source)
    write_json(run / "data_quality.json", read_json(ROOT / "data/processed/quality.json"))
    write_json(run / "dataset_metadata.json", read_json(ROOT / "data/raw/source-metadata.json"))
    folds = StratifiedKFold(cfg["cv_folds"], shuffle=True, random_state=seed)
    specs = {
        "logistic": (LogisticRegression(max_iter=2000, random_state=seed), {"model__C": [0.01, 0.1, 1, 10], "model__class_weight": [None, "balanced"]}),
        "random_forest": (RandomForestClassifier(random_state=seed, n_jobs=2), {"model__n_estimators": [150, 300], "model__max_depth": [5, 10, None], "model__min_samples_leaf": [2, 5, 15], "model__class_weight": [None, "balanced"]}),
        "xgboost": (XGBClassifier(random_state=seed, n_jobs=2, eval_metric="logloss", tree_method="hist"), {"model__n_estimators": [100, 200, 300], "model__max_depth": [2, 3, 5], "model__learning_rate": [0.03, 0.08], "model__subsample": [0.8, 1.0], "model__colsample_bytree": [0.8, 1.0], "model__reg_lambda": [1, 5, 10]}),
    }
    models, rows, best_params = {}, [], {}
    dummy = Pipeline([("prep", preprocessing(X)), ("model", DummyClassifier(strategy="prior"))]).fit(X, y)
    models["dummy_raw"] = dummy
    rows.append({"model": "dummy", "variant": "raw", **metrics(yv, dummy.predict_proba(Xv)[:, 1])})
    for name, (estimator, params) in specs.items():
        print(f"Training {name}: CV search", flush=True)
        start = time.perf_counter()
        pipe = Pipeline([("prep", preprocessing(X)), ("model", estimator)])
        search = RandomizedSearchCV(pipe, params, n_iter=min(8 if name == "logistic" else cfg["search_iterations"], int(np.prod([len(v) for v in params.values()]))), scoring="average_precision", cv=folds, n_jobs=2, random_state=seed, refit=True, error_score="raise")
        search.fit(X, y)
        raw = search.best_estimator_
        calibrated = CalibratedClassifierCV(raw, method="sigmoid", cv=folds, ensemble=False, n_jobs=2)
        calibrated.fit(X, y)
        for variant, model in [("raw", raw), ("calibrated", calibrated)]:
            models[f"{name}_{variant}"] = model
            rows.append({"model": name, "variant": variant, **metrics(yv, model.predict_proba(Xv)[:, 1])})
        best_params[name] = {"params": search.best_params_, "cv_average_precision": search.best_score_, "seconds": time.perf_counter() - start}
        save_csv(pd.DataFrame(search.cv_results_), run / f"cv_{name}.csv")
        print(f"Completed {name} ({time.perf_counter() - start:.1f}s)", flush=True)
    validation = pd.DataFrame(rows)
    winner = choose_model(validation)
    model = models[f"{winner}_calibrated"]
    thresholds = pd.DataFrame([{"threshold": float(t), **metrics(yv, model.predict_proba(Xv)[:, 1], t)} for t in np.arange(0.05, 1, 0.05)])
    best_threshold = float(thresholds.sort_values(["f1", "threshold"], ascending=[False, True]).iloc[0].threshold)
    metadata = {"run_id": run_id, "selected_model": winner, "threshold": best_threshold, "seed": seed, "created_at": now(), "source_sha256": source["sha256"], "config": cfg, "selection_rule": "AP within 0.01 of best calibrated candidate; Brier within 0.002 of best; prefer simpler", "split_counts": df.split.value_counts().to_dict(), "feature_columns": list(X.columns), "numeric_medians": df.loc[df.split.eq("train"), NUMERIC].median().to_dict(), "best_parameters": best_params, "python": platform.python_version(), "dependencies": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}, "code_sha256": {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in (ROOT / "src").rglob("*.py")}}
    joblib.dump({"model": model, "metadata": metadata}, run / "model.joblib")
    joblib.dump(models, run / "candidates.joblib")
    save_csv(validation, run / "validation_metrics.csv")
    save_csv(thresholds, run / "threshold_analysis.csv")
    write_json(run / "manifest.json", metadata)
    write_json(ROOT / "artifacts/latest.json", {"run_id": run_id})
    print(f"Selected {winner}; run={run_id}", flush=True)
    return run


def score_frame(df, bundle=None, origin="uploaded_unseen"):
    bundle = bundle or joblib.load(latest_run() / "model.joblib")
    out = df.copy()
    out["churn_probability"] = bundle["model"].predict_proba(features(df))[:, 1]
    for col, median in bundle["metadata"]["numeric_medians"].items():
        out[col] = out[col].fillna(median)
    out["customer_id"] = out.customerID
    out["model_version"] = bundle["metadata"]["run_id"]
    out["prediction_origin"] = origin
    if "split" in out:
        out["prediction_origin"] = out.split.map({"train": "in_sample_do_not_evaluate", "validation": "selection_holdout", "test": "untouched_test"})
    out["risk_band"] = pd.cut(out.churn_probability, [-np.inf, 0.25, 0.5, 1], labels=["low", "medium", "high"]).astype(str)
    return out


def evaluate(run=None):
    run = run or latest_run()
    df = pd.read_csv(run / "customers.csv")
    bundle = joblib.load(run / "model.joblib")
    models = joblib.load(run / "candidates.joblib")
    test = df.loc[df.split.eq("test")]
    X, y = features(test), test.churn.to_numpy()
    threshold = bundle["metadata"]["threshold"]
    rows, probabilities = [], {}
    for name, model in models.items():
        p = model.predict_proba(X)[:, 1]
        probabilities[name] = p
        rows.append({"model": name, **metrics(y, p, threshold)})
    save_csv(pd.DataFrame(rows), run / "test_metrics.csv")
    scores = score_frame(df, bundle)
    save_csv(scores, run / "scorecard.csv")
    p = scores.loc[scores.split.eq("test"), "churn_probability"].to_numpy()
    cfg = bundle["metadata"]["config"]
    rng = np.random.default_rng(cfg["seed"])
    boot = []
    for _ in range(cfg["bootstrap_iterations"]):
        idx = rng.integers(0, len(y), len(y))
        boot.append(metrics(y[idx], p[idx], threshold))
    bootstrap = pd.DataFrame(boot)
    intervals = pd.DataFrame({"metric": bootstrap.columns, "lower_95": bootstrap.quantile(.025).values, "upper_95": bootstrap.quantile(.975).values})
    save_csv(intervals, run / "bootstrap_intervals.csv")
    save_csv(pd.DataFrame(confusion_matrix(y, p >= threshold), columns=["pred_no", "pred_yes"]).assign(actual=["no", "yes"]), run / "confusion_matrix.csv")
    curves = []
    for name, prob in probabilities.items():
        observed, predicted = calibration_curve(y, prob, n_bins=10, strategy="quantile")
        curves.extend({"model": name, "predicted": a, "observed": b} for a, b in zip(predicted, observed))
    save_csv(pd.DataFrame(curves), run / "calibration.csv")
    precision, recall, _ = precision_recall_curve(y, p)
    save_csv(pd.DataFrame({"precision": precision, "recall": recall}), run / "pr_curve.csv")
    fpr, tpr, _ = roc_curve(y, p)
    save_csv(pd.DataFrame({"fpr": fpr, "tpr": tpr}), run / "roc_curve.csv")
    diagnostic = []
    for col in ["Contract", "InternetService", "PaymentMethod", "gender", "SeniorCitizen"]:
        for group, part in scores.loc[scores.split.eq("test")].groupby(col):
            diagnostic.append({"attribute": col, "group": group, "n": len(part), "small_sample": len(part) < 50, **metrics(part.churn, part.churn_probability, threshold)})
    save_csv(pd.DataFrame(diagnostic), run / "segment_errors.csv")
    explain(run, models, df)
    return run


def explain(run, models, df):
    # Explain validation only, and explicitly explain the raw classifiers.
    val = df.loc[df.split.eq("validation")]
    X, y = features(val), val.churn
    lr = models["logistic_raw"]
    save_csv(pd.DataFrame({"feature": lr.named_steps["prep"].get_feature_names_out(), "coefficient": lr.named_steps["model"].coef_[0]}).sort_values("coefficient"), run / "logistic_coefficients.csv")
    for name in ["random_forest", "xgboost"]:
        result = permutation_importance(models[name + "_raw"], X, y, scoring="average_precision", n_repeats=5, random_state=42, n_jobs=2)
        save_csv(pd.DataFrame({"feature": X.columns, "importance": result.importances_mean, "std": result.importances_std}).sort_values("importance", ascending=False), run / f"permutation_{name}.csv")
    import shap
    xgb = models["xgboost_raw"]
    sample = X.sample(n=min(200, len(X)), random_state=42)
    transformed = xgb.named_steps["prep"].transform(sample)
    names = xgb.named_steps["prep"].get_feature_names_out()
    # XGBoost's native TreeSHAP avoids version-specific JSON parser issues in SHAP.
    import xgboost as xgb_lib
    contributions = xgb.named_steps["model"].get_booster().predict(xgb_lib.DMatrix(transformed), pred_contribs=True)
    explanation = shap.Explanation(values=contributions[:, :-1], base_values=contributions[:, -1], data=transformed, feature_names=list(names))
    save_csv(pd.DataFrame({"feature": names, "mean_abs_shap": np.abs(explanation.values).mean(axis=0)}).sort_values("mean_abs_shap", ascending=False), run / "shap_global.csv")
    local = pd.DataFrame(explanation.values, columns=names)
    local.insert(0, "customer_id", val.loc[sample.index, "customerID"].values)
    local["base_value"] = explanation.base_values
    local["raw_probability"] = xgb.predict_proba(sample)[:, 1]
    save_csv(local, run / "shap_local.csv")
    save_csv(pd.DataFrame(transformed, columns=names).assign(customer_id=local.customer_id.values), run / "shap_feature_values.csv")
    joblib.dump(explanation, run / "shap_explanation.joblib")
    write_json(run / "explanation_metadata.json", {"model": "xgboost_raw", "scale": "log_odds", "population": "validation sample", "n": len(sample), "not_causal": True, "not_calibrated_probability_decomposition": True})
