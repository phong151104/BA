import io
import zipfile
import pandas as pd
import pytest
from telco_retention.common import ROOT, config, latest_run
from telco_retention.data import features
from telco_retention.extended import SHARED, join_extended, read_xlsx

NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'


def xlsx(rows):
    """Minimal workbook: shared strings for text, numbers inline, blank cells omitted as Excel does."""
    strings, sheet = [], []
    for r, row in enumerate(rows, 1):
        cells = []
        for c, value in enumerate(row):
            ref = f"{chr(65 + c)}{r}"
            if value is None:
                continue
            if isinstance(value, str):
                strings.append(value)
                cells.append(f'<c r="{ref}" t="s"><v>{len(strings) - 1}</v></c>')
            else:
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
        sheet.append(f'<row r="{r}">{"".join(cells)}</row>')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("xl/sharedStrings.xml", f'<sst {NS}>' + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet {NS}><sheetData>{"".join(sheet)}</sheetData></worksheet>')
    return buffer.getvalue()


def test_read_xlsx_places_cells_by_reference():
    frame = read_xlsx(xlsx([["id", "reason", "value"], ["a", None, 3], ["b", "Moved", 4.5]]))
    assert frame.columns.tolist() == ["id", "reason", "value"]
    assert frame.reason.isna().iloc[0] and frame.reason.iloc[1] == "Moved"
    assert frame.value.tolist() == ["3", "4.5"]


def extended_for(customers):
    out = pd.DataFrame({"CustomerID": customers.customerID, "Churn Reason": customers.Churn.map({"Yes": "Moved", "No": None}), "CLTV": 4000,
                        "Churn Score": 99})
    for extended, base in SHARED.items():
        out[extended] = customers[base].astype(str) if base not in ["tenure", "MonthlyCharges"] else customers[base]
    return out


def test_join_accepts_matching_rows_and_never_keeps_the_churn_score():
    customers = pd.read_csv(ROOT / "data/processed/customers.csv").head(30)
    context, report = join_extended(customers, config(), extended_for(customers))
    assert report["accepted"] and report["matched"] == 30
    assert "Churn Score" not in context.columns and context.churn_reason.notna().sum() == customers.Churn.eq("Yes").sum()
    assert set(context.churn_category.dropna()) <= set(config()["extended"]["reason_categories"])


def test_join_rejects_a_disagreeing_field():
    customers = pd.read_csv(ROOT / "data/processed/customers.csv").head(30)
    extended = extended_for(customers)
    extended.loc[0, "Contract"] = "Two year" if customers.Contract.iloc[0] != "Two year" else "One year"
    with pytest.raises(ValueError, match="do not match"):
        join_extended(customers, config(), extended)


def test_context_fields_stay_out_of_the_model_data():
    customers = pd.read_csv(ROOT / "data/processed/customers.csv")
    assert not {"churn_reason", "churn_category", "cltv"} & (set(customers.columns) | set(features(customers).columns))
    context = pd.read_csv(latest_run() / "customer_context.csv")
    assert len(context) == len(customers) and context.churn_reason.notna().sum() == customers.churn.sum()
