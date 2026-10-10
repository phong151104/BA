<!-- Generated from src/telco_retention/templates/docs/cleaning-log.md.j2 for run 20261010T124415068764Z-88be4b93. Edit the template, not this file. -->
# Cleaning log

| Step | Decision | Rows affected |
|---|---|---|
| Whitespace | Trim leading/trailing spaces in every text field | all |
| Duplicates | Drop exact duplicate rows from the full file before splitting | 0 |
| `TotalCharges` blanks | Blank strings become missing; customers with tenure 0 get 0 (they have not been billed yet) | 11 of 11 |
| Other numeric gaps | Median imputation fitted on train inside the model pipeline; the same train medians fill gaps before valuing customers | 0 in the source |
| `SeniorCitizen` | Normalised to the strings "0"/"1" | all |
| Label | `Churn` Yes/No mapped to `churn` 1/0; not used as a feature | all |
| Service consistency | "No phone service" / "No internet service" kept as their own categories and checked against the parent service | 0 violations |
| Outliers | Valid extreme values kept; nothing trimmed | 0 |
| Split | Stratified 60/20/20 train/validation/test, seed 42; IDs saved in `data/processed/splits.csv` | 4,225 / 1,409 / 1,409 |

## Quality summary

| Metric | Value |
|---|---|
| Rows before / after | 7,043 / 7,043 |
| Unique IDs | 7,043 |
| Missing values after cleaning | 0 |
| Churn counts (0 / 1) | 5,174 / 1,869 |

Validation rules live in `src/telco_retention/data.py` (`validate`). The same rules reject invalid uploaded CSV files in the dashboard, listing the row, column and reason.
