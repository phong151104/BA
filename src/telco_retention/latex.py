"""Render the LaTeX final report from the run's facts, and compile it with pdflatex when it is installed."""
from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup
from .common import ROOT
from . import templating as md

LATEX_DIR = "reports/latex"
# template (relative to templates/) -> (source written to LATEX_DIR, compiled PDF relative to ROOT)
LATEX_DOCUMENTS = {
    "latex/report.tex.j2": ("report.tex", "reports/final-report.pdf"),
}
MAX_PASSES = 4  # pdflatex reruns until cross-references and the table of contents settle

_SPECIAL = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
            "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


class LatexUnavailable(RuntimeError):
    """No usable TeX installation: pdflatex missing, not runnable or hanging (for example on a package-install prompt)."""


class LatexError(RuntimeError):
    """pdflatex ran and rejected the document: a template or data problem, never skipped."""


def escape(text):
    """Plain text -> LaTeX-safe text; values already marked safe pass through."""
    if isinstance(text, Markup):
        return text
    return Markup("".join(_SPECIAL.get(ch, ch) for ch in str(text)))


def _signed(text):
    """Typeset a leading minus as a true minus sign, then escape the rest."""
    if text.startswith("-"):
        return Markup(r"\textminus{}") + escape(text[1:])
    return escape(text)


def _wrap(fn):
    return lambda *args, **kwargs: _signed(fn(*args, **kwargs))


def ratio(x, digits=2):
    return Markup("n/a") if md._missing(x) else Markup(f"{x:.{digits}f}" + r"$\times$")


FILTERS = {"usd": _wrap(md.usd), "signed_usd": _wrap(md.signed_usd), "pct": _wrap(md.pct), "num": _wrap(md.num), "ratio": ratio, "tex": escape}
CELL_FORMATS = {"usd": FILTERS["usd"], "usd2": lambda v: FILTERS["usd"](v, 2), "pct": FILTERS["pct"], "pct0": lambda v: FILTERS["pct"](v, 0),
                "num": FILTERS["num"], "num1": lambda v: FILTERS["num"](v, 1), "num2": lambda v: FILTERS["num"](v, 2), "num3": lambda v: FILTERS["num"](v, 3),
                "ratio": ratio, None: lambda v: Markup("n/a") if md._missing(v) else escape(v)}


def tex_rows(rows, columns):
    """Table body: one `a & b & c \\\\` line per row; columns are (key, format) pairs with CELL_FORMATS names."""
    lines = [" & ".join(CELL_FORMATS[f](row.get(k)) for k, f in columns) + r" \\" for row in rows]
    return Markup("\n".join(lines))


def _finalize(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return Markup("n/a")
    return escape(value) if isinstance(value, str) else value


# Angle-bracket delimiters keep Jinja out of LaTeX's braces and percent signs.
ENV = Environment(loader=FileSystemLoader(str(md.TEMPLATES)), undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True,
                  block_start_string="<%", block_end_string="%>", variable_start_string="<<", variable_end_string=">>",
                  comment_start_string="<#", comment_end_string="#>", finalize=_finalize)
ENV.filters.update(FILTERS, tex_rows=tex_rows)


def render(template, ctx):
    return ENV.get_template(template).render(**ctx)


def render_latex(ctx, root=ROOT):
    """Write every LaTeX source, the cover logo and the dashboard picture to reports/latex."""
    from .presentation import DASHBOARD, LOGO, crop_dashboard
    folder = Path(root) / LATEX_DIR
    images = folder / "images"
    images.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(LOGO, images / "hust-logo.png")
    shot = images / "dashboard-decision.png"
    if DASHBOARD.exists():  # the report shows the top of the browser-QA screenshot when one exists
        shot.write_bytes(crop_dashboard(DASHBOARD).getvalue())
    elif shot.exists():
        shot.unlink()
    written = []
    for template, (source, _) in LATEX_DOCUMENTS.items():
        header = f"% Generated from src/telco_retention/templates/{template} for run {ctx['run']['id']}. Edit the template, not this file.\n"
        path = folder / source
        path.write_text(header + render(template, ctx).strip() + "\n", encoding="utf-8", newline="\n")
        written.append(path)
    return written


def compile_latex(root=ROOT, engine=None, timeout=600):
    """pdflatex each source until references settle; copy the PDFs to their delivery paths. Returns {pdf path: pages}."""
    engine = engine or shutil.which("pdflatex")
    if engine is None:
        raise LatexUnavailable("pdflatex not found; install TeX Live or MiKTeX")
    from .export import pdf_page_count
    folder, root = Path(root) / LATEX_DIR, Path(root)
    build = folder / "build"
    build.mkdir(exist_ok=True)
    pages = {}
    for source, pdf in LATEX_DOCUMENTS.values():
        for attempt in range(MAX_PASSES):
            try:
                result = subprocess.run([engine, "-interaction=nonstopmode", "-halt-on-error", f"-output-directory={build.name}", source],
                                        cwd=folder, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise LatexUnavailable(f"pdflatex could not run: {exc}") from exc
            if result.returncode != 0:
                tail = "\n".join(result.stdout.splitlines()[-25:])
                raise LatexError(f"pdflatex failed on {source}:\n{tail}")
            # The outline and table of contents are read on the next pass, which pdflatex does not always announce.
            if attempt >= 1 and "Rerun to get" not in result.stdout and "Rerun LaTeX" not in result.stdout:
                break
        target = root / pdf
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(build / Path(source).with_suffix(".pdf").name, target)
        pages[pdf] = pdf_page_count(target)
    return pages
