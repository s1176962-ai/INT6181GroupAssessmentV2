"""Reusable Tkinter drawing helpers. No extra dependencies."""

import tkinter as tk

from .ui_tokens import BORDER, FONT, PRIMARY, SURFACE


def subject_icon(parent, subject, size=40, bg=SURFACE):
    """Simple line marks for English / Mathematics / Science."""
    canvas = tk.Canvas(
        parent,
        width=size,
        height=size,
        bg=bg,
        highlightthickness=0,
        bd=0,
        takefocus=0,
    )
    pad = 5
    canvas.create_oval(pad, pad, size - pad, size - pad, outline=PRIMARY, width=2)
    key = (subject or "").lower()
    cx = size / 2
    cy = size / 2
    if "math" in key:
        canvas.create_polygon(
            cx,
            pad + 8,
            size - pad - 8,
            size - pad - 8,
            pad + 8,
            size - pad - 8,
            outline=PRIMARY,
            fill="",
            width=2,
        )
    elif "sci" in key:
        canvas.create_arc(
            pad + 8,
            pad + 6,
            size - pad - 8,
            size - pad - 4,
            start=200,
            extent=140,
            style="arc",
            outline=PRIMARY,
            width=2,
        )
        canvas.create_line(cx, pad + 8, cx, cy + 4, fill=PRIMARY, width=2)
        canvas.create_oval(cx - 3, pad + 6, cx + 3, pad + 12, outline=PRIMARY, width=2)
    else:
        canvas.create_text(cx, cy, text="Aa", fill=PRIMARY, font=(FONT, 11, "bold"))
    return canvas


def card_frame(parent, bg=SURFACE, pad=16):
    frame = tk.Frame(
        parent,
        bg=bg,
        padx=pad,
        pady=pad,
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=PRIMARY,
    )
    return frame


def bind_whole(widget, callback):
    widget.bind("<Button-1>", lambda _e: callback())
    for child in widget.winfo_children():
        bind_whole(child, callback)
