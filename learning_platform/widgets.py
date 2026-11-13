"""Reusable Tkinter drawing helpers. No extra dependencies."""

import tkinter as tk

from . import ui_tokens as T
from .ui_tokens import FONT


def subject_icon(parent, subject, size=40, bg=None):
    """Simple line marks for English / Mathematics / Science."""
    bg = bg or T.SURFACE
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
    canvas.create_oval(pad, pad, size - pad, size - pad, outline=T.PRIMARY, width=2)
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
            outline=T.PRIMARY,
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
            outline=T.PRIMARY,
            width=2,
        )
        canvas.create_line(cx, pad + 8, cx, cy + 4, fill=T.PRIMARY, width=2)
        canvas.create_oval(cx - 3, pad + 6, cx + 3, pad + 12, outline=T.PRIMARY, width=2)
    else:
        canvas.create_text(cx, cy, text="Aa", fill=T.PRIMARY, font=(FONT, 11, "bold"))
    return canvas


_GRID = (4, 8, 12, 16, 24, 32)


def card_frame(parent, bg=None, pad=16):
    """Rounded soft card used by the legacy pages (no 1px hard border).

    The background is a Canvas drawn behind the children: Tk stacks later
    children above earlier ones, so callers can keep packing into the returned
    Frame exactly as before. Callers are rebuilt on theme change, so the
    token colours are always read fresh at draw time.
    """
    from . import modern

    face = bg or T.SURFACE
    # 8pt grid: legacy callers pass 14/18/22, snap to the nearest allowed step.
    snapped = min(_GRID, key=lambda step: abs(step - pad))
    inset = T.px(snapped)
    shell = modern.parent_bg(parent)
    frame = tk.Frame(
        parent, bg=shell, padx=inset, pady=inset,
        highlightthickness=0, bd=0,
    )
    canvas = tk.Canvas(
        frame, bg=shell, highlightthickness=0, bd=0, takefocus=0
    )
    # Tk's placer sizes/places against the Frame's *content* box (after padx /
    # pady), so relwidth=1 would clip the drawing to the inner rectangle and
    # let full-width children cover the rounded corners. Offset by -inset and
    # size explicitly so the canvas spans the whole Frame, padding included.
    canvas.place(x=-inset, y=-inset, width=1, height=1)

    last_size = [None]

    def draw(_event=None):
        w, h = frame.winfo_width(), frame.winfo_height()
        if last_size[0] == (w, h):
            return
        last_size[0] = (w, h)
        canvas.place(x=-inset, y=-inset, width=max(w, 1), height=max(h, 1))
        canvas.delete("all")
        if w <= 2 or h <= 2:
            return
        radius = T.px(T.RADIUS_CARD)
        near = T.px(T.SHADOW_OFFSET_NEAR)
        far = T.px(T.SHADOW_OFFSET_FAR)
        modern.round_rect(canvas, 0, far, w, h, radius, fill=T.SHADOW_FAR)
        modern.round_rect(canvas, 0, near, w - near, h - near, radius, fill=T.SHADOW_NEAR)
        modern.round_rect(canvas, 0, 0, w - near, h - far, radius, fill=face)

    frame.bind("<Configure>", draw, add="+")
    return frame


def bind_whole(widget, callback):
    widget.bind("<Button-1>", lambda _e: callback())
    for child in widget.winfo_children():
        bind_whole(child, callback)
