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
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.inspection import permutation_importance
from scipy.optimize import brentq
from xgboost import XGBClassifier
from .common import ROOT, config, digest, latest_run, now, read_json, save_csv, write_json
from .data import features, prepare, tenure_segment, BINARY, DOMAINS, NUMERIC, OPTIONAL, REFERENCE_LEVELS, SCHEMA, SEGMENTS, SERVICES

# Candidate feature sets: (continuous, categorical); every set also uses the BINARY flags.
FEATURE_SETS = {
    "all inputs": (NUMERIC, ["InternetService", "Contract", "PaymentMethod"]),
    "without TotalCharges": (["tenure", "MonthlyCharges"], ["InternetService", "Contract", "PaymentMethod"]),
    "without TotalCharges, with tenure band": (["tenure", "MonthlyCharges"], ["InternetService", "Contract", "PaymentMethod", "tenure_band"]),
    "all inputs with tenure band": (NUMERIC, ["InternetService", "Contract", "PaymentMethod", "tenure_band"]),
}
FEATURE_RULE = "Full-rank sets only; cross-validated AP within one standard error of the best; then the fewest encoded columns"


def calibration_stats(y, p, n_bins=10):
    """ECE on quantile bins, calibration slope and calibration-in-the-large intercept."""
    y, p = np.asarray(y, dtype=float), np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    if len(np.unique(y)) < 2:
        return {"ece": None, "calibration_slope": None, "calibration_intercept": None}
    bins = pd.qcut(pd.Series(p).rank(method="first"), min(n_bins, len(p)), labels=False)
    gaps = pd.DataFrame({"y": y, "p": p, "bin": bins}).groupby("bin").agg(y=("y", "mean"), p=("p", "mean"), n=("y", "size"))
    ece = float((gaps.n * (gaps.y - gaps.p).abs()).sum() / len(y))
    logit = np.log(p / (1 - p))
    # A constant predictor (e.g. the prior-only baseline) has no defined slope.
    slope = float(LogisticRegression(penalty=None, max_iter=1000).fit(logit.reshape(-1, 1), y).coef_[0, 0]) if logit.std() > 1e-8 else None
    intercept = float(brentq(lambda a: (1 / (1 + np.exp(-(a + logit)))).mean() - y.mean(), -10, 10))
    return {"ece": ece, "calibration_slope": slope, "calibration_intercept": intercept}


def metrics(y, p, threshold=0.5):
    hard = np.asarray(p) >= threshold
    return {"average_precision": average_precision_score(y, p), "roc_auc": roc_auc_score(y, p) if len(np.unique(y)) > 1 else None,
            "brier": brier_score_loss(y, p), "log_loss": log_loss(y, p, labels=[0, 1]),
            "precision": precision_score(y, hard, zero_division=0), "recall": recall_score(y, hard, zero_division=0), "f1": f1_score(y, hard, zero_division=0),
            **calibration_stats(y, p)}


def gains_table(y, p, n_bins=10):
    """Deciles by predicted risk: churn rate, lift and cumulative share of churners captured."""
    frame = pd.DataFrame({"y": np.asarray(y), "p": np.asarray(p)}).sort_values("p", ascending=False, kind="mergesort").reset_index(drop=True)
    frame["decile"] = np.arange(len(frame)) * n_bins // len(frame) + 1
    out = frame.groupby("decile").agg(customers=("y", "size"), churners=("y", "sum"), mean_probability=("p", "mean"), min_probability=("p", "min")).reset_index()
    out["churn_rate"] = out.churners / out.customers
    out["lift"] = out.churn_rate / frame.y.mean()
    out["cumulative_customer_share"] = out.customers.cumsum() / len(frame)
    out["cumulative_churner_capture"] = out.churners.cumsum() / frame.y.sum()
    return out


def precision_at_k(y, p, shares=(0.05, 0.10, 0.20, 0.30)):
    order = np.argsort(-np.asarray(p), kind="mergesort")
    y = np.asarray(y)[order]
    rows = []
    for share in shares:
        k = max(1, int(round(share * len(y))))
        rows.append({"contact_share": share, "customers": k, "precision": y[:k].mean(), "recall": y[:k].sum() / y.sum(), "lift": y[:k].mean() / y.mean()})
    return pd.DataFrame(rows)


