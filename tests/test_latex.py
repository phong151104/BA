import copy
import re
import subprocess
import pytest
from jinja2 import UndefinedError
from telco_retention import latex
from telco_retention.common import latest_run
from telco_retention.facts import build_facts
from telco_retention.latex import FILTERS, LATEX_DIR, LATEX_DOCUMENTS, LOGO, LatexError, compile_latex, escape, render, render_latex, tex_rows
from telco_retention.team import TEAM


@pytest.fixture(scope="module")
def facts():
    return build_facts(latest_run())


def test_escape_handles_every_special_character():
    assert escape("50% of A&B_c $5 #1 {x} ~ ^") == r"50\% of A\&B\_c \$5 \#1 \{x\} \textasciitilde{} \textasciicircum{}"
    assert escape(r"a\b") == r"a\textbackslash{}b"
    assert escape(escape("50%")) == r"50\%"  # already-safe text is not escaped twice


def test_number_filters_produce_latex():
    assert FILTERS["usd"](-1036.6) == r"\textminus{}\$1,037"
    assert FILTERS["signed_usd"](1368.2) == r"+\$1,368"
    assert FILTERS["pct"](0.1376) == r"13.8\%"
    assert FILTERS["ratio"](3.336) == r"3.34$\times$"
    assert FILTERS["usd"](None) == "n/a"


def test_table_rows_escape_text_and_format_numbers():
    body = tex_rows([{"rule": "Top 10% & rest", "net": -5.0}], [("rule", None), ("net", "usd")])
    assert body == r"Top 10\% \& rest & \textminus{}\$5 \\"


def test_report_renders_completely(facts, tmp_path):
    written = render_latex(facts, tmp_path)
    assert len(written) == len(LATEX_DOCUMENTS)
    text = written[0].read_text(encoding="utf-8")
    assert text.startswith("% Generated from") and facts["run"]["id"] in text.splitlines()[0]
    assert f"{{{LOGO.name}}}" in text and (tmp_path / LATEX_DIR / "images" / LOGO.name).exists()
    assert all(t["email"] in text and escape(t["contribution"]) in text for t in TEAM)  # cover and team table
    assert "<<" not in text and "<%" not in text and "None" not in text
    for env in ["document", "table", "figure", "tabularx", "itemize", "enumerate"]:
        assert text.count(rf"\begin{{{env}}}") == text.count(rf"\end{{{env}}}"), env
    # Outside math, every dollar sign that is money must be escaped.
    prose = re.sub(r"\\\[.*?\\\]|\\begin\{gather\*\}.*?\\end\{gather\*\}|\$[^$]*\\times\$", "", text, flags=re.S)
    assert not re.search(r"(?<!\\)\$\d", prose)


def test_report_follows_the_facts(facts):
    changed = copy.deepcopy(facts)
    changed["headline"]["delta_vs_risk"] = 4321.0
    assert r"+\$4,321" in render("latex/report.tex.j2", changed)
    broken = copy.deepcopy(facts)
    del broken["pilot"]
    with pytest.raises(UndefinedError):
        render("latex/report.tex.j2", broken)


def test_compile_fails_when_references_never_settle(tmp_path, monkeypatch):
    (tmp_path / LATEX_DIR).mkdir(parents=True)
    unsettled = subprocess.CompletedProcess([], 0, stdout="LaTeX Warning: Label(s) may have changed. Rerun to get cross-references right.", stderr="")
    monkeypatch.setattr(latex.subprocess, "run", lambda *args, **kwargs: unsettled)
    with pytest.raises(LatexError, match="still changing"):
        compile_latex(tmp_path, engine="pdflatex")
