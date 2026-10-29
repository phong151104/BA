import copy
from pathlib import Path
import pytest
from docx import Document
from pptx import Presentation
from pypdf import PdfWriter
from telco_retention.common import ROOT, digest, latest_run
from telco_retention.export import ExportUnavailable, _check_generated, convert_pdfs, markdown_to_docx
from telco_retention.facts import build_facts
from telco_retention.presentation import DEMO_SPEAKER, SPEAKERS, TALK_SECONDS, _slide_ranges, build_presentation, lint
from telco_retention.team import TEAM
from telco_retention.templating import render


@pytest.fixture(scope="module")
def facts():
    return build_facts(latest_run())


@pytest.fixture(scope="module")
def deck(facts, tmp_path_factory):
    folder = tmp_path_factory.mktemp("presentation")
    script = build_presentation(facts, folder / "deck.pptx", folder / "script.md")
    return Presentation(folder / "deck.pptx"), script, (folder / "script.md").read_text(encoding="utf-8")


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


def test_deck_has_a_speaker_script_on_every_slide(deck):
    prs, script, _ = deck
    assert lint(script) == []
    assert len(prs.slides) == len(script)
    for slide, entry in zip(prs.slides, script):
        notes = slide.notes_slide.notes_text_frame.text
        assert notes.startswith(entry["cue"]) and entry["text"] in notes


def test_talk_fits_the_slot_and_is_shared(deck):
    _, script, _ = deck
    timed = [e for e in script if e["speaker"] in SPEAKERS]
    assert sum(e["seconds"] for e in timed) == TALK_SECONDS
    assert {e["speaker"] for e in timed} == set(SPEAKERS)
    # Each speaker talks in one block, in order, and the demo follows the talk.
    order = [e["speaker"] for e in timed]
    assert order == sorted(order, key=SPEAKERS.index)
    demo = next(e for e in script if e["speaker"] == DEMO_SPEAKER)
    assert demo["slide"] > max(e["slide"] for e in timed if e["seconds"] >= 30)


def test_deck_uses_the_template_and_the_facts(deck, facts):
    prs, script, rehearsal = deck
    assert len(prs.slide_masters) == 5 and prs.slides[0].slide_layout.slide_master == prs.slide_masters[0]
    text = " ".join(sh.text_frame.text for s in prs.slides for sh in s.shapes if sh.has_text_frame)
    gain = f"${facts['headline']['delta_vs_risk']:,.0f}"
    assert gain in text and gain in " ".join(e["text"] for e in script) and gain in rehearsal
    assert f"{facts['pilot']['list_size_per_wave']:,}" in text


def test_team_slide_lists_every_contribution(deck):
    prs, script, _ = deck
    entry = next(e for e in script if e["title"] == "Team Contributions")
    cells = [c.text for sh in prs.slides[entry["slide"] - 1].shapes if sh.has_table for row in sh.table.rows for c in row.cells]
    assert all(t["name"] in cells and t["student_id"] in cells and t["contribution"] in cells for t in TEAM)
    # Shown after the demo, in the closing speaker's time.
    assert entry["speaker"] == SPEAKERS[-1] and entry["slide"] > next(e["slide"] for e in script if e["speaker"] == DEMO_SPEAKER)


def test_deck_follows_changed_facts(facts, tmp_path):
    changed = copy.deepcopy(facts)
    changed["headline"]["delta_vs_risk"] = 4321.0
    script = build_presentation(changed, tmp_path / "deck.pptx")
    assert any("$4,321" in e["text"] for e in script)


def test_lint_flags_timing_and_pace():
    script = [{"slide": 1, "speaker": "Kiet", "seconds": 300, "text": "word " * 900},
              {"slide": 2, "speaker": "Hieu", "seconds": 40, "text": ""},
              {"slide": 3, "speaker": "Dung", "seconds": 0, "text": "Thanks."}]
    problems = lint(script)
    assert any("talk lasts" in p for p in problems) and any("slide 2 has no speaker notes" in p for p in problems)
    assert "slide 1: 3.0 words per second" in problems  # too fast
    assert "slide 2: 0.0 words per second" in problems  # silent
    assert any(p.startswith("Dung speaks") for p in problems)


def test_deck_avoids_overclaims(deck):
    _, script, rehearsal = deck
    banned = ["the method works", "never loses money", "causal uplift of", "guaranteed", "proves"]
    lowered = rehearsal.lower()
    assert not [b for b in banned if b in lowered]


def test_slide_ranges():
    assert _slide_ranges([10, 11, 12, 13, 15]) == "10-13, 15"
    assert _slide_ranges([14]) == "14"


def blank_pdf(path, pages):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    with open(path, "wb") as f:
        writer.write(f)


def test_each_pdf_records_the_run_it_comes_from(tmp_path):
    brief, deck = tmp_path / "brief.pdf", tmp_path / "deck.pdf"
    blank_pdf(brief, 1)
    blank_pdf(deck, 3)
    run_a_deck = deck.read_bytes()
    hashes = {p.name: digest(p.read_bytes()) for p in [brief, deck]}
    previous = {"run_id": "A", "brief_pages": 1, "deck_pdf_pages": 3, "pdf_run_id": "A", "sha256": hashes}  # run A's export, before per-PDF runs

    def no_powerpoint(source, target):
        raise ExportUnavailable("PowerPoint is not installed")

    jobs = [("brief", lambda source, target: blank_pdf(target, 2), None, brief, "brief_pages"), ("deck", no_powerpoint, None, deck, "deck_pdf_pages")]
    out = convert_pdfs(jobs, "auto", "B", previous, tmp_path)
    assert (out["brief_pages"], out["brief_pdf_run_id"]) == (2, "B")
    assert (out["deck_pdf_pages"], out["deck_pdf_run_id"]) == (3, "A")  # the deck was not rebuilt
    assert out["pdf_status"] == "partial" and "PowerPoint" in out["pdf_error"]
    with pytest.raises(ExportUnavailable):
        convert_pdfs(jobs, "require", "B", previous, tmp_path)
    # Only a file the previous export hashed at its own path is described: not a replaced deck, not a missing one,
    # not another document copied over the brief.
    out["sha256"] = {**hashes, "brief.pdf": digest(brief.read_bytes())}
    deck.write_bytes(run_a_deck + b"\n% replaced")
    assert convert_pdfs(jobs, "skip", "C", out, tmp_path) == {"brief_pages": 2, "brief_pdf_run_id": "B", "pdf_status": "skipped"}
    deck.unlink()
    assert convert_pdfs(jobs, "skip", "C", out, tmp_path) == {"brief_pages": 2, "brief_pdf_run_id": "B", "pdf_status": "skipped"}
    brief.write_bytes(run_a_deck)
    assert convert_pdfs(jobs, "skip", "C", {**out, "sha256": {**out["sha256"], "deck.pdf": hashes["deck.pdf"]}}, tmp_path) == {"pdf_status": "skipped"}


def test_export_refuses_sources_from_another_run(tmp_path):
    source = tmp_path / "report.tex"
    source.write_text("% Generated from src/telco_retention/templates/latex/report.tex.j2 for run A. Edit the template, not this file.\n", encoding="utf-8")
    _check_generated(source, Path("runs/A"))
    for run in ["runs/B", "runs/AB"]:
        with pytest.raises(ValueError, match="not from run"):
            _check_generated(source, Path(run))
    with pytest.raises(ValueError):
        _check_generated(tmp_path / "missing.tex", Path("runs/A"))