def preprocessing(continuous, categorical):
    """Scale continuous inputs, pass 0/1 flags through, and code categoricals against their reference level."""
    levels = {**DOMAINS, "tenure_band": SEGMENTS}
    return ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), list(continuous)),
        ("flag", "passthrough", BINARY),
        ("cat", OneHotEncoder(categories=[levels[c] for c in categorical], drop=[REFERENCE_LEVELS[c] for c in categorical], sparse_output=False), list(categorical)),
    ], remainder="drop", verbose_feature_names_out=False)


def _previous_design(df):
    """The first feature design (raw columns, four derived columns, every level one-hot coded); kept only as a reference row."""
    out = df[[c for c in SCHEMA if c not in OPTIONAL | {"customerID"}]].copy()
    out["tenure_band"] = tenure_segment(out.tenure).astype(object)
    out["addon_count"] = out[SERVICES].eq("Yes").sum(axis=1)
    out["monthly_contract"] = out.Contract.eq("Month-to-month").astype(int)
    out["autopay"] = out.PaymentMethod.str.contains("automatic", regex=False).astype(int)
    nums = out.select_dtypes(include="number").columns.tolist()
    prep = ColumnTransformer([("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), nums),
                              ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), [c for c in out if c not in nums])])
    return out, prep


def feature_ablation(train_df, y, folds, seed):
    """Cross-validated logistic regression on train for each candidate feature set; returns the table and the chosen set."""
    candidates = {name: (features(train_df), preprocessing(*spec)) for name, spec in FEATURE_SETS.items()}
    candidates["previous design (reference)"] = _previous_design(train_df)
    rows = []
    for name, (X, prep) in candidates.items():
        best = None
        for C in [0.01, 0.1, 1, 10]:
            scores = cross_val_score(Pipeline([("prep", prep), ("model", LogisticRegression(C=C, max_iter=3000, random_state=seed))]), X, y, cv=folds, scoring="average_precision")
            if best is None or scores.mean() > best[1]:
                best = (C, scores.mean(), scores.std(ddof=1) / np.sqrt(len(scores)))
        encoded = prep.fit_transform(X)
        rank = int(np.linalg.matrix_rank(encoded))
        rows.append({"feature_set": name, "best_C": best[0], "cv_average_precision": best[1], "cv_standard_error": best[2],
                     "encoded_columns": encoded.shape[1], "matrix_rank": rank, "full_rank": rank == encoded.shape[1]})
    table = pd.DataFrame(rows)
    top = table.loc[table.cv_average_precision.idxmax()]
    table["within_one_se"] = table.cv_average_precision >= top.cv_average_precision - top.cv_standard_error
    table["eligible"] = table.within_one_se & table.full_rank & table.feature_set.isin(FEATURE_SETS)
    chosen = table.loc[table.eligible].sort_values("encoded_columns", kind="mergesort").iloc[0].feature_set
    table["selected"] = table.feature_set.eq(chosen)
    return table, chosen


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
    train_df, val_df = df.loc[df.split.eq("train")], df.loc[df.split.eq("validation")]
    y, yv = train_df.churn, val_df.churn
    source = read_json(ROOT / "data/raw/source.json")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + source["sha256"][:8]
    run = ROOT / "artifacts/runs" / run_id
    run.mkdir(parents=True)
    save_csv(df, run / "customers.csv")
    write_json(run / "dataset_source.json", source)
    write_json(run / "data_quality.json", read_json(ROOT / "data/processed/quality.json"))
    write_json(run / "dataset_metadata.json", read_json(ROOT / "data/raw/source-metadata.json"))
    write_json(run / "extended_source.json", read_json(ROOT / "data/raw/source_extended.json"))
    write_json(run / "extended_join.json", read_json(ROOT / "data/processed/extended_join.json"))
    save_csv(pd.read_csv(ROOT / "data/processed/customer_context.csv"), run / "customer_context.csv")
    folds = StratifiedKFold(cfg["cv_folds"], shuffle=True, random_state=seed)
    print("Feature design: cross-validated ablation on train", flush=True)
    ablation, feature_set = feature_ablation(train_df, y, folds, seed)
    save_csv(ablation, run / "feature_ablation.csv")
    continuous, categorical = FEATURE_SETS[feature_set]
    columns = [*continuous, *BINARY, *categorical]
    X, Xv = features(train_df)[columns], features(val_df)[columns]
    specs = {
        "logistic": (LogisticRegression(max_iter=2000, random_state=seed), {"model__C": [0.01, 0.1, 1, 10], "model__class_weight": [None, "balanced"]}),
        "random_forest": (RandomForestClassifier(random_state=seed, n_jobs=2), {"model__n_estimators": [150, 300], "model__max_depth": [5, 10, None], "model__min_samples_leaf": [2, 5, 15], "model__class_weight": [None, "balanced"]}),
        "xgboost": (XGBClassifier(random_state=seed, n_jobs=2, eval_metric="logloss", tree_method="hist"), {"model__n_estimators": [100, 200, 300], "model__max_depth": [2, 3, 5], "model__learning_rate": [0.03, 0.08], "model__subsample": [0.8, 1.0], "model__colsample_bytree": [0.8, 1.0], "model__reg_lambda": [1, 5, 10]}),
    }
    models, best_params, val_probs = {}, {}, {}
    dummy = Pipeline([("prep", preprocessing(continuous, categorical)), ("model", DummyClassifier(strategy="prior"))]).fit(X, y)
    models["dummy_raw"] = dummy
    val_probs["dummy", "raw"] = dummy.predict_proba(Xv)[:, 1]
    for name, (estimator, params) in specs.items():
        print(f"Training {name}: CV search", flush=True)
        start = time.perf_counter()
        pipe = Pipeline([("prep", preprocessing(continuous, categorical)), ("model", estimator)])
        search = RandomizedSearchCV(pipe, params, n_iter=min(8 if name == "logistic" else cfg["search_iterations"], int(np.prod([len(v) for v in params.values()]))), scoring="average_precision", cv=folds, n_jobs=2, random_state=seed, refit=True, error_score="raise")
        search.fit(X, y)
        raw = search.best_estimator_
        calibrated = CalibratedClassifierCV(raw, method="sigmoid", cv=folds, ensemble=False, n_jobs=2)
        calibrated.fit(X, y)
        for variant, model in [("raw", raw), ("calibrated", calibrated)]:
            models[f"{name}_{variant}"] = model
            val_probs[name, variant] = model.predict_proba(Xv)[:, 1]
        best_params[name] = {"params": search.best_params_, "cv_average_precision": search.best_score_, "seconds": time.perf_counter() - start}
        save_csv(pd.DataFrame(search.cv_results_), run / f"cv_{name}.csv")
        print(f"Completed {name} ({time.perf_counter() - start:.1f}s)", flush=True)
    # Selection uses threshold-free metrics; the table is then reported at the chosen threshold for every candidate.
    winner = choose_model(pd.DataFrame([{"model": m, "variant": v, **metrics(yv, p)} for (m, v), p in val_probs.items()]))
    model = models[f"{winner}_calibrated"]
    thresholds = pd.DataFrame([{"threshold": float(t), **metrics(yv, model.predict_proba(Xv)[:, 1], t)} for t in np.arange(0.05, 1, 0.05)])
    best_threshold = float(thresholds.sort_values(["f1", "threshold"], ascending=[False, True]).iloc[0].threshold)
    validation = pd.DataFrame([{"model": m, "variant": v, "threshold": best_threshold, **metrics(yv, p, best_threshold)} for (m, v), p in val_probs.items()])
    encoded = preprocessing(continuous, categorical).fit(X).get_feature_names_out()
    metadata = {"run_id": run_id, "selected_model": winner, "threshold": best_threshold, "seed": seed, "created_at": now(), "source_sha256": source["sha256"], "config": cfg, "selection_rule": "AP within 0.01 of best calibrated candidate; Brier within 0.002 of best; prefer simpler", "split_counts": df.split.value_counts().to_dict(),
                "feature_set": feature_set, "feature_rule": FEATURE_RULE, "feature_columns": columns, "continuous_features": list(continuous), "binary_features": BINARY, "categorical_features": list(categorical),
                "reference_levels": {c: REFERENCE_LEVELS[c] for c in categorical}, "encoded_features": list(encoded), "numeric_medians": df.loc[df.split.eq("train"), NUMERIC].median().to_dict(), "best_parameters": best_params, "python": platform.python_version(), "dependencies": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}, "code_sha256": {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in (ROOT / "src").rglob("*.py")}}
    joblib.dump({"model": model, "metadata": metadata, "reference_splits": df.set_index("customerID").split.to_dict()}, run / "model.joblib")
    joblib.dump(models, run / "candidates.joblib")
    save_csv(validation, run / "validation_metrics.csv")
    save_csv(thresholds, run / "threshold_analysis.csv")
    write_json(run / "manifest.json", metadata)
    write_json(ROOT / "artifacts/latest.json", {"run_id": run_id})
    print(f"Selected {winner}; run={run_id}", flush=True)
    return run


