"""Produce the submission files: executive brief (DOCX + PDF) and slide deck (PPTX, optional PDF)."""
from __future__ import annotations

import re
from pathlib import Path
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor
from pptx import Presentation
from pptx.dml.color import RGBColor as PptColor
from pptx.util import Emu, Inches, Pt as PptPt
from .common import ROOT, digest, latest_run, now, write_json

INK, SECONDARY, ACCENT = "0B0B0B", "52514E", "2A78D6"
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


class ExportUnavailable(RuntimeError):
    pass


def _runs(paragraph, text, size=None, color=INK):
    """Add text with **bold** spans."""
    for i, part in enumerate(re.split(r"\*\*", text)):
        if part:
            run = paragraph.add_run(part.replace("`", ""))
            run.bold = i % 2 == 1
            run.font.color.rgb = RGBColor.from_string(color)
            if size:
                run.font.size = Pt(size)


def _table_rows(lines):
    rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in lines]
    return [r for r in rows if not all(set(c) <= set("-: ") for c in r)]


def markdown_to_docx(md_path, out_path, image_width_cm=15.5):
    md_path, out_path = Path(md_path), Path(out_path)
    doc = Document()
    section = doc.sections[0]
    section.page_height, section.page_width = Cm(29.7), Cm(21.0)
    section.left_margin = section.right_margin = Cm(1.9)
    section.top_margin = section.bottom_margin = Cm(1.6)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Calibri", Pt(10)
    normal.paragraph_format.space_after = Pt(3)
    normal.paragraph_format.line_spacing = 1.08
    for level, size in [(1, 16), (2, 12), (3, 10.5)]:
        style = doc.styles[f"Heading {level}"]
        style.font.name, style.font.size, style.font.bold = "Calibri", Pt(size), True
        style.font.color.rgb = RGBColor.from_string(INK if level != 2 else ACCENT)
        style.paragraph_format.space_before, style.paragraph_format.space_after = Pt(8 if level > 1 else 0), Pt(3)
    text = re.sub(r"<!--.*?-->", "", md_path.read_text(encoding="utf-8"), flags=re.S)
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            doc.add_heading(line.lstrip("#").strip(), level=min(level, 3))
        elif line.lstrip().startswith("|"):
            block = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                block.append(lines[i])
                i += 1
            rows = _table_rows(block)
            table = doc.add_table(rows=len(rows), cols=len(rows[0]))
            table.style = "Light Grid Accent 1"
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            for r, row in enumerate(rows):
                for c, value in enumerate(row):
                    cell = table.cell(r, c)
                    cell.text = ""
                    _runs(cell.paragraphs[0], value if r else f"**{value}**", size=9)
                    if c and r:
                        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
            doc.add_paragraph().paragraph_format.space_after = Pt(0)
            continue
        elif IMAGE.search(line):
            alt, src = IMAGE.search(line).groups()
            doc.add_picture(str((md_path.parent / src).resolve()), width=Cm(image_width_cm))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif re.match(r"^\s*([-*]|\d+\.)\s+", line):
            style = "List Number" if re.match(r"^\s*\d+\.", line) else "List Bullet"
            paragraph = doc.add_paragraph(style=style)
            paragraph.paragraph_format.space_after = Pt(1)
            _runs(paragraph, re.sub(r"^\s*([-*]|\d+\.)\s+", "", line))
        else:
            paragraph = doc.add_paragraph()
            _runs(paragraph, line.strip(), color=SECONDARY if line.startswith("_") else INK)
        i += 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path)
    return out_path


def docx_to_pdf(docx_path, pdf_path):
    try:
        import pythoncom
        from docx2pdf import convert
        pythoncom.CoInitialize()
        convert(str(docx_path), str(pdf_path))
    except Exception as exc:  # Word missing or COM failure
        raise ExportUnavailable(f"PDF export needs Microsoft Word (docx2pdf): {exc}") from exc
    if not Path(pdf_path).exists():
        raise ExportUnavailable("Word did not produce a PDF")
    return Path(pdf_path)


