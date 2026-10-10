"""Render business documents from Jinja2 templates and the run's facts."""
from __future__ import annotations

from pathlib import Path
import math
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from .common import ROOT

TEMPLATES = Path(__file__).with_name("templates")

# template (relative to TEMPLATES) -> output (relative to ROOT)
DOCUMENTS = {
    "reports/executive-brief.md.j2": "reports/executive-brief.md",
    "reports/analysis-report.md.j2": "reports/analysis-report.md",
    "docs/business-case.md.j2": "docs/business-case.md",
    "docs/data-readiness-review.md.j2": "docs/data-readiness-review.md",
    "docs/source-log.md.j2": "docs/source-log.md",
    "docs/cleaning-log.md.j2": "docs/cleaning-log.md",
    "docs/data-dictionary.md.j2": "docs/data-dictionary.md",
    "docs/assumption-register.md.j2": "docs/assumption-register.md",
    "docs/model-card.md.j2": "docs/model-card.md",
    "docs/retention-playbook.md.j2": "docs/retention-playbook.md",
    "docs/pilot-design.md.j2": "docs/pilot-design.md",
    "docs/governance-and-risks.md.j2": "docs/governance-and-risks.md",
    "presentation/deck.md.j2": "reports/presentation/deck.md",
    "presentation/demo-script.md.j2": "reports/presentation/demo-script.md",
    "presentation/qa-prep.md.j2": "reports/presentation/qa-prep.md",
}


def _missing(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def usd(x, digits=0):
    if _missing(x):
        return "n/a"
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.{digits}f}"


def signed_usd(x, digits=0):
    if _missing(x):
        return "n/a"
    return ("+" if x >= 0 else "") + usd(x, digits)


def pct(x, digits=1):
    return "n/a" if _missing(x) else f"{x * 100:.{digits}f}%"


def num(x, digits=0):
    return "n/a" if _missing(x) else f"{x:,.{digits}f}"


def ratio(x, digits=2):
    return "n/a" if _missing(x) else f"{x:.{digits}f}x"


def md_table(rows, columns):
    """rows: list of dicts; columns: list of (key, header, format) where format is a filter name or None."""
    formats = {"usd": usd, "usd2": lambda v: usd(v, 2), "pct": pct, "pct0": lambda v: pct(v, 0), "num": num,
               "num1": lambda v: num(v, 1), "num2": lambda v: num(v, 2), "num3": lambda v: num(v, 3), "ratio": ratio, None: lambda v: "n/a" if _missing(v) else str(v)}
    header = "| " + " | ".join(h for _, h, _ in columns) + " |"
    align = "| " + " | ".join("---:" if f not in [None] else "---" for _, _, f in columns) + " |"
    body = ["| " + " | ".join(formats[f](row.get(k)) for k, _, f in columns) + " |" for row in rows]
    return "\n".join([header, align, *body])


ENV = Environment(loader=FileSystemLoader(str(TEMPLATES)), undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
ENV.filters.update(usd=usd, signed_usd=signed_usd, pct=pct, num=num, ratio=ratio, md_table=md_table)


def render(template, ctx):
    return ENV.get_template(template).render(**ctx)


def render_documents(ctx, root=ROOT, documents=None):
    written = []
    for template, output in (documents or DOCUMENTS).items():
        text = render(template, ctx).strip() + "\n"
        header = f"<!-- Generated from src/telco_retention/templates/{template} for run {ctx['run']['id']}. Edit the template, not this file. -->\n"
        path = Path(root) / output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(header + text, encoding="utf-8", newline="\n")
        written.append(path)
    return written
