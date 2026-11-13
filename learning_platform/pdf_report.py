"""Printable reports with question artwork and readable, paginated sections."""

import io
from datetime import datetime
from itertools import groupby
from pathlib import Path
from xml.sax.saxutils import escape

from .history_notes import display_time
from .models import option_label


def build_report(kind, data, bank):
    try:
        from reportlab.lib import colors
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import (
            Image,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise ValueError("PDF export requires: python -m pip install -r requirements.txt") from exc
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    font = "STSong-Light"
    local_font = Path("C:/Windows/Fonts/simsun.ttc")
    if local_font.exists():
        from reportlab.pdfbase.ttfonts import TTFont

        pdfmetrics.registerFont(TTFont("ReportChinese", str(local_font), subfontIndex=0))
        font = "ReportChinese"
    body = ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=10,
        leading=16,
        textColor=colors.HexColor("#243746"),
        wordWrap="CJK",
        spaceAfter=6,
    )
    title = ParagraphStyle(
        "title",
        parent=body,
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=32,
        textColor=colors.HexColor("#146A99"),
        spaceAfter=14,
    )
    heading = ParagraphStyle(
        "heading", parent=body, fontSize=14, leading=21, spaceBefore=16, keepWithNext=True
    )

    def para(text, style=body):
        def needs_unicode(character):
            try:
                character.encode("cp1252")
                return False
            except UnicodeEncodeError:
                return True

        fragments = []
        for unicode_run, characters in groupby(str(text), needs_unicode):
            fragment = escape("".join(characters)).replace("\n", "<br/>")
            # Keep Latin text in Helvetica while supporting full-width punctuation
            # and Chinese content without converting or replacing user text.
            fragments.append(f'<font name="{font}">{fragment}</font>' if unicode_run else fragment)
        return Paragraph("".join(fragments), style)

    root = Path(__file__).resolve().parent.parent

    def art(value, width=260, height=150):
        if not value:
            return []
        path = (root / value).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            return [para("Image unavailable")]
        try:
            image = Image(str(path))
            ratio = min(width / image.imageWidth, height / image.imageHeight, 1)
            image.drawWidth = image.imageWidth * ratio
            image.drawHeight = image.imageHeight * ratio
            image.hAlign = "LEFT"
            return [image, Spacer(1, 8)]
        except Exception:
            return [para("Image could not be loaded")]

    history = data["history"]
    total = sum(r["total"] for r in history)
    correct = sum(r["correct"] for r in history)
    generated = datetime.now().astimezone()
    offset = generated.strftime("%z")
    story = [
        para("WhaleMate", heading),
        para(
            "Learning Progress Report" if kind == "history" else "Wrong-Question Review Report",
            title,
        ),
        para("Generated: " + generated.strftime("%Y/%m/%d %H:%M:%S")),
        para("Time zone: UTC" + offset[:3] + ":" + offset[3:]),
    ]
    summary = Table(
        [
            [
                para("Sessions: " + str(len(history))),
                para("Questions answered: " + str(total)),
                para("Accuracy: " + (f"{correct / total:.1%}" if total else "N/A")),
            ]
        ],
        colWidths=[170, 170, 170],
    )
    summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EAF3F9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story += [summary, Spacer(1, 16)]
    if kind == "history":
        for i, r in enumerate(reversed(history), 1):
            story += [
                para(f"{i:02}  {r['subject']} · {display_time(r['date'])}", heading),
                para(
                    f"Score {r['score']}/{r['max_score']}    Accuracy {r['accuracy']}%    Correct {r['correct']}  Incorrect {r['incorrect']}"
                ),
                para("Mode: " + ("Review" if r["mode"] == "review" else "Quiz")),
            ]
            if r.get("timed_out"):
                story.append(para(f"Time limit reached · Unanswered: {r.get('unanswered', 0)}"))
            story.append(para("Liked: " + ("Yes" if r.get("liked") else "No")))
            if r.get("note"):
                story.append(para("Note:\n" + r["note"]))
    else:
        for i, (qid, r) in enumerate(data["wrong"].items(), 1):
            if i > 1:
                from reportlab.platypus import PageBreak

                story.append(PageBreak())
            q = bank.get(qid)
            story.append(para(f"{i:02}  {qid} · Mistakes: {r['count']}", heading))
            if not q:
                story.append(
                    para("This question was deleted. Last answer: " + r.get("last_answer", ""))
                )
                if r.get("last_seen"):
                    story.append(para("Last attempted: " + display_time(r["last_seen"])))
                continue
            story += [para(q.subject + " / " + q.topic), para(q.question)]
            story += art(q.question_image)
            for index, option in enumerate(q.options):
                story.append(para(f"{option_label(index)}: {option}"))
                if q.option_images:
                    story += art(q.option_images[index], 170, 90)
            story += [
                para("Your answer: " + r.get("last_answer", "")),
                para("Correct answer: " + q.answer),
                para("Explanation: " + q.explanation),
                para(
                    "Last attempted: "
                    + (display_time(r["last_seen"]) if r.get("last_seen") else "Not recorded")
                ),
                Spacer(1, 12),
            ]
    if not (history if kind == "history" else data["wrong"]):
        story.append(para("No records available."))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D5E1EB"))
        canvas.line(42, 38, 553, 38)
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor("#607784"))
        canvas.drawString(42, 24, "WhaleMate · Learning records")
        canvas.drawRightString(553, 24, f"Page {doc.page}")
        canvas.restoreState()

    stream = io.BytesIO()
    SimpleDocTemplate(
        stream,
        pagesize=(595, 842),
        leftMargin=42,
        rightMargin=42,
        topMargin=36,
        bottomMargin=54,
        title="Learning Progress Report" if kind == "history" else "Wrong-Question Review Report",
        author="WhaleMate",
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()
