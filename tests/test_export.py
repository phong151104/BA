from docx import Document
from pptx import Presentation
from telco_retention.common import ROOT, latest_run
from telco_retention.export import build_deck, deck_lint, markdown_to_docx, parse_deck
from telco_retention.facts import build_facts
from telco_retention.templating import render


def test_brief_docx_has_structure(tmp_path):
    md = tmp_path / "brief.md"
    md.write_text(render("reports/executive-brief.md.j2", build_facts(latest_run())), encoding="utf-8")
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures/profit_curve.png").write_bytes((ROOT / "reports/figures/profit_curve.png").read_bytes())
    doc = Document(markdown_to_docx(md, tmp_path / "brief.docx"))
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
    assert headings[0].startswith("Executive brief") and "Decisions requested" in headings
    assert len(doc.tables) == 1 and len(doc.inline_shapes) == 1
    assert all("**" not in p.text for p in doc.paragraphs)


def test_deck_has_notes_on_every_slide(tmp_path):
    folder = tmp_path / "presentation"
    folder.mkdir()
    md = folder / "deck.md"
    md.write_text(render("presentation/deck.md.j2", build_facts(latest_run())), encoding="utf-8")
    (tmp_path / "figures").mkdir()
    for png in (ROOT / "reports/figures").glob("*.png"):
        (tmp_path / "figures" / png.name).write_bytes(png.read_bytes())
    out, slides = build_deck(md, folder / "deck.pptx")
    assert deck_lint(slides) == []
    prs = Presentation(out)
    assert 12 <= len(prs.slides) <= 15
    assert all(s.notes_slide.notes_text_frame.text.strip() for s in prs.slides)


def test_parse_deck_blocks():
    slides = parse_deck("# One\n- a\nNotes: say a\n---\n# Two\n![](x.png)\nNotes: say b\nmore")
    assert [s["title"] for s in slides] == ["One", "Two"]
    assert slides[1]["image"] == "x.png" and slides[1]["notes"] == "say b\nmore"
