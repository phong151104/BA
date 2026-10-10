"""IBM's extended telco sample: churn reasons and the CLTV index for the same customers, joined for description only."""
from __future__ import annotations

import io
import re
import zipfile
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import requests
from .common import ROOT, digest, now, read_json, save_csv, write_json

RAW = ROOT / "data/raw/telco_extended.xlsx"
MANIFEST = ROOT / "data/raw/source_extended.json"
# Extended column -> base column; all must agree for the join to be accepted.
SHARED = {"Churn Label": "Churn", "Tenure Months": "tenure", "Monthly Charges": "MonthlyCharges", "Contract": "Contract",
          "Internet Service": "InternetService", "Payment Method": "PaymentMethod", "Tech Support": "TechSupport"}
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def read_xlsx(content: bytes) -> pd.DataFrame:
    """First worksheet of an .xlsx file as text columns, using only the standard library."""
    with zipfile.ZipFile(io.BytesIO(content)) as book:
        names = book.namelist()
        strings = []
        if "xl/sharedStrings.xml" in names:
            for item in ET.fromstring(book.read("xl/sharedStrings.xml")).findall("m:si", NS):
                strings.append("".join(t.text or "" for t in item.iter(f"{{{NS['m']}}}t")))
        sheet = sorted(n for n in names if n.startswith("xl/worksheets/sheet"))[0]
        rows = []
        for row in ET.fromstring(book.read(sheet)).find("m:sheetData", NS).findall("m:row", NS):
            cells = {}
            for cell in row.findall("m:c", NS):
                column = re.match(r"[A-Z]+", cell.get("r")).group()  # blank cells are absent, so place by reference
                value, inline = cell.find("m:v", NS), cell.find("m:is", NS)
                if cell.get("t") == "s" and value is not None:
                    cells[column] = strings[int(value.text)]
                elif inline is not None:
                    cells[column] = "".join(t.text or "" for t in inline.iter(f"{{{NS['m']}}}t"))
                elif value is not None:
                    cells[column] = value.text
            rows.append(cells)
    header = rows[0]
    return pd.DataFrame([[r.get(c) for c in header] for r in rows[1:]], columns=[header[c] for c in header])


def download_extended(cfg):
    if RAW.exists():
        if digest(RAW.read_bytes()) != read_json(MANIFEST)["sha256"]:
            raise ValueError("Extended data checksum does not match source_extended.json. Refusing to overwrite raw data.")
        return RAW
    ext = cfg["extended"]
    response = requests.get(ext["url"], timeout=120)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".xlsx"))
        content = z.read(name)
    frame = read_xlsx(content)
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_bytes(content)
    write_json(MANIFEST, {"source": "Kaggle yeanzc/telco-customer-churn-ibm-dataset", "url": ext["url"], "dataset_page": ext["dataset_page"],
                          "original_filename": name, "downloaded_at_utc": now(), "sha256": digest(content), "rows": len(frame), "columns": list(frame.columns),
                          "license_note": "IBM Cognos Analytics sample data republished on Kaggle; consult the data card for distribution rights.",
                          "use": "Churn Reason and CLTV only, for description; Churn Score and location fields are never stored or used."})
    return RAW


def join_extended(customers, cfg, extended=None):
    """Join reasons and CLTV by customer ID after checking that the shared fields agree; returns the context table and a join report."""
    extended = read_xlsx(download_extended(cfg).read_bytes()) if extended is None else extended
    ext = extended[["CustomerID", "Churn Reason", "CLTV", *SHARED]]  # Churn Score is never kept
    ext = ext.rename(columns={c: f"extended {c}" for c in SHARED})
    merged = customers[["customerID", *SHARED.values()]].merge(ext, left_on="customerID", right_on="CustomerID", how="left", validate="one_to_one")
    agreement = {}
    for extended, base in SHARED.items():
        other = merged[f"extended {extended}"]
        if base in ["tenure", "MonthlyCharges"]:
            same = np.isclose(pd.to_numeric(other, errors="coerce"), merged[base].astype(float), atol=1e-6)
        else:
            same = other.eq(merged[base])
        agreement[base] = float(np.mean(same))
    report = {"joined_on": "customerID = CustomerID", "base_rows": len(customers), "matched": int(merged.CustomerID.notna().sum()),
              "field_agreement": agreement, "kept_fields": ["Churn Reason", "CLTV"], "dropped_fields": "Churn Score, location and all other columns"}
    report["accepted"] = report["matched"] == len(customers) and all(v == 1.0 for v in agreement.values())
    if not report["accepted"] and cfg["extended"]["required"]:
        raise ValueError(f"Extended data do not match the base file: {report}")
    category = {reason: name for name, reasons in cfg["extended"]["reason_categories"].items() for reason in reasons}
    reasons = merged["Churn Reason"].where(merged.Churn.eq("Yes"))
    unmapped = sorted(set(reasons.dropna()) - set(category))
    if unmapped:
        raise ValueError(f"Churn reasons without a category: {unmapped}")
    context = pd.DataFrame({"customerID": merged.customerID, "churn_reason": reasons, "churn_category": reasons.map(category),
                            "cltv": pd.to_numeric(merged.CLTV, errors="coerce")})
    return context, report


def prepare_context(customers, cfg):
    context, report = join_extended(customers, cfg)
    save_csv(context, ROOT / "data/processed/customer_context.csv")
    write_json(ROOT / "data/processed/extended_join.json", report)
    return context, report