def score_frame(df, bundle=None, origin="uploaded_unverified"):
    bundle = bundle or joblib.load(latest_run() / "model.joblib")
    out = df.copy()
    out["churn_probability"] = bundle["model"].predict_proba(features(df)[bundle["metadata"]["feature_columns"]])[:, 1]
    for col, median in bundle["metadata"]["numeric_medians"].items():
        out[col] = out[col].fillna(median)
    out["customer_id"] = out.customerID
    out["model_version"] = bundle["metadata"]["run_id"]
    out["prediction_origin"] = origin
    if "split" in out:
        out["prediction_origin"] = out.split.map({"train": "in_sample_do_not_evaluate", "validation": "selection_holdout", "test": "untouched_test"})
    else:
        reference = bundle.get("reference_splits")
        # Backward compatibility for locally produced bundles without an ID registry.
        path = ROOT / "artifacts/runs" / bundle["metadata"]["run_id"] / "customers.csv"
        if reference is None and path.exists():
            reference = pd.read_csv(path, usecols=["customerID", "split"], dtype={"customerID": str}).set_index("customerID").split.to_dict()
        if reference is not None:
            out["reference_split"] = out.customerID.map(reference).fillna("not_in_reference")
            out["prediction_origin"] = out.reference_split.map({
                "train": "uploaded_matches_train_do_not_evaluate", "validation": "uploaded_matches_validation",
                "test": "uploaded_matches_test", "not_in_reference": "uploaded_not_in_reference",
            })
    out["risk_band"] = pd.cut(out.churn_probability, [-np.inf, 0.25, 0.5, 1], labels=["low", "medium", "high"]).astype(str)
    return out


