"""Portable exports of the active profile; no account secrets are included."""

import csv
import io
import os
import tempfile
from xml.sax.saxutils import escape


def rows_for(kind, data, bank):
    if kind == "history":
        keys = [
            "date",
            "subject",
            "mode",
            "total",
            "correct",
            "incorrect",
            "accuracy",
            "score",
            "timed_out",
            "unanswered",
        ]
        return keys, [[r.get(k, "") for k in keys] for r in data["history"]]
    keys = [
        "id",
        "subject",
        "question",
        "last_answer",
        "answer",
        "explanation",
        "count",
        "last_seen",
    ]
    rows = []
    for qid, record in data["wrong"].items():
        q = bank.get(qid)
        rows.append(
            [
                qid,
                q.subject if q else "",
                q.question if q else "[Deleted question]",
                record.get("last_answer", ""),
                q.answer if q else "",
                q.explanation if q else "",
                record.get("count", 0),
                record.get("last_seen", ""),
            ]
        )
    return keys, rows


def export_progress(path, kind, format, data, bank):
    keys, rows = rows_for(kind, data, bank)
    if format == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)

        # Spreadsheet applications must treat question text as text, not formulas.
        def safe(value):
            value = str(value)
            return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value

        writer.writerow(keys)
        writer.writerows([[safe(v) for v in row] for row in rows])
        payload = stream.getvalue().encode("utf-8-sig")
    else:
        try:
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
        except ImportError as exc:
            raise ValueError(
                "PDF export requires reportlab. Run: python -m pip install -r requirements.txt"
            ) from exc
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        style = ParagraphStyle(
            "report", fontName="STSong-Light", fontSize=10, leading=15, wordWrap="CJK"
        )
        stream = io.BytesIO()
        story = [Paragraph("Quiz Studio - " + kind, style), Spacer(1, 16)]
        for index, row in enumerate(rows, 1):
            story.append(Paragraph(str(index) + ".", style))
            for key, value in zip(keys, row):
                story.append(
                    Paragraph(escape(key + ": " + str(value)).replace("\n", "<br/>"), style)
                )
            story.append(Spacer(1, 14))
        if not rows:
            story.append(Paragraph("No records", style))
        SimpleDocTemplate(
            stream, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40
        ).build(story)
        payload = stream.getvalue()
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
