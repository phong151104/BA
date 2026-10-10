from __future__ import annotations

import io
import zipfile
import numpy as np
import pandas as pd
import requests
from sklearn.model_selection import train_test_split
from .common import ROOT, config, digest, now, read_json, save_csv, write_json

KAGGLE = "https://www.kaggle.com/api/v1/datasets/download/blastchar/telco-customer-churn"
IBM = "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv"
METADATA_URL = "https://www.kaggle.com/api/v1/datasets/list?search=blastchar%2Ftelco-customer-churn"
NUMERIC = ["tenure", "MonthlyCharges", "TotalCharges"]
DOMAINS = {
    "gender": ["Male", "Female"], "SeniorCitizen": ["0", "1"],
    "Partner": ["Yes", "No"], "Dependents": ["Yes", "No"],
    "PhoneService": ["Yes", "No"], "MultipleLines": ["Yes", "No", "No phone service"],
    "InternetService": ["DSL", "Fiber optic", "No"],
    **{k: ["Yes", "No", "No internet service"] for k in ["OnlineSecurity", "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies"]},
    "Contract": ["Month-to-month", "One year", "Two year"], "PaperlessBilling": ["Yes", "No"],
    "PaymentMethod": ["Electronic check", "Mailed check", "Bank transfer (automatic)", "Credit card (automatic)"],
    "Churn": ["Yes", "No"],
}
SEGMENTS = ["new", "developing", "loyal"]
TENURE_BINS = [12, 24]  # <=12 months new, 13-24 developing, >24 loyal
SCHEMA = ["customerID", "gender", "SeniorCitizen", "Partner", "Dependents", "tenure", "PhoneService", "MultipleLines", "InternetService", "OnlineSecurity", "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies", "Contract", "PaperlessBilling", "PaymentMethod", "MonthlyCharges", "TotalCharges", "Churn"]
OPTIONAL = {"gender", "SeniorCitizen", "Churn"}
SERVICES = ["OnlineSecurity", "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies"]
# Model inputs. Flags are 1 when the customer has the service or attribute; "No phone/internet service" counts as 0,
# so that information lives only in PhoneService and InternetService.
BINARY = ["Partner", "Dependents", "PhoneService", "PaperlessBilling", "MultipleLines", *SERVICES]
CATEGORICAL = ["InternetService", "Contract", "PaymentMethod", "tenure_band"]
# Each categorical is coded against its lowest-churn level, so odds ratios read "compared with ...".
REFERENCE_LEVELS = {"InternetService": "No", "Contract": "Two year", "PaymentMethod": "Credit card (automatic)", "tenure_band": "loyal"}


class DataValidationError(ValueError):
    def __init__(self, errors):
        self.errors = pd.DataFrame(errors, columns=["row", "column", "message"])
        super().__init__(self.errors.to_string(index=False))


def validate(frame: pd.DataFrame, training=False):
    df = frame.copy()
    errors = []
    required = set(SCHEMA) if training else set(SCHEMA) - OPTIONAL
    for col in sorted(required - set(df.columns)):
        errors.append((0, col, "Required column missing"))
    if errors:
        raise DataValidationError(errors)
    if len(df) == 0:
        raise DataValidationError([(0, "file", "CSV contains no customers")])
    extra = sorted(set(df.columns) - set(SCHEMA))
    df = df[[c for c in SCHEMA if c in df]].copy()
    missing_before = df.isna().sum().to_dict()
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].map(lambda x: x.strip() if isinstance(x, str) else x)
    before = len(df)
    if training:
        df = df.drop_duplicates().copy()
    for idx in df.index[df.customerID.isna() | df.customerID.eq("")]:
        errors.append((int(idx) + 2, "customerID", "Empty ID"))
    for idx in df.index[df.customerID.duplicated(keep=False)]:
        errors.append((int(idx) + 2, "customerID", "Duplicate ID"))
    for col in NUMERIC:
        raw = df[col].map(lambda x: np.nan if isinstance(x, str) and not x.strip() else x)
        num = pd.to_numeric(raw, errors="coerce")
        bad = (raw.notna() & num.isna()) | (num.notna() & (~np.isfinite(num) | num.lt(0)))
        if col == "tenure":
            bad |= num.notna() & (num % 1 != 0)
        for idx in df.index[bad]:
            errors.append((int(idx) + 2, col, "Must be a finite, non-negative number; tenure must be an integer"))
        df[col] = num
    blank_total = int(df.TotalCharges.isna().sum())
    fill_zero = df.tenure.eq(0) & df.TotalCharges.isna()
    df.loc[fill_zero, "TotalCharges"] = 0.0
    for col, allowed in DOMAINS.items():
        if col not in df:
            continue
        if col == "SeniorCitizen":
            df[col] = df[col].map(lambda x: str(int(x)) if pd.notna(x) and str(x) in ["0", "1", "0.0", "1.0"] else x)
        for idx in df.index[~df[col].isin(allowed)]:
            errors.append((int(idx) + 2, col, f"Value outside allowed domain: {allowed}"))
    dependencies = [("PhoneService", "No", "MultipleLines", "No phone service")]
    dependencies += [("InternetService", "No", col, "No internet service") for col in
                     ["OnlineSecurity", "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies"]]
    for parent, absent, child, unavailable in dependencies:
        mismatch = df[parent].eq(absent) != df[child].eq(unavailable)
        for idx in df.index[mismatch]:
            errors.append((int(idx) + 2, child, f"Service contradiction: {child}='{unavailable}' if and only if {parent}='{absent}'"))
    if errors:
        raise DataValidationError(errors)
    if "Churn" in df:
        df["churn"] = df.Churn.map({"Yes": 1, "No": 0}).astype(int)
    return df.reset_index(drop=True), {
        "rows_before": before, "rows_after": len(df), "duplicates_removed": before - len(df),
        "total_charges_missing_before": blank_total, "total_charges_filled_zero": int(fill_zero.sum()),
        "missing_before": missing_before, "missing_after": df.isna().sum().to_dict(),
        "ignored_columns": extra, "unique_ids": df.customerID.nunique(),
        "churn_counts": df.churn.value_counts().to_dict() if "churn" in df else {},
        "joins": "None: single source file, no external customer data joined",
        "filters": "Exact duplicate rows removed from the full file before splitting; no other rows filtered" if training else "None",
    }