def pptx_to_pdf(pptx_path, pdf_path):
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        app = win32com.client.Dispatch("PowerPoint.Application")
        deck = app.Presentations.Open(str(Path(pptx_path).resolve()), WithWindow=False)
        deck.SaveAs(str(Path(pdf_path).resolve()), 32)
        deck.Close()
    except Exception as exc:
        raise ExportUnavailable(f"Deck PDF export needs Microsoft PowerPoint: {exc}") from exc
    return Path(pdf_path)


def pdf_page_count(pdf_path):
    from pypdf import PdfReader
    return len(PdfReader(str(pdf_path)).pages)


def parse_deck(md_text):
    slides = []
    for block in re.split(r"^---\s*$", re.sub(r"<!--.*?-->", "", md_text, flags=re.S), flags=re.M):
        lines = [l.rstrip() for l in block.strip().splitlines()]
        if not lines:
            continue
        slide = {"title": "", "subtitle": "", "bullets": [], "image": None, "table": [], "notes": []}
        in_notes = False
        for line in lines:
            if in_notes:
                slide["notes"].append(line)
            elif line.startswith("Notes:"):
                in_notes = True
                slide["notes"].append(line[len("Notes:"):].strip())
            elif line.startswith("# "):
                slide["title"] = line[2:].strip()
            elif line.startswith("## "):
                slide["subtitle"] = line[3:].strip()
            elif IMAGE.search(line):
                slide["image"] = IMAGE.search(line).group(2)
            elif line.lstrip().startswith("|"):
                slide["table"].append(line)
            elif re.match(r"^\s*[-*]\s+", line):
                slide["bullets"].append(re.sub(r"^\s*[-*]\s+", "", line))
        slide["notes"] = "\n".join(slide["notes"]).strip()
        slides.append(slide)
    return slides


def _text(frame, text, size, color=INK, bold=False):
    paragraph = frame.paragraphs[0] if not frame.paragraphs[0].runs else frame.add_paragraph()
    for i, part in enumerate(re.split(r"\*\*", text)):
        if part:
            run = paragraph.add_run()
            run.text = part.replace("`", "")
            run.font.size, run.font.bold = PptPt(size), bold or i % 2 == 1
            run.font.color.rgb = PptColor.from_string(color)
            run.font.name = "Segoe UI"
    return paragraph


