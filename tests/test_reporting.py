import copy
import pytest
from jinja2 import UndefinedError
from telco_retention.common import latest_run
from telco_retention.facts import build_facts
from telco_retention.notebooks import to_notebook
from telco_retention.templating import DOCUMENTS, render, render_documents


@pytest.fixture(scope="module")
def facts():
    return build_facts(latest_run())


def test_every_template_renders(facts, tmp_path):
    written = render_documents(facts, tmp_path)
    assert len(written) == len(DOCUMENTS)
    for path in written:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("<!-- Generated from") and facts["run"]["id"] in text.splitlines()[0]
        assert "{{" not in text and "{%" not in text


def test_brief_is_short_and_decision_first(facts):
    brief = render("reports/executive-brief.md.j2", facts)
    assert len(brief.split()) <= 800
    headings = [line for line in brief.splitlines() if line.startswith("## ")]
    assert headings[0] == "## Recommendation" and headings[-1] == "## Decisions requested"
    assert f"{facts['break_even']['break_even_default_save_rate'] * 100:.1f}%" in brief


MANAGER_DOCUMENTS = ["reports/executive-brief.md.j2", "presentation/qa-prep.md.j2", "presentation/demo-script.md.j2",
                     "docs/business-case.md.j2", "docs/retention-playbook.md.j2", "docs/deployment-vietnam.md.j2"]


def test_manager_documents_avoid_overclaims(facts):
    banned = ["the method works", "never loses money", "conservative 20%", "no campaign is run", "the course", "rather than hide"]
    for template in MANAGER_DOCUMENTS:
        text = render(template, facts).lower()
        assert not [b for b in banned if b in text], template


def test_one_headline_gain_everywhere(facts):
    gain = f"${facts['headline']['delta_vs_risk']:,.0f}"
    for template in ["reports/executive-brief.md.j2", "presentation/demo-script.md.j2", "reports/analysis-report.md.j2"]:
        assert gain in render(template, facts), template
    brief = render("reports/executive-brief.md.j2", facts)
    assert f"${facts['headline']['targeting_effect']:,.0f}" in brief and f"${facts['headline']['offer_design_effect']:,.0f}" in brief
    assert brief.index("**The issue.**") < brief.index("## Recommendation")


def test_documents_follow_the_facts(facts):
    changed = copy.deepcopy(facts)
    changed["budget"]["base"] = 9999
    changed["comparison"]["risk"]["expected_net_value"] = 1234.0
    changed["model"]["label"] = "Some Other Model"
    brief = render("reports/executive-brief.md.j2", changed)
    assert "$9,999" in brief and "$1,234" in brief
    assert "Some Other Model" in render("docs/model-card.md.j2", changed)


def test_missing_fact_fails_loudly(facts):
    broken = copy.deepcopy(facts)
    del broken["break_even"]
    with pytest.raises(UndefinedError):
        render("reports/executive-brief.md.j2", broken)


def test_notebook_template_splits_code_and_narrative():
    nb = to_notebook("# Title\n\nText\n\n```python\nx = 1\nprint(x)\n```\n\nMore text\n")
    assert [c.cell_type for c in nb.cells] == ["markdown", "code", "markdown"]
    assert nb.cells[1].source == "x = 1\nprint(x)"