def parse_upload(content: bytes):
    if len(content) > 10 * 1024 * 1024:
        raise DataValidationError([(0, "file", "Limit is 10 MB")])
    try:
        text = content.decode("utf-8-sig")
        df = pd.read_csv(io.StringIO(text), dtype={"customerID": str}, nrows=50001)
    except (UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise DataValidationError([(0, "file", "A UTF-8, comma-separated CSV is required")]) from exc
    if len(df) > 50000:
        raise DataValidationError([(0, "file", "Limit is 50,000 customers")])
    return validate(df, training=False)


def download():
    folder = ROOT / "data/raw"
    folder.mkdir(parents=True, exist_ok=True)
    path, manifest_path = folder / "telco.csv", folder / "source.json"
    if path.exists():
        manifest = read_json(manifest_path)
        if digest(path.read_bytes()) != manifest["sha256"]:
            raise ValueError("Raw data checksum does not match source.json. Refusing to overwrite raw data.")
        return path
    attempts = []
    for source, url in [("Kaggle blastchar/telco-customer-churn", KAGGLE), ("IBM GitHub", IBM)]:
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            content = response.content
            name = "Telco-Customer-Churn.csv"
            if "Kaggle" in source:
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
                    content = z.read(name)
            frame = pd.read_csv(io.BytesIO(content))
            validate(frame, training=True)
            path.write_bytes(content)
            write_json(manifest_path, {
                "source": source, "url": url, "dataset_page": "https://www.kaggle.com/datasets/blastchar/telco-customer-churn",
                "original_filename": name, "downloaded_at_utc": now(), "sha256": digest(content),
                "rows": len(frame), "columns": list(frame.columns), "attempts": attempts,
                "version": "Snapshot identified by SHA-256; upstream version not supplied by download endpoint",
                "license_note": "Dataset attribution: IBM sample / BlastChar. Consult source data card for distribution rights; software license does not extend to source data.",
            })
            return path
        except (requests.RequestException, zipfile.BadZipFile, StopIteration, ValueError) as exc:
            attempts.append({"source": source, "error": str(exc)[:500]})
    raise RuntimeError(f"Could not download the dataset: {attempts}")


def prepare():
    raw = download()
    metadata_path = ROOT / "data/raw/source-metadata.json"
    if not metadata_path.exists():
        try:
            response = requests.get(METADATA_URL, timeout=30)
            response.raise_for_status()
            entry = next(item for item in response.json() if item.get("ref") == "blastchar/telco-customer-churn")
            write_json(metadata_path, {"metadata_url": METADATA_URL, "observed_at_utc": now(), "ref": entry["ref"], "version": entry.get("currentVersionNumber"), "last_updated": entry.get("lastUpdated"), "license": entry.get("licenseName"), "note": "Metadata observed separately from downloaded bytes; raw SHA-256 identifies the exact analyzed file."})
        except (requests.RequestException, ValueError, StopIteration) as exc:
            write_json(metadata_path, {"metadata_url": METADATA_URL, "error": str(exc), "license": "See upstream data card; metadata unavailable"})
    df, quality = validate(pd.read_csv(raw), training=True)
    seed = config()["seed"]
    train, rest = train_test_split(df.index, test_size=0.4, stratify=df.churn, random_state=seed)
    val, test = train_test_split(rest, test_size=0.5, stratify=df.loc[rest, "churn"], random_state=seed)
    df["split"] = "train"
    df.loc[val, "split"], df.loc[test, "split"] = "validation", "test"
    save_csv(df, ROOT / "data/processed/customers.csv")
    save_csv(df[["customerID", "split"]], ROOT / "data/processed/splits.csv")
    write_json(ROOT / "data/processed/quality.json", quality)
    # The upload template gets fresh IDs, so it behaves like customers the model has not seen.
    template = df.loc[test[:20], [c for c in SCHEMA if c not in OPTIONAL]].copy()
    template["customerID"] = [f"DEMO-{i:04d}" for i in range(1, len(template) + 1)]
    save_csv(template, ROOT / "data/examples/customers_unlabeled.csv")
    return df


def tenure_segment(tenure):
    """Ordered tenure segment used by the model feature, the value proxy and every report."""
    return pd.cut(tenure, [-np.inf, *TENURE_BINS, np.inf], labels=SEGMENTS, ordered=True)


def features(df):
    """All candidate model inputs; the trained pipeline keeps only its chosen feature set. Never the label, gender or age."""
    out = df[[*NUMERIC, "InternetService", "Contract", "PaymentMethod"]].copy()
    for col in BINARY:
        out[col] = df[col].eq("Yes").astype(int)
    out["tenure_band"] = tenure_segment(df.tenure).astype(object)
    return out