def build_deck(deck_md, out_path):
    deck_md, out_path = Path(deck_md), Path(out_path)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    slides = parse_deck(deck_md.read_text(encoding="utf-8"))
    for number, spec in enumerate(slides, 1):
        slide = prs.slides.add_slide(blank)
        bar = slide.shapes.add_shape(1, 0, 0, Inches(0.18), prs.slide_height)
        bar.fill.solid(); bar.fill.fore_color.rgb = PptColor.from_string(ACCENT); bar.line.fill.background()
        title = slide.shapes.add_textbox(Inches(0.55), Inches(0.35), Inches(12.2), Inches(0.9)).text_frame
        title.word_wrap = True
        _text(title, spec["title"], 28 if number > 1 else 36, bold=True)
        top = Inches(1.25)
        if spec["subtitle"]:
            sub = slide.shapes.add_textbox(Inches(0.55), Inches(1.15), Inches(12.2), Inches(0.6)).text_frame
            sub.word_wrap = True
            _text(sub, spec["subtitle"], 16, SECONDARY)
            top = Inches(1.8)
        has_image, has_text = spec["image"] is not None, bool(spec["bullets"] or spec["table"])
        text_width = Inches(5.0) if has_image else Inches(12.2)
        if spec["bullets"]:
            box = slide.shapes.add_textbox(Inches(0.55), top, text_width, Inches(5.2)).text_frame
            box.word_wrap = True
            for bullet in spec["bullets"]:
                p = _text(box, "• " + bullet, 15 if has_image else 18)
                p.space_after = PptPt(8)
        if spec["table"]:
            rows = _table_rows(spec["table"])
            height = Inches(0.42) * len(rows)
            y = top + (Inches(0.3) * (len(spec["bullets"]) * 1.6) if spec["bullets"] else 0)
            shape = slide.shapes.add_table(len(rows), len(rows[0]), Inches(0.55), int(y), text_width, int(height))
            for r, row in enumerate(rows):
                for c, value in enumerate(row):
                    cell = shape.table.cell(r, c)
                    cell.text = ""
                    _text(cell.text_frame, value, 12, "FFFFFF" if r == 0 else INK, bold=r == 0)
        if has_image:
            image_path = (deck_md.parent / spec["image"]).resolve()
            left = Inches(5.8) if has_text else Inches(1.2)
            max_w, max_h = (Inches(7.2) if has_text else Inches(10.9)), prs.slide_height - top - Inches(0.45)
            picture = slide.shapes.add_picture(str(image_path), left, top)
            scale = min(max_w / picture.width, max_h / picture.height)
            picture.width, picture.height = int(picture.width * scale), int(picture.height * scale)
        footer = slide.shapes.add_textbox(Inches(0.55), Inches(7.05), Inches(12.2), Inches(0.35)).text_frame
        _text(footer, f"Retention Lab | Profit-aware churn & retention targeting | {number}/{len(slides)}", 10, "898781")
        slide.notes_slide.notes_text_frame.text = spec["notes"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out_path)
    return out_path, slides


def deck_lint(slides, min_slides=12, max_slides=15, max_bullets=6, max_chars=110):
    problems = []
    if not min_slides <= len(slides) <= max_slides:
        problems.append(f"{len(slides)} slides; expected {min_slides}-{max_slides}")
    for i, s in enumerate(slides, 1):
        if not s["notes"]:
            problems.append(f"slide {i} has no speaker notes")
        if len(s["bullets"]) > max_bullets:
            problems.append(f"slide {i} has {len(s['bullets'])} bullets")
        problems += [f"slide {i} bullet too long ({len(b)} chars)" for b in s["bullets"] if len(b) > max_chars]
    return problems


def export(run=None, pdf="auto"):
    run = run or latest_run()
    reports = ROOT / "reports"
    brief_md, brief_docx, brief_pdf = reports / "executive-brief.md", reports / "executive-brief.docx", reports / "executive-brief.pdf"
    deck_md, deck_pptx, deck_pdf = reports / "presentation/deck.md", reports / "presentation/retention-deck.pptx", reports / "presentation/retention-deck.pdf"
    markdown_to_docx(brief_md, brief_docx, image_width_cm=15)
    _, slides = build_deck(deck_md, deck_pptx)
    manifest = {"run_id": run.name, "created_at_utc": now(), "brief_words": len(re.sub(r"<!--.*?-->", "", brief_md.read_text(encoding="utf-8"), flags=re.S).split()),
                "slides": len(slides), "slides_with_notes": sum(bool(s["notes"]) for s in slides), "deck_lint": deck_lint(slides)}
    if pdf != "skip":
        try:
            docx_to_pdf(brief_docx, brief_pdf)
            manifest["brief_pages"] = pdf_page_count(brief_pdf)
            pptx_to_pdf(deck_pptx, deck_pdf)
            manifest["deck_pdf_pages"] = pdf_page_count(deck_pdf)
        except ExportUnavailable as exc:
            if pdf == "require":
                raise
            manifest["pdf_error"] = str(exc)
    manifest["sha256"] = {str(p.relative_to(ROOT)).replace("\\", "/"): digest(p.read_bytes()) for p in [brief_docx, brief_pdf, deck_pptx, deck_pdf] if p.exists()}
    write_json(reports / "deliverables-manifest.json", manifest)
    return manifest