OUTCOMES = {"tp": "Flagged and left (true positive)", "fp": "Flagged but stayed (false positive)",
            "fn": "Missed and left (false negative)", "tn": "Not flagged and stayed (true negative)"}


def error_profiles(scored, threshold):
    """Who the model gets right and wrong at the threshold: size, risk and profile of each outcome group."""
    flagged, left = scored.churn_probability >= threshold, scored.churn.eq(1)
    outcome = np.select([flagged & left, flagged & ~left, ~flagged & left], [OUTCOMES["tp"], OUTCOMES["fp"], OUTCOMES["fn"]], OUTCOMES["tn"])
    rows = []
    for key, label in OUTCOMES.items():
        part = scored.loc[outcome == label]
        rows.append({"outcome": label, "key": key, "customers": len(part), "share": len(part) / len(scored),
                     "mean_probability": part.churn_probability.mean(), "mean_tenure": part.tenure.mean(), "median_monthly_charges": part.MonthlyCharges.median(),
                     "fibre_share": part.InternetService.eq("Fiber optic").mean(), "month_to_month_share": part.Contract.eq("Month-to-month").mean(),
                     "echeck_share": part.PaymentMethod.eq("Electronic check").mean(), "senior_share": part.SeniorCitizen.astype(str).eq("1").mean()})
    return pd.DataFrame(rows)


def deployed_linear(bundle):
    """Deployed logistic model as one linear score: logit = slope x (intercept + coef . x) + offset, with the sigmoid calibration folded in."""
    if bundle["metadata"]["selected_model"] != "logistic":
        return None
    calibrated = bundle["model"].calibrated_classifiers_[0]
    sigmoid = calibrated.calibrators[0]  # predicts expit(-(a * f + b))
    return calibrated.estimator, -float(sigmoid.a_), -float(sigmoid.b_)


def _terms(bundle):
    pipe, slope, offset = deployed_linear(bundle)
    prep, lr = pipe.named_steps["prep"], pipe.named_steps["model"]
    meta = bundle["metadata"]
    scaler = prep.named_transformers_["num"].named_steps["scale"]
    cont = meta["continuous_features"]
    return (dict(zip(prep.get_feature_names_out(), slope * lr.coef_[0])), slope * float(lr.intercept_[0]) + offset,
            dict(zip(cont, scaler.mean_)), dict(zip(cont, scaler.scale_)))


