<!-- Generated from src/telco_retention/templates/docs/source-log.md.j2 for run 20261010T124415068764Z-88be4b93. Edit the template, not this file. -->
# Source log

| Field | Value |
|---|---|
| Dataset | IBM Telco Customer Churn (sample data, fictional company) |
| Actual download source | **Kaggle blastchar/telco-customer-churn** |
| Download URL | https://www.kaggle.com/api/v1/datasets/download/blastchar/telco-customer-churn |
| Dataset page | https://www.kaggle.com/datasets/blastchar/telco-customer-churn |
| Original file | `WA_Fn-UseC_-Telco-Customer-Churn.csv` |
| Downloaded (UTC) | 2026-10-03T11:36:37.024155+00:00 |
| Version | Snapshot identified by SHA-256; upstream version not supplied by download endpoint; Kaggle metadata reports version 1 (last updated 2018-02-23T18:20:00.21Z) |
| SHA-256 | `88be4b93fbe0cc83421af1c503794c97c342eca914c1576db7c276e61d61358a` |
| Rows x columns | 7,043 x 21 |
| Licence | Kaggle metadata: "Data files © Original Authors". Dataset attribution: IBM sample / BlastChar. Consult source data card for distribution rights; software license does not extend to source data. |
| Joins | None: single source file, no external customer data joined |
| Filters | Exact duplicate rows removed from the full file before splitting; no other rows filtered (0 rows removed) |

## Provenance notes

- IBM publishes the data as a sample for its analytics products: "a fictional telco company that provided home phone and Internet services to 7043 customers in California in Q3" ([IBM, 2019](references.md#ibm2019); [IBM docs](references.md#ibmdocs)). The Kaggle copy is the 21-column base version ([BlastChar, 2018](references.md#kaggle2018)).
- The churn window differs between descriptions: "left within the last month" (Kaggle and the base IBM sample) and "left the company this quarter" (IBM extended sample). The project treats the label as churn within one observation window and does not annualise it.
- Currency is not stated by the source; amounts are treated as USD for a US company.
- The pipeline first tries the Kaggle API, then the IBM GitHub copy ([IBM GitHub](references.md#ibmgithub)). The raw file is never modified; on re-runs the checksum is verified and the pipeline stops if it changed.

## Synthetic elements

The offer table (offer costs, contact cost, save rates, eligibility rules) is created by the team for simulation, as the brief allows. It is version `v2` in `configs/default.yaml` and is documented with sources in the [assumption register](assumption-register.md). No randomised campaign data exist in the source.
