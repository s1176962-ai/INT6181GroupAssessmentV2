"""Queryable learning journal with profile-isolated likes and notes."""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import modern
from . import ui_tokens as T
from .date_picker import DatePicker
from .exports import export_progress
from .history_notes import HistoryNotes, display_time, query_history
from .storage import DataError
from .widgets import card_frame


class HistoryPage:
    def __init__(self, app):
        self.app = app
        self.tr = app.tr
        self.notes = HistoryNotes(app.progress.store.path.parent)
        self.start = tk.StringVar()
        self.end = tk.StringVar()
        self.liked = tk.StringVar(value=self.tr("全部"))
        self.commented = tk.StringVar(value=self.tr("全部"))
        self.matches = []

    def show(self):
        app = self.app
        app._nav_key = "history"
        app.clear(self.tr("学习统计与历史"), show_heading=False)
        toolbar = card_frame(app.body, pad=16)
        toolbar.pack(fill="x", pady=(0, T.px(12)))
        fields = (
            ("开始日期", self.start),
            ("结束日期", self.end),
            ("收藏筛选", self.liked),
            ("笔记筛选", self.commented),
        )
        for index, (title, variable) in enumerate(fields):
            field = ttk.Frame(toolbar)
            field.grid(row=0, column=index, sticky="ew", padx=6)
            toolbar.columnconfigure(index, weight=1)
            ttk.Label(field, text=self.tr(title)).pack(anchor="w")
            if index < 2:
                DatePicker(field, variable, self.tr).pack(fill="x", pady=5)
            else:
                ttk.Combobox(
                    field,
                    textvariable=variable,
                    state="readonly",
                    width=12,
                    values=[self.tr("全部"), self.tr("是"), self.tr("否")],
                ).pack(fill="x", pady=5)
        ttk.Label(
            toolbar, text=self.tr("日期格式 yyyy/mm/dd，留空不限日期"), style="Muted.TLabel"
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=6)
        modern.SoftButton(toolbar, text=self.tr("查询"), command=self.refresh, width=T.px(90)).grid(
            row=1, column=3, sticky="e"
        )
        self.summary = ttk.Frame(app.body)
        self.summary.pack(fill="x", pady=(0, T.px(12)))
        self.feed = ttk.Frame(app.body)
        self.feed.pack(fill="x")
        dock = app._action_dock()
        modern.SoftButton(
            dock, text=self.tr("导出查询结果 PDF"), command=self.export, width=T.px(240)
        ).pack(side="left")
        self.refresh()

    def refresh(self):
        try:
            records = self.app.progress.load()["history"]
            notes = self.notes.load()
            choices = {self.tr("全部"): "all", self.tr("是"): "yes", self.tr("否"): "no"}
            matches = query_history(
                records,
                notes,
                self.start.get().strip(),
                self.end.get().strip(),
                choices[self.liked.get()],
                choices[self.commented.get()],
            )
        except (ValueError, DataError) as exc:
            messagebox.showerror(self.tr("查询失败"), str(exc), parent=self.app.root)
            return
        self.matches = matches
        for parent in (self.summary, self.feed):
            for child in parent.winfo_children():
                child.destroy()
        total = sum(item["total"] for item in matches)
        correct = sum(item["correct"] for item in matches)
        for index, (label, value) in enumerate(
            (
                ("练习次数", len(matches)),
                ("已答题数", total),
                ("答对题数", correct),
                ("正确率", f"{correct / total:.1%}" if total else "0%"),
            )
        ):
            cell = card_frame(self.summary, pad=16)
            cell.grid(row=0, column=index, sticky="ew", padx=(0, 8))
            self.summary.columnconfigure(index, weight=1)
            tk.Label(cell, text=str(value), bg=T.SURFACE, fg=T.PRIMARY, font=T.TYPE_HERO).pack(
                anchor="w"
            )
            tk.Label(
                cell, text=self.tr(label), bg=T.SURFACE, fg=T.TEXT_MUTED, font=T.TYPE_CAPTION
            ).pack(anchor="w")
        if not matches:
            ttk.Label(self.feed, text=self.tr("没有符合条件的记录")).pack(pady=20)
        for record in matches:
            card = card_frame(self.feed, pad=16)
            card.pack(fill="x", pady=(0, 10))
            header = tk.Frame(card, bg=T.SURFACE)
            header.pack(fill="x")
            tk.Label(
                header, text=record["subject"], bg=T.SURFACE, fg=T.TEXT, font=T.TYPE_HEADING
            ).pack(side="left")
            color = T.PRIMARY if record["liked"] else "#FFFFFF"
            like_button = tk.Button(
                header,
                text="♥" if record["liked"] else "♡",
                width=3,
                fg=color,
                activeforeground=color,
                bg=T.SURFACE,
                activebackground=T.SURFACE,
                relief="flat",
                bd=0,
                font=T.TYPE_HEADING,
                cursor="hand2",
                highlightthickness=0,
            )
            like_button.configure(command=lambda r=record, b=like_button: self.like(r, b))
            like_button.pack(side="right", padx=4)
            ttk.Button(
                header,
                text="✎",
                width=3,
                command=lambda r=record: self.edit_note(r),
                style="Tool.TButton",
            ).pack(side="right", padx=4)
            tk.Label(
                card,
                text=f"{display_time(record['date'])}  ·  {self.tr('错题复习') if record['mode'] == 'review' else self.tr('练习')}",
                bg=T.SURFACE,
                fg=T.TEXT_MUTED,
                font=T.TYPE_CAPTION,
            ).pack(anchor="w", pady=(4, 8))
            tk.Label(
                card,
                text=self.tr(
                    "得分 {0}/{1} · 正确率 {2}% · 共 {3} 题",
                    record["score"],
                    record["max_score"],
                    f"{record['accuracy']:.1f}",
                    record["total"],
                ),
                bg=T.SURFACE,
                fg=T.TEXT,
                font=T.TYPE_BODY,
            ).pack(anchor="w")
            if record["note"]:
                note = tk.Label(
                    card,
                    text="Note: " + record["note"],
                    bg=T.SURFACE,
                    fg=T.TEXT_SECONDARY,
                    font=T.TYPE_BODY,
                    justify="left",
                    anchor="w",
                )
                note.pack(fill="x", pady=(8, 0))
                note.bind(
                    "<Configure>",
                    lambda e, widget=note: widget.configure(wraplength=max(100, e.width - 10)),
                )

    def like(self, record, button=None):
        try:
            self.notes.save(record["id"], not record["liked"], record["note"])
        except DataError as exc:
            messagebox.showerror(self.tr("保存失败"), str(exc), parent=self.app.root)
            return
        if button is None or self.liked.get() != self.tr("全部"):
            self.refresh()
            return
        record["liked"] = not record["liked"]
        color = T.PRIMARY if record["liked"] else "#FFFFFF"
        button.configure(text="♥" if record["liked"] else "♡", fg=color, activeforeground=color)

    def edit_note(self, record):
        dialog = tk.Toplevel(self.app.root)
        dialog.title(self.tr("学习笔记"))
        dialog.transient(self.app.root)
        dialog.grab_set()
        editor = tk.Text(dialog, height=10, width=55, wrap="word", font=T.TYPE_BODY)
        editor.pack(fill="both", expand=True, padx=16, pady=16)
        editor.insert("1.0", record["note"])

        def save():
            try:
                self.notes.save(record["id"], record["liked"], editor.get("1.0", "end-1c"))
            except DataError as exc:
                messagebox.showerror(self.tr("保存失败"), str(exc), parent=dialog)
                return
            dialog.destroy()
            self.refresh()

        ttk.Button(dialog, text=self.tr("保存笔记"), command=save).pack(pady=(0, 16))

    def export(self):
        if not self.app.require_learning_account():
            return
        path = filedialog.asksaveasfilename(
            parent=self.app.root, defaultextension=".pdf", filetypes=[("PDF", "*.pdf")]
        )
        if path:
            try:
                # Snapshot exactly the displayed query, including annotations.
                export_progress(
                    Path(path),
                    "history",
                    "pdf",
                    {"history": list(reversed(self.matches)), "wrong": {}},
                    self.app.by_id,
                )
            except (ValueError, OSError) as exc:
                messagebox.showerror(self.tr("导出失败"), str(exc), parent=self.app.root)
                return
            messagebox.showinfo(self.tr("导出完成"), str(path), parent=self.app.root)
