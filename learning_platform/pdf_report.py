"""Printable reports with question artwork and readable, paginated sections."""

import io
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape


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
        fontName=font,
        fontSize=10,
        leading=16,
        textColor=colors.HexColor("#243746"),
        wordWrap="CJK",
        spaceAfter=6,
    )
    title = ParagraphStyle(
        "title",
        parent=body,
        fontSize=24,
        leading=32,
        textColor=colors.HexColor("#146A99"),
        spaceAfter=14,
    )
    heading = ParagraphStyle(
        "heading", parent=body, fontSize=14, leading=21, spaceBefore=16, keepWithNext=True
    )

    def para(text, style=body):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)

    root = Path(__file__).resolve().parent.parent

    def art(value, width=260, height=150):
        if not value:
            return []
        path = (root / value).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            return [para("图片不可用")]
        try:
            image = Image(str(path))
            ratio = min(width / image.imageWidth, height / image.imageHeight, 1)
            image.drawWidth = image.imageWidth * ratio
            image.drawHeight = image.imageHeight * ratio
            image.hAlign = "LEFT"
            return [image, Spacer(1, 8)]
        except Exception:
            return [para("图片无法读取")]

    history = data["history"]
    total = sum(r["total"] for r in history)
    correct = sum(r["correct"] for r in history)
    story = [
        para("QUIZ STUDIO", heading),
        para("学习成绩报告" if kind == "history" else "错题复习报告", title),
        para("生成时间：" + datetime.now().strftime("%Y-%m-%d %H:%M")),
    ]
    summary = Table(
        [
            [
                para("完成练习：" + str(len(history))),
                para("累计答题：" + str(total)),
                para("正确率：" + (f"{correct / total:.1%}" if total else "—")),
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
        for name in ("english", "mathematics", "science"):
            if any(name[:4] in r["subject"].lower() for r in history):
                story += art("assets/images/subjects/" + name + ".png", 170, 65)
        for i, r in enumerate(reversed(history), 1):
            story += [
                para(f"{i:02}  {r['subject']} · {r['date']}", heading),
                para(
                    f"得分 {r['score']}/{r['max_score']}    正确率 {r['accuracy']}%    正确 {r['correct']}  错误 {r['incorrect']}"
                ),
                para("模式：" + ("错题复习" if r["mode"] == "review" else "练习")),
            ]
            if r.get("timed_out"):
                story.append(para(f"超时结束 · 未答 {r.get('unanswered', 0)} 题"))
    else:
        for i, (qid, r) in enumerate(data["wrong"].items(), 1):
            if i > 1:
                from reportlab.platypus import PageBreak
                story.append(PageBreak())
            q = bank.get(qid)
            story.append(para(f"{i:02}  {qid} · 错误次数 {r['count']}", heading))
            if not q:
                story.append(para("题目已从题库删除。最近答案：" + r.get("last_answer", "")))
                continue
            story += [para(q.subject + " / " + q.topic), para(q.question)]
            story += art(q.question_image)
            for index, option in enumerate(q.options):
                story.append(para(f"{chr(65 + index)}: {option}"))
                if q.option_images:
                    story += art(q.option_images[index], 170, 90)
            story += [
                para("你的答案：" + r.get("last_answer", "")),
                para("正确答案：" + q.answer),
                para("解析：" + q.explanation),
                para("最近错误：" + r.get("last_seen", "")),
                Spacer(1, 12),
            ]
    if not (history if kind == "history" else data["wrong"]):
        story.append(para("暂无记录。"))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D5E1EB"))
        canvas.line(42, 38, 553, 38)
        canvas.setFont(font, 9)
        canvas.setFillColor(colors.HexColor("#607784"))
        canvas.drawString(42, 24, "QUIZ STUDIO · 学习记录")
        canvas.drawRightString(553, 24, f"第 {doc.page} 页")
        canvas.restoreState()

    stream = io.BytesIO()
    SimpleDocTemplate(
        stream,
        pagesize=(595, 842),
        leftMargin=42,
        rightMargin=42,
        topMargin=36,
        bottomMargin=54,
        title="Quiz Studio Learning Report",
        author="Quiz Studio",
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()
