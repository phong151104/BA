from io import BytesIO
import numpy as np
import pandas as pd
import pytest
from telco_retention.common import ROOT, latest_run, read_json
from telco_retention.data import validate, parse_upload, features, DataValidationError


@pytest.fixture
def sample():
    return pd.read_csv(ROOT / "data/examples/customers_unlabeled.csv").head(3)


def test_raw_quality_and_splits():
    df = pd.read_csv(ROOT / "data/raw/telco.csv")
    clean, quality = validate(df, training=True)
    assert len(clean) == 7043
    assert quality["total_charges_missing_before"] == 11
    assert quality["total_charges_filled_zero"] == 11
    assert clean.TotalCharges.isna().sum() == 0
    split = pd.read_csv(ROOT / "data/processed/splits.csv")
    assert split.customerID.is_unique
    assert set(split.split) == {"train", "validation", "test"}
    groups = [set(split.loc[split.split.eq(s), "customerID"]) for s in ["train", "validation", "test"]]
    assert not groups[0] & groups[1] and not groups[0] & groups[2] and not groups[1] & groups[2]


def test_feature_exclusions(sample):
    frame, _ = validate(sample)
    X = features(frame)
    assert not {"customerID", "Churn", "churn", "gender", "SeniorCitizen", "split"} & set(X)
    assert {"tenure_band", "addon_count", "monthly_contract", "autopay"} <= set(X)


@pytest.mark.parametrize("column,value", [("tenure", -1), ("tenure", .5), ("MonthlyCharges", "oops"), ("MonthlyCharges", np.inf), ("Contract", "unknown"), ("customerID", "")])
def test_invalid_value(sample, column, value):
    sample[column] = sample[column].astype(object)
    sample.loc[0, column] = value
    with pytest.raises(DataValidationError):
        validate(sample)


def test_duplicate_upload_rejected(sample):
    with pytest.raises(DataValidationError):
        validate(pd.concat([sample, sample], ignore_index=True))


def test_duplicate_training_logged():
    raw = pd.read_csv(ROOT / "data/raw/telco.csv").head(3)
    clean, log = validate(pd.concat([raw, raw], ignore_index=True), training=True)
    assert len(clean) == 3 and log["duplicates_removed"] == 3
    raw.loc[1, "customerID"] = raw.loc[0, "customerID"]
    with pytest.raises(DataValidationError):
        validate(raw, training=True)


def test_missing_column(sample):
    with pytest.raises(DataValidationError, match="MonthlyCharges"):
        validate(sample.drop(columns="MonthlyCharges"))


def test_extra_columns_logged(sample):
    sample["note"] = "ignore"
    df, log = validate(sample)
    assert log["ignored_columns"] == ["note"] and "note" not in df


def test_missing_numeric_allowed(sample):
    sample.loc[0, "MonthlyCharges"] = np.nan
    clean, _ = validate(sample)
    assert pd.isna(clean.loc[0, "MonthlyCharges"])


def test_zero_tenure_total_charges(sample):
    sample.loc[0, "tenure"] = 0
    sample["TotalCharges"] = sample.TotalCharges.astype(object)
    sample.loc[0, "TotalCharges"] = "   "
    clean, log = validate(sample)
    assert clean.loc[0, "TotalCharges"] == 0 and log["total_charges_filled_zero"] == 1


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
def test_upload_encoding(sample, encoding):
    clean, _ = parse_upload(sample.to_csv(index=False).encode(encoding))
    assert len(clean) == 3


def test_upload_limits(sample):
    with pytest.raises(DataValidationError, match="10 MB"):
        parse_upload(b"a" * (10 * 1024 * 1024 + 1))
    many = pd.concat([sample.iloc[:1]] * 50001, ignore_index=True)
    many["customerID"] = [f"ID{x}" for x in range(len(many))]
    with pytest.raises(DataValidationError, match="50.000"):
        parse_upload(many.to_csv(index=False).encode())


@pytest.mark.parametrize("content", [b"", b"\xff\xfe", b"a;b\n1;2", b"customerID,tenure\n"])
def test_bad_csv(content):
    with pytest.raises(DataValidationError):
        parse_upload(content)