def odds_ratios(bundle, cfg):
    """Odds ratios of the deployed model: continuous inputs per natural step, flags yes vs no, categories vs their reference."""
    if deployed_linear(bundle) is None:
        return pd.DataFrame()
    beta, _, _, sd = _terms(bundle)
    meta, steps = bundle["metadata"], cfg["scorecard"]["odds_ratio_steps"]
    rows = []
    for term, b in beta.items():
        if term in meta["continuous_features"]:
            step = steps.get(term, sd[term])
            unit = "months" if term == "tenure" else "USD a month"
            rows.append({"term": term, "variable": term, "comparison": f"+{step:g} {unit}", "coefficient": b / sd[term] * step})
        elif term in meta["binary_features"]:
            rows.append({"term": term, "variable": term, "comparison": "Yes vs No", "coefficient": b})
        else:
            variable, level = term.split("_", 1)
            rows.append({"term": term, "variable": variable, "comparison": f"{level} vs {meta['reference_levels'][variable]}", "coefficient": b})
    out = pd.DataFrame(rows)
    out["odds_ratio"] = np.exp(out.coefficient)
    return out.sort_values("odds_ratio", ascending=False).reset_index(drop=True)


def _band_label(interval, unit):
    low, high = interval.left, interval.right
    if unit == "months":
        return f"{0 if not np.isfinite(low) else int(low) + 1}+ months" if not np.isfinite(high) else f"{0 if not np.isfinite(low) else int(low) + 1}-{int(high)} months"
    if not np.isfinite(low):
        return f"up to ${high:g}"
    return f"over ${low:g}" if not np.isfinite(high) else f"${low:g}-{high:g}"


def points_scorecard(bundle, train_df, cfg):
    """Points card for the call centre: each attribute adds whole points, and the total maps back to a churn probability."""
    if deployed_linear(bundle) is None:
        return pd.DataFrame(), {}
    sc, meta = cfg["scorecard"], bundle["metadata"]
    factor = sc["pdo"] / np.log(2)
    beta, intercept, mu, sd = _terms(bundle)
    intercept -= sum(beta[c] * mu[c] / sd[c] for c in meta["continuous_features"])  # work on raw units
    levels = {**DOMAINS, "tenure_band": SEGMENTS}
    rows = []
    for c in meta["continuous_features"]:
        bands = pd.cut(train_df[c], [-np.inf, *sc["bands"][c], np.inf])
        for interval, part in train_df[c].groupby(bands, observed=False):
            rows.append({"characteristic": c, "attribute": _band_label(interval, "months" if c == "tenure" else "usd"), "lower": interval.left, "upper": interval.right,
                         "representative": float(part.median()), "raw": factor * beta[c] / sd[c] * float(part.median())})
    for c in meta["binary_features"]:
        rows += [{"characteristic": c, "attribute": "Yes", "raw": factor * beta[c]}, {"characteristic": c, "attribute": "No", "raw": 0.0}]
    for c in meta["categorical_features"]:
        rows += [{"characteristic": c, "attribute": level, "raw": factor * beta.get(f"{c}_{level}", 0.0)} for level in levels[c]]
    card = pd.DataFrame(rows)
    shift = card.groupby("characteristic", sort=False).raw.min()
    card["points"] = (card.raw - card.characteristic.map(shift)).round().astype(int)
    base = int(round(sc["anchor_score"] + factor * intercept + shift.sum()))
    return card, {"anchor_score": sc["anchor_score"], "pdo": sc["pdo"], "base_points": base, "factor": factor}


def apply_scorecard(card, meta, df):
    """Score customers with the points card; returns points and the probability they imply."""
    total = pd.Series(meta["base_points"], index=df.index, dtype=float)
    X = features(df)
    for c, part in card.groupby("characteristic", sort=False):
        if part.lower.notna().any():
            edges = [-np.inf, *part.upper.iloc[:-1], np.inf]
            total += pd.cut(df[c], edges, labels=False).map(dict(enumerate(part.points))).astype(float)
        elif set(part.attribute) == {"Yes", "No"}:
            total += np.where(X[c].eq(1), part.set_index("attribute").points["Yes"], part.set_index("attribute").points["No"])
        else:
            total += X[c].map(part.set_index("attribute").points).astype(float)
    probability = 1 / (1 + np.exp(-(total - meta["anchor_score"]) / meta["factor"]))
    return total, probability


