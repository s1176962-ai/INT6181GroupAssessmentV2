"""Theme-compatible calendar picker without extra runtime dependencies."""

import calendar
import tkinter as tk
from datetime import date, datetime
from tkinter import ttk

from . import ui_tokens as T


class DatePicker(ttk.Frame):
    def __init__(self, parent, variable, translator):
        super().__init__(parent)
        self.variable = variable
        self.tr = translator
        self.popup = None
        ttk.Entry(self, textvariable=variable, width=12).pack(side="left", fill="x", expand=True)
        ttk.Button(self, text="▦", width=3, command=self.open).pack(side="right", padx=(4, 0))

    def open(self):
        if self.popup is not None and self.popup.winfo_exists():
            self.popup.lift()
            return
        try:
            chosen = datetime.strptime(self.variable.get(), "%Y/%m/%d").date()
        except ValueError:
            chosen = date.today()
        self.year, self.month = chosen.year, chosen.month
        self.popup = tk.Toplevel(self)
        self.popup.title(self.tr("选择日期"))
        self.popup.transient(self.winfo_toplevel())
        self.popup.resizable(False, False)
        self.popup.configure(bg=T.SURFACE)
        self.popup.geometry(f"+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height()}")
        self.popup.bind("<Escape>", lambda _e: self.popup.destroy())
        self.draw()

    def select(self, value):
        self.variable.set(value.strftime("%Y/%m/%d") if value else "")
        self.popup.destroy()

    def move(self, delta):
        absolute = self.year * 12 + self.month - 1 + delta
        self.year, month = divmod(absolute, 12)
        self.year = min(9999, max(1, self.year))
        self.month = month + 1
        self.draw()

    def draw(self):
        for child in self.popup.winfo_children():
            child.destroy()
        host = tk.Frame(self.popup, bg=T.SURFACE, padx=T.px(12), pady=T.px(12))
        host.pack()
        ttk.Button(host, text="‹", width=3, command=lambda: self.move(-1)).grid(row=0, column=0)
        tk.Label(
            host,
            text=f"{self.year:04d} / {self.month:02d}",
            bg=T.SURFACE,
            fg=T.TEXT,
            font=T.TYPE_HEADING,
        ).grid(row=0, column=1, columnspan=5, pady=8)
        ttk.Button(host, text="›", width=3, command=lambda: self.move(1)).grid(row=0, column=6)
        labels = (
            "Mon Tue Wed Thu Fri Sat Sun" if self.tr.language == "en" else "一 二 三 四 五 六 日"
        ).split()
        for column, label in enumerate(labels):
            tk.Label(host, text=label, bg=T.SURFACE, fg=T.TEXT_MUTED, font=T.TYPE_CAPTION).grid(
                row=1, column=column, pady=6
            )
        for row, week in enumerate(calendar.monthcalendar(self.year, self.month), 2):
            for column, day in enumerate(week):
                if day:
                    value = date(self.year, self.month, day)
                    ttk.Button(
                        host, text=str(day), width=4, command=lambda d=value: self.select(d)
                    ).grid(row=row, column=column, padx=1, pady=2)
        ttk.Button(host, text=self.tr("今天"), command=lambda: self.select(date.today())).grid(
            row=9, column=0, columnspan=3, sticky="ew", pady=(10, 0)
        )
        ttk.Button(host, text=self.tr("清空日期"), command=lambda: self.select(None)).grid(
            row=9, column=4, columnspan=3, sticky="ew", pady=(10, 0)
        )
