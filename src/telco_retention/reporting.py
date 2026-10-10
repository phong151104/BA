"""Regenerate every report artifact from one run: figures, tables, facts, documents and notebooks."""
from __future__ import annotations

import shutil
from pathlib import Path
from .common import ROOT, digest, latest_run, now, write_json
from .facts import build_facts, write_facts
from .figures import figures
from .templating import DOCUMENTS, TEMPLATES, render_documents
from . import notebooks

# Large or internal files that stay in the run folder only.
SKIP_TABLES = {"customers.csv", "customer_context.csv", "shap_feature_values.csv", "cv_logistic.csv", "cv_random_forest.csv", "cv_xgboost.csv", "random_campaigns.csv"}


def copy_tables(run, root=ROOT):
    dest = Path(root) / "reports/tables"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for path in sorted(run.glob("*.csv")):
        if path.name not in SKIP_TABLES:
            shutil.copy2(path, dest / path.name)
    return dest


def report(run=None, root=ROOT, execute_notebooks=True):
    run = run or latest_run()
    figures(run)
    copy_tables(run, root)
    facts = build_facts(run)
    facts_path = write_facts(facts, Path(root) / "reports/facts.json")
    written = render_documents(facts, root)
    paths = notebooks.build(facts, root)
    if execute_notebooks:
        notebooks.execute(paths)
    brief = (Path(root) / DOCUMENTS["reports/executive-brief.md.j2"]).read_text(encoding="utf-8")
    write_json(Path(root) / "reports/report-manifest.json", {
        "run_id": run.name, "generated_at_utc": now(), "strategy": facts["strategy"],
        "scenario_id": facts["comparison"][facts["strategy"]]["scenario_id"], "documents": [str(Path(p).relative_to(root)).replace("\\", "/") for p in written],
        "figure_count": len(facts["figures"]), "executive_brief_words": len(brief.split()),
        "facts_sha256": digest(Path(facts_path).read_bytes()),
        "template_sha256": {str(p.relative_to(TEMPLATES)).replace("\\", "/"): digest(p.read_bytes()) for p in sorted(TEMPLATES.rglob("*.j2"))}})
    return Path(root) / "reports/analysis-report.md"
