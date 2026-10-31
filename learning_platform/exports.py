"""Portable exports of the active profile; no account secrets are included."""

import csv
import io
import json
import os
import tempfile


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
        "topic",
        "difficulty",
        "type",
        "question",
        "options",
        "question_image",
        "option_images",
        "last_answer",
        "answer",
        "explanation",
        "count",
        "last_seen",
        "import_source",
    ]
    rows = []
    for qid, record in data["wrong"].items():
        q = bank.get(qid)
        rows.append(
            [
                f"WRONG-{qid}",
                q.subject if q else "",
                q.topic if q else "Imported mistakes",
                q.difficulty if q else "review",
                q.type if q else "single_choice",
                q.question if q else "[Deleted question]",
                json.dumps(q.options, ensure_ascii=False) if q else "[]",
                q.question_image if q and q.question_image else "",
                json.dumps(q.option_images, ensure_ascii=False) if q and q.option_images else "",
                record.get("last_answer", ""),
                q.answer if q else "",
                q.explanation if q else "",
                record.get("count", 0),
                record.get("last_seen", ""),
                "wrong_export",
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
        from .pdf_report import build_report

        payload = build_report(kind, data, bank)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