def scorecard_outputs(run, bundle, df, cfg):
    """Odds ratios, points card, score bands and how closely the card reproduces the model on test."""
    ratios = odds_ratios(bundle, cfg)
    card, meta = points_scorecard(bundle, df.loc[df.split.eq("train")], cfg)
    save_csv(ratios, run / "odds_ratios.csv")
    save_csv(card, run / "scorecard_points.csv")
    if card.empty:
        write_json(run / "scorecard_meta.json", {"available": False, "reason": "the deployed model is not logistic regression"})
        return
    test = df.loc[df.split.eq("test")]
    points, implied = apply_scorecard(card, meta, test)
    model_p = bundle["model"].predict_proba(features(test)[bundle["metadata"]["feature_columns"]])[:, 1]
    edges = [-np.inf, *[meta["anchor_score"] + k * meta["pdo"] for k in range(-3, 3)], np.inf]
    bands = pd.cut(points, edges)
    table = pd.DataFrame({"band": bands, "points": points, "card_probability": implied, "model_probability": model_p, "churn": test.churn.to_numpy()})
    summary = table.groupby("band", observed=False).agg(customers=("churn", "size"), mean_points=("points", "mean"), card_probability=("card_probability", "mean"),
                                                         model_probability=("model_probability", "mean"), observed_churn=("churn", "mean")).reset_index()
    summary["band"] = [f"up to {int(i.right)}" if not np.isfinite(i.left) else f"over {int(i.left)}" if not np.isfinite(i.right) else f"{int(i.left) + 1}-{int(i.right)}" for i in summary.band]
    save_csv(summary, run / "scorecard_bands.csv")
    gap = np.abs(implied - model_p)
    val = df.loc[df.split.eq("validation")]
    val_gap = np.abs(apply_scorecard(card, meta, val)[1] - bundle["model"].predict_proba(features(val)[bundle["metadata"]["feature_columns"]])[:, 1])
    write_json(run / "scorecard_meta.json", {"available": True, **meta, "population": "test", "mean_abs_probability_gap": float(gap.mean()), "max_abs_probability_gap": float(gap.max()),
                                             "validation_mean_abs_probability_gap": float(val_gap.mean()),
                                             "card_roc_auc": float(roc_auc_score(test.churn, points)), "model_roc_auc": float(roc_auc_score(test.churn, model_p)),
                                             "score_min": float(points.min()), "score_max": float(points.max())})


def evaluate(run=None):
    run = run or latest_run()
    df = pd.read_csv(run / "customers.csv")
    bundle = joblib.load(run / "model.joblib")
    models = joblib.load(run / "candidates.joblib")
    test = df.loc[df.split.eq("test")]
    columns = bundle["metadata"]["feature_columns"]
    X, y = features(test)[columns], test.churn.to_numpy()
    threshold = bundle["metadata"]["threshold"]
    rows, probabilities = [], {}
    for name, model in models.items():
        p = model.predict_proba(X)[:, 1]
        probabilities[name] = p
        rows.append({"model": name, "threshold": threshold, **metrics(y, p, threshold)})
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
    save_csv(gains_table(y, p), run / "gains_test.csv")
    save_csv(precision_at_k(y, p), run / "precision_at_k.csv")
    diagnostic = []
    tested = scores.loc[scores.split.eq("test")].assign(tenure_segment=lambda d: tenure_segment(d.tenure).astype(str))
    for col in ["tenure_segment", "Contract", "InternetService", "PaymentMethod", "gender", "SeniorCitizen"]:
        for group, part in tested.groupby(col):
            diagnostic.append({"attribute": col, "group": group, "n": len(part), "small_sample": len(part) < 50, **metrics(part.churn, part.churn_probability, threshold)})
    save_csv(pd.DataFrame(diagnostic), run / "segment_errors.csv")
    save_csv(error_profiles(tested, threshold), run / "error_profiles.csv")
    scorecard_outputs(run, bundle, df, cfg)
    explain(run, models, df, columns, cfg["seed"])
    return run


def explain(run, models, df, columns, seed=42):
    # Explain validation only, and explicitly explain the raw classifiers.
    val = df.loc[df.split.eq("validation")]
    X, y = features(val)[columns], val.churn
    lr = models["logistic_raw"]
    save_csv(pd.DataFrame({"feature": lr.named_steps["prep"].get_feature_names_out(), "coefficient": lr.named_steps["model"].coef_[0]}).sort_values("coefficient"), run / "logistic_coefficients.csv")
    for name in ["random_forest", "xgboost"]:
        result = permutation_importance(models[name + "_raw"], X, y, scoring="average_precision", n_repeats=5, random_state=seed, n_jobs=2)
        save_csv(pd.DataFrame({"feature": X.columns, "importance": result.importances_mean, "std": result.importances_std}).sort_values("importance", ascending=False), run / f"permutation_{name}.csv")
    import shap
    xgb = models["xgboost_raw"]
    sample = X.sample(n=min(200, len(X)), random_state=seed)
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
