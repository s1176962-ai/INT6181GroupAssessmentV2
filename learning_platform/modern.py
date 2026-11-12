"""Canvas-painted, token-driven widgets for the light-weight Quiz Studio shell.

Tk/ttk cannot draw rounded corners, soft shadows or focus glows natively, so
every control here paints itself on a Canvas. Each clickable control implements
hover / pressed / focus / disabled and reads all colours and dimensions from
``ui_tokens`` (backed by ``tokens.py``) at draw time.

Compatibility: several widgets mimic the small part of the ttk widget protocol
that the GUI layer and its regression tests use (``cget``, ``configure``,
``state``, ``invoke``, ``current``, ``set``, ``bind``, ``event_generate``).
"""

import tkinter as tk

from . import ui_tokens as T


def parent_bg(parent):
    """Return the parent's face colour so rounded corners blend into it."""
    try:
        value = parent.cget("bg")
        if value:
            return value
    except (tk.TclError, AttributeError, KeyError):
        pass
    return T.BG


def round_rect(canvas, x1, y1, x2, y2, radius, fill=None, outline=None, width=1):
    """Paint a rounded rectangle using pieslice arcs (Tk has no round_rect)."""
    if x2 <= x1 or y2 <= y1:
        return
    r = max(0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    paint = fill or ""
    if r <= 0:
        canvas.create_rectangle(x1, y1, x2, y2, fill=paint, outline="")
    else:
        canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=paint, outline="")
        canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=paint, outline="")
        for cx, cy, start in (
            (x1, y1, 90),
            (x2 - 2 * r, y1, 0),
            (x1, y2 - 2 * r, 180),
            (x2 - 2 * r, y2 - 2 * r, 270),
        ):
            canvas.create_arc(
                cx, cy, cx + 2 * r, cy + 2 * r,
                start=start, extent=90, style="pieslice", fill=paint, outline="",
            )
    if outline and width:
        canvas.create_line(x1 + r, y1, x2 - r, y1, fill=outline, width=width)
        canvas.create_line(x1 + r, y2, x2 - r, y2, fill=outline, width=width)
        canvas.create_line(x1, y1 + r, x1, y2 - r, fill=outline, width=width)
        canvas.create_line(x2, y1 + r, x2, y2 - r, fill=outline, width=width)
        for cx, cy, start in (
            (x1, y1, 90),
            (x2 - 2 * r, y1, 0),
            (x1, y2 - 2 * r, 180),
            (x2 - 2 * r, y2 - 2 * r, 270),
        ):
            canvas.create_arc(
                cx, cy, cx + 2 * r, cy + 2 * r,
                start=start, extent=90, style="arc", outline=outline, width=width,
            )


class Interactive:
    """Shared hover / pressed / focus / disabled state machine."""

    def _init_state(self, command=None):
        self._hover = False
        self._pressed = False
        self._focused = False
        self._disabled = False
        self._command = command
        seen = set()
        for widget in (self, getattr(self, "canvas", None), getattr(self, "content", None)):
            if widget is None or id(widget) in seen:
                continue
            seen.add(id(widget))
            widget.bind("<Enter>", self._st_enter, add="+")
            widget.bind("<Leave>", self._st_leave, add="+")
            widget.bind("<ButtonPress-1>", self._st_press, add="+")
            widget.bind("<ButtonRelease-1>", self._st_release, add="+")
            widget.bind("<FocusIn>", self._st_focus_in, add="+")
            widget.bind("<FocusOut>", self._st_focus_out, add="+")

    def _st_enter(self, _event):
        self._hover = True
        self._draw()

    def _st_leave(self, _event):
        self._hover = False
        self._pressed = False
        self._draw()

    def _st_press(self, _event):
        if self._disabled:
            return
        try:
            self.focus_set()
        except (tk.TclError, AttributeError):
            pass
        self._pressed = True
        self._draw()

    def _st_release(self, _event):
        if self._disabled:
            return
        was_pressed = self._pressed
        self._pressed = False
        self._draw()
        if was_pressed:
            self._activate()

    def _st_focus_in(self, _event):
        self._focused = True
        self._draw()

    def _st_focus_out(self, _event):
        self._focused = False
        self._draw()

    def _activate(self):
        if self._command and not self._disabled:
            self._command()

    def _glow(self):
        return self._focused and not self._disabled

    def set_disabled(self, value):
        self._disabled = bool(value)
        self._draw()

    def _glow_ring(self, canvas, x1, y1, x2, y2, radius):
        if not self._glow():
            return
        g = T.px(T.FOCUS_RING)
        round_rect(
            canvas, x1 - g, y1 - g, x2 + g, y2 + g, radius + g,
            fill=T.FOCUS_GLOW,
        )


# ---------------------------------------------------------------------------
# Containers
# ---------------------------------------------------------------------------
class SoftCard(tk.Frame):
    """One white surface: 12px radius, two soft shadow bands, 24px padding."""

    def __init__(self, parent, padding=None, shadow=True, **kwargs):
        super().__init__(parent, bg=parent_bg(parent), **kwargs)
        self.radius = T.px(T.RADIUS_CARD)
        self.pad = T.px(padding if padding is not None else T.CARD_PAD)
        self.shadow = shadow
        self.canvas = tk.Canvas(self, bg=T.BG, highlightthickness=0, bd=0, takefocus=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.content = tk.Frame(self, bg=T.SURFACE)
        self.content.pack(fill="both", expand=True, padx=self.pad, pady=self.pad)
        self.bind("<Configure>", self._draw)

    def _draw(self, _event=None):
        cv = self.canvas
        cv.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 2 or h <= 2:
            return
        r = self.radius
        far = T.px(T.SHADOW_OFFSET_FAR)
        near = T.px(T.SHADOW_OFFSET_NEAR)
        if self.shadow:
            round_rect(cv, 0, far, w, h, r, fill=T.SHADOW_FAR)
            round_rect(cv, 0, near, w - near, h - near, r, fill=T.SHADOW_NEAR)
        round_rect(cv, 0, 0, w - near, h - far, r, fill=T.SURFACE)
        # The content frame is inset by 24px, so the four rounded corners stay
        # visible; the straight middle is the same SURFACE colour, i.e. seamless.

    def refresh(self):
        self.content.configure(bg=T.SURFACE)
        self.canvas.configure(bg=T.BG)
        self._draw()


class SoftPanel(tk.Frame):
    """Tinted rounded surface without a shadow (chat composer, reply area).

    Paint order matters: the Canvas is created first and the content Frame is
    packed afterwards, so the children always stack above the painted corners.
    The content is inset by ``padding``, which is what keeps the rounded corners
    visible instead of being covered by a full-width child.
    """

    def __init__(self, parent, fill=None, edge=None, padding=16, radius=None, **kwargs):
        super().__init__(parent, bg=parent_bg(parent), highlightthickness=0, bd=0, **kwargs)
        self.surface = fill or T.SURFACE
        self.edge = edge
        self.radius = T.px(radius if radius is not None else T.RADIUS_CARD)
        self.pad = T.px(padding)
        self.canvas = tk.Canvas(
            self, bg=parent_bg(parent), highlightthickness=0, bd=0, takefocus=0
        )
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.content = tk.Frame(self, bg=self.surface)
        self.content.pack(fill="both", expand=True, padx=self.pad, pady=self.pad)
        self.bind("<Configure>", self._draw)

    def _draw(self, _event=None):
        cv = self.canvas
        cv.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 2 or h <= 2:
            return
        round_rect(cv, 0, 0, w, h, self.radius, fill=self.surface)
        if self.edge:
            round_rect(
                cv, 1, 1, w - 1, h - 1, self.radius - 1,
                outline=self.edge, width=T.px(T.HAIRLINE),
            )

    def set_edge(self, color):
        """Swap the hairline colour (used for the focus ring on the composer)."""
        if color == self.edge:
            return
        self.edge = color
        self._draw()

    def refresh(self):
        self.canvas.configure(bg=parent_bg(self.master))
        self.content.configure(bg=self.surface)
        self._draw()


def hairline(parent, color=None):
    """A 1px hairline separator (no dark 1px border)."""
    line = tk.Canvas(
        parent, height=T.px(T.HAIRLINE), highlightthickness=0, bd=0,
        bg=parent_bg(parent),
    )
    line.bind(
        "<Configure>",
        lambda e: (
            line.delete("all"),
            line.create_line(0, 0, e.width, 0, fill=color or T.BORDER_LIGHT),
        ),
    )
    return line


# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------
class SoftButton(tk.Canvas, Interactive):
    """Rounded action button with four states and a ttk-like protocol."""

    def __init__(self, parent, text="", command=None, variant="primary", width=None, **kwargs):
        height = T.px(T.CONTROL_H)
        super().__init__(
            parent, height=height, width=width or T.px(140),
            bg=parent_bg(parent), highlightthickness=0, bd=0, takefocus=1, **kwargs,
        )
        self._text = text
        self._variant = variant
        self.canvas = self
        self._init_state(command)
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<KeyPress-Return>", lambda _e: self.invoke())
        self.bind("<KeyPress-space>", lambda _e: self.invoke())

    def cget(self, key):
        if key == "text":
            return self._text
        return super().cget(key)

    def configure(self, cnf=None, **kwargs):
        if not hasattr(self, "_variant"):
            return super().configure(cnf, **kwargs)
        text = kwargs.pop("text", None)
        state = kwargs.pop("state", None)
        if text is not None:
            self._text = text
        result = super().configure(cnf, **kwargs) if (cnf or kwargs) else None
        if state is not None:
            self.set_disabled(state in ("disabled", ["disabled"]))
        self._draw()
        return result

    def state(self, spec=None):
        if spec:
            for item in spec:
                if item == "disabled":
                    self._disabled = True
                elif item == "!disabled":
                    self._disabled = False
            self._draw()
        return ("disabled",) if self._disabled else ()

    def invoke(self):
        if not self._disabled and self._command:
            return self._command()
        return None

    def _activate(self):
        self.invoke()

    def _face(self):
        if self._disabled:
            return T.DISABLED_FILL, T.DISABLED_INK
        if self._variant == "primary":
            if self._pressed:
                return T.PRIMARY_ACTIVE, T.ON_PRIMARY
            if self._hover:
                return T.PRIMARY_HOVER, T.ON_PRIMARY
            return T.PRIMARY, T.ON_PRIMARY
        if self._variant == "ghost":
            if self._pressed:
                return T.PRESSED, T.TEXT
            if self._hover:
                return T.HOVER, T.TEXT
            return T.BG, T.TEXT_SECONDARY
        if self._pressed:
            return T.PRESSED, T.TEXT
        if self._hover:
            return T.HOVER, T.TEXT
        return T.SURFACE, T.TEXT

    def _draw(self):
        if not self.winfo_exists():
            return
        cv = self
        cv.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 2 or h <= 2:
            return
        r = T.px(T.RADIUS_CONTROL)
        g = T.px(T.FOCUS_RING)
        self._glow_ring(cv, g, g, w - g, h - g, r)
        fill, ink = self._face()
        round_rect(cv, g, g, w - g, h - g, r, fill=fill)
        if self._variant != "primary":
            round_rect(
                cv, g, g, w - g, h - g, r,
                outline=T.BORDER_CONTROL, width=T.px(T.HAIRLINE),
            )
        cv.create_text(w // 2, h // 2, text=self._text, fill=ink, font=T.TYPE_BUTTON)

    def refresh(self):
        self._draw()


class CircleIconButton(tk.Button, Interactive):
    """Circular 36px top-bar icon button; still a tk.Button for command=."""

    def __init__(self, parent, glyph="←", command=None, size=None, **kwargs):
        self.size = T.px(size or T.CONTROL_H)
        super().__init__(
            parent, text="", command=command, relief="flat", bd=0,
            highlightthickness=0, bg=parent_bg(parent), activebackground=parent_bg(parent),
            cursor="hand2", takefocus=1, **kwargs,
        )
        self._glyph = glyph
        self._images = {}
        self.canvas = None
        self._init_state(command)
        self.bind("<KeyPress-Return>", lambda _e: self.invoke())
        self.refresh()

    def _make_image(self, fill, ink):
        import math
        from tkinter import PhotoImage

        size = self.size
        image = PhotoImage(master=self, width=size, height=size)
        image.put(parent_bg(self.master), to=(0, 0, size, size))
        radius = size / 2
        for y in range(size):
            span = math.sqrt(max(0.0, radius**2 - (y + 0.5 - radius) ** 2))
            x1, x2 = max(0, int(radius - span)), min(size, int(radius + span) + 1)
            if x2 > x1:
                image.put(T.BORDER_CONTROL, to=(x1, y, x2, y + 1))
        for y in range(1, size - 1):
            span = math.sqrt(max(0.0, (radius - 1) ** 2 - (y + 0.5 - radius) ** 2))
            x1 = max(1, int(radius - span))
            x2 = min(size - 1, int(radius + span) + 1)
            if x2 > x1:
                image.put(fill, to=(x1, y, x2, y + 1))
        # 16px linear left arrow: 2px shaft + two diagonal head strokes.
        mid = size // 2
        image.put(ink, to=(mid - 5, mid - 1, mid + 6, mid + 1))
        for step in range(6):
            image.put(ink, to=(mid - 5 + step, mid - 1 - step,
                              mid - 3 + step, mid + 1 - step))
            image.put(ink, to=(mid - 5 + step, mid + step,
                              mid - 3 + step, mid + 2 + step))
        return image

    def _face(self):
        if self._disabled:
            return T.DISABLED_FILL, T.DISABLED_INK
        if self._pressed:
            return T.PRESSED, T.TEXT
        if self._hover:
            return T.HOVER, T.TEXT
        return T.RAISED, T.TEXT_SECONDARY

    def refresh(self):
        if not self.winfo_exists():
            return
        fill, ink = self._face()
        image = self._make_image(fill, ink)
        self._images["current"] = image
        self.configure(
            image=image, bg=parent_bg(self.master), activebackground=parent_bg(self.master)
        )

    def _draw(self):
        self.refresh()

    def _activate(self):
        if self._command and not self._disabled:
            self._command()

    def invoke(self):
        if not self._disabled and self._command:
            return self._command()
        return None


# ---------------------------------------------------------------------------
# Form controls
# ---------------------------------------------------------------------------
class Dropdown(tk.Frame, Interactive):
    """36px rounded select with a painted chevron; no native square arrow."""

    def __init__(self, parent, textvariable, values=(), height=None, **kwargs):
        self._h = T.px(height or T.CONTROL_H)
        super().__init__(parent, bg=parent_bg(parent), height=self._h, takefocus=1, **kwargs)
        self.pack_propagate(False)
        self._var = textvariable
        self._values = list(values)
        self._callbacks = []
        self._trace = self._var.trace_add("write", lambda *_: self._draw())
        self.canvas = tk.Canvas(
            self, bg=parent_bg(parent), highlightthickness=0, bd=0, takefocus=0
        )
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self._init_state()
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Destroy>", self._on_destroy)

    def _on_destroy(self, event):
        if event.widget is self and getattr(self, "_trace", None):
            try:
                self._var.trace_remove("write", self._trace)
            except (tk.TclError, ValueError):
                pass
            self._trace = None

    def _activate(self):
        self._open_menu()

    def _open_menu(self):
        if self._disabled or not self._values:
            return
        menu = tk.Menu(
            self, tearoff=0, bg=T.SURFACE, fg=T.TEXT,
            activebackground=T.PRIMARY_SOFT, activeforeground=T.PRIMARY,
            bd=0, relief="flat", font=T.TYPE_BODY,
        )
        for value in self._values:
            menu.add_command(label=str(value), command=lambda v=value: self._pick(v))
        try:
            menu.tk_popup(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height())
        finally:
            menu.grab_release()

    def _pick(self, value):
        index = self._values.index(value) if value in self._values else -1
        self.current(index)

    def current(self, index=None):
        if index is None:
            try:
                return self._values.index(self._var.get())
            except ValueError:
                return -1
        if 0 <= index < len(self._values):
            self._var.set(str(self._values[index]))
            self.event_generate("<<ComboboxSelected>>")
        return self.current()

    def set(self, value):
        self._var.set(str(value))

    def get(self):
        return self._var.get()

    def __getitem__(self, key):
        if key == "values" and hasattr(self, "_values"):
            return tuple(self._values)
        if key == "state" and hasattr(self, "_disabled"):
            return "disabled" if self._disabled else "readonly"
        return super().__getitem__(key)

    def configure(self, cnf=None, **kwargs):
        if not hasattr(self, "_values"):
            return super().configure(cnf, **kwargs)
        values = kwargs.pop("values", (cnf or {}).pop("values", None) if isinstance(cnf, dict) else None)
        if values is not None:
            self._values = list(values)
        result = super().configure(cnf, **kwargs) if (cnf or kwargs) else None
        if values is not None:
            self._draw()
        return result

    def state(self, spec=None):
        if spec:
            for item in spec:
                if item == "disabled":
                    self.set_disabled(True)
                elif item == "!disabled":
                    self.set_disabled(False)
        return ("disabled",) if self._disabled else ()

    def __setitem__(self, key, value):
        if key == "values" and hasattr(self, "_values"):
            self._values = list(value)
            self._draw()
        else:
            super().__setitem__(key, value)

    def bind(self, sequence=None, func=None, add=None):
        if sequence == "<<ComboboxSelected>>":
            if func is not None and func not in self._callbacks:
                self._callbacks.append(func)
            return None
        return super().bind(sequence, func, add)

    def event_generate(self, sequence, **kwargs):
        if sequence == "<<ComboboxSelected>>":
            for callback in list(self._callbacks):
                callback(None)
            return None
        return super().event_generate(sequence, **kwargs)

    def _draw(self):
        if not self.winfo_exists():
            return
        cv = self.canvas
        cv.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 2 or h <= 2:
            h = self._h
            w = max(w, self._h)
        r = T.px(T.RADIUS_CONTROL)
        g = T.px(T.FOCUS_RING)
        self._glow_ring(cv, g, g, w - g, h - g, r)
        fill = T.DISABLED_FILL if self._disabled else (
            T.PRESSED if self._pressed else T.HOVER if self._hover else T.SURFACE
        )
        round_rect(cv, g, g, w - g, h - g, r, fill=fill)
        round_rect(
            cv, g, g, w - g, h - g, r,
            outline=T.PRIMARY if self._glow() else T.BORDER_CONTROL,
            width=T.px(2) if self._glow() else T.px(T.HAIRLINE),
        )
        # 16px linear chevron
        cx, cy = w - g - T.px(20), h // 2
        step = T.px(4)
        ink = T.DISABLED_INK if self._disabled else T.TEXT_SECONDARY
        cv.create_line(cx - step, cy - step // 2, cx, cy + step // 2, fill=ink, width=T.px(2))
        cv.create_line(cx, cy + step // 2, cx + step, cy - step // 2, fill=ink, width=T.px(2))
        cv.create_text(
            g + T.px(T.SPACE_3), h / 2,
            text=self._var.get(), anchor="w",
            fill=T.DISABLED_INK if self._disabled else T.TEXT,
            font=T.TYPE_BODY_LARGE,
        )

    def refresh(self):
        self._draw()


class Stepper(tk.Canvas, Interactive):
    """One-piece [−] value [+] control; no native Spinbox arrows."""

    def __init__(self, parent, textvariable, maximum=20, minimum=1, **kwargs):
        self._h = T.px(T.CONTROL_H)
        super().__init__(
            parent, height=self._h, width=T.px(160), bg=parent_bg(parent),
            highlightthickness=0, bd=0, takefocus=1, **kwargs,
        )
        self._var = textvariable
        self._max = maximum
        self._min = minimum
        self._zone = None
        self.wheel_guard = lambda: False
        self._trace = self._var.trace_add("write", lambda *_: self._draw())
        self.canvas = self
        self._init_state()
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Destroy>", self._on_destroy)
        self.bind("<KeyRelease>", self._on_key)
        self.bind("<MouseWheel>", self._on_wheel)

    def _on_destroy(self, event):
        if event.widget is self and getattr(self, "_trace", None):
            try:
                self._var.trace_remove("write", self._trace)
            except (tk.TclError, ValueError):
                pass
            self._trace = None

    def _on_key(self, event):
        if self._disabled:
            return
        text = self._var.get()
        if event.keysym == "BackSpace":
            self._var.set(text[:-1] or "0")
        elif event.char and event.char.isdigit():
            self._var.set((text + event.char).lstrip("0") or "0")

    def _on_wheel(self, event):
        if self._disabled or not self.wheel_guard():
            return "break"
        try:
            value = int(self._var.get())
        except ValueError:
            value = 1
        delta = -1 if event.delta > 0 else 1
        self._var.set(str(max(self._min, min(self._max, value + delta))))
        return "break"

    def get(self):
        return self._var.get()

    def set(self, value):
        self._var.set(str(value))

    def configure(self, cnf=None, **kwargs):
        if not hasattr(self, "_max"):
            return super().configure(cnf, **kwargs)
        self._max = kwargs.pop("to", self._max)
        return super().configure(cnf, **kwargs) if (cnf or kwargs) else None

    def _activate(self):
        if self._zone == "minus":
            self.set(max(self._min, self._number() - 1))
        elif self._zone == "plus":
            self.set(min(max(self._max, self._min), self._number() + 1))

    def _number(self):
        try:
            return int(self._var.get())
        except ValueError:
            return self._min

    def _zone_at(self, x, w):
        third = T.px(40)
        if x < third:
            return "minus"
        if x > w - third:
            return "plus"
        return "value"

    def _st_press(self, event):
        super()._st_press(event)
        self._zone = self._zone_at(event.x, self.winfo_width())

    def _draw(self):
        if not self.winfo_exists():
            return
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 2 or h <= 2:
            return
        r = T.px(T.RADIUS_CONTROL)
        g = T.px(T.FOCUS_RING)
        self._glow_ring(self, g, g, w - g, h - g, r)
        fill = T.DISABLED_FILL if self._disabled else (
            T.HOVER if self._hover and not self._pressed else T.SURFACE
        )
        round_rect(self, g, g, w - g, h - g, r, fill=fill)
        round_rect(
            self, g, g, w - g, h - g, r,
            outline=T.PRIMARY if self._glow() else T.BORDER_CONTROL,
            width=T.px(2) if self._glow() else T.px(T.HAIRLINE),
        )
        third = T.px(40)
        for x in (third, w - third):
            self.create_line(x, g + T.px(8), x, h - g - T.px(8), fill=T.BORDER_LIGHT)
        ink = T.DISABLED_INK if self._disabled else T.TEXT
        active = T.PRIMARY if not self._disabled else T.DISABLED_INK
        hit = T.px(8)
        for cx, zone in ((third // 2, "minus"), (w - third // 2, "plus")):
            hot = self._hover and self._zone == zone and not self._disabled
            color = active if hot else ink
            self.create_line(cx - hit // 2, h // 2, cx + hit // 2, h // 2,
                             fill=color, width=T.px(2))
            if zone == "plus":
                self.create_line(cx, h // 2 - hit // 2, cx, h // 2 + hit // 2,
                                 fill=color, width=T.px(2))
        self.create_text(w // 2, h // 2, text=self._var.get(), font=T.TYPE_BODY_LARGE, fill=ink)

    def refresh(self):
        self._draw()


class Segmented(tk.Canvas, Interactive):
    """Grey track with a white capsule for the selected difficulty."""

    def __init__(self, parent, values=(), labels=None, variable=None, on_change=None, **kwargs):
        self._h = T.px(T.CONTROL_H)
        super().__init__(
            parent, height=self._h, width=T.px(320), bg=parent_bg(parent),
            highlightthickness=0, bd=0, takefocus=1, **kwargs,
        )
        self._values = list(values)
        self._labels = list(labels) if labels else [str(v) for v in values]
        self._var = variable
        self._on_change = on_change
        self._index = 0
        self.canvas = self
        self._init_state()
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<KeyPress-Left>", lambda _e: self._move(-1))
        self.bind("<KeyPress-Right>", lambda _e: self._move(1))

    def _move(self, delta):
        if self._disabled or not self._values:
            return
        self.select((self._index + delta) % len(self._values))

    def set_values(self, values, labels):
        self._values = list(values)
        self._labels = list(labels)
        self._index = 0
        self._draw()

    def set(self, value):
        if value in self._values:
            self._index = self._values.index(value)
            self._draw()

    def get(self):
        return self._values[self._index] if self._values else ""

    def select(self, index):
        if self._disabled or not (0 <= index < len(self._values)):
            return
        self._index = index
        if self._var is not None:
            self._var.set(self._values[index])
        self._draw()
        if self._on_change:
            self._on_change(self._values[index])

    def _activate(self):
        # _st_press stores the pointer x; recompute the segment here.
        x = getattr(self, "_press_x", 0)
        w = self.winfo_width()
        if self._values and w > 0:
            self.select(min(len(self._values) - 1, int(x / (w / len(self._values)))))

    def _st_press(self, event):
        super()._st_press(event)
        self._press_x = event.x

    def _draw(self):
        if not self.winfo_exists():
            return
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 2 or h <= 2 or not self._values:
            return
        g = T.px(T.FOCUS_RING)
        r = T.px(T.RADIUS_CONTROL)
        self._glow_ring(self, g, g, w - g, h - g, r)
        round_rect(self, g, g, w - g, h - g, r, fill=T.SEGMENT_TRACK)
        pad = T.px(4)
        inner_w = w - 2 * g - 2 * pad
        seg_w = inner_w / len(self._values)
        hover_index = None
        if self._hover and hasattr(self, "_press_x"):
            hover_index = min(len(self._values) - 1, int(self._press_x / (w / len(self._values))))
        for index, label in enumerate(self._labels):
            x1 = g + pad + index * seg_w
            x2 = x1 + seg_w
            y1, y2 = g + pad, h - g - pad
            selected = index == self._index
            if selected:
                round_rect(self, x1, y1, x2, y2, T.px(T.RADIUS_CHIP), fill=T.SEGMENT_SELECTED)
            elif self._hover and index == hover_index and not self._disabled:
                round_rect(self, x1, y1, x2, y2, T.px(T.RADIUS_CHIP), fill=T.HOVER)
            ink = T.DISABLED_INK if self._disabled else (
                T.PRIMARY if selected else T.TEXT_SECONDARY
            )
            self.create_text((x1 + x2) / 2, h / 2, text=label,
                             font=T.TYPE_BODY if selected else T.TYPE_CAPTION, fill=ink)

    def refresh(self):
        self._draw()


class Toggle(tk.Canvas, Interactive):
    """36x20 switch used by the dark-mode setting."""

    def __init__(self, parent, value=False, command=None, **kwargs):
        self._width_px = T.px(44)
        self._height_px = T.px(24)
        super().__init__(
            parent, width=self._width_px, height=self._height_px, bg=parent_bg(parent),
            highlightthickness=0, bd=0, takefocus=1, **kwargs,
        )
        self._value = bool(value)
        self.canvas = self
        self._init_state(command)
        self.bind("<KeyPress-space>", lambda _e: self.toggle())
        self._draw()

    def get(self):
        return self._value

    def set(self, value):
        self._value = bool(value)
        self._draw()

    def toggle(self):
        if self._disabled:
            return
        self._value = not self._value
        self._draw()
        if self._command:
            self._command()

    def _activate(self):
        # The release handler performs the flip; avoid flipping twice.
        return None

    def _st_release(self, event):
        if self._disabled:
            return
        self._pressed = False
        self.toggle()

    def _draw(self):
        if not self.winfo_exists():
            return
        self.delete("all")
        w, h, g = self._width_px, self._height_px, T.px(T.FOCUS_RING)
        r = h // 2
        self._glow_ring(self, g, g, w - g, h - g, r)
        track = T.DISABLED_FILL if self._disabled else (
            T.PRIMARY_HOVER if (self._hover or self._pressed) else T.PRIMARY
        )
        if not self._value:
            track = T.DISABLED_FILL if self._disabled else T.BORDER_CONTROL
        round_rect(self, g, g, w - g, h - g, r, fill=track)
        knob_r = r - T.px(4)
        cx = (w - g - knob_r - T.px(2)) if self._value else (g + knob_r + T.px(2))
        cy = h / 2
        self.create_oval(cx - knob_r, cy - knob_r, cx + knob_r, cy + knob_r,
                         fill=T.SURFACE, outline=T.BORDER_LIGHT, width=T.px(T.HAIRLINE))

    def refresh(self):
        self._draw()


# ---------------------------------------------------------------------------
# Navigation and subject cards
# ---------------------------------------------------------------------------
def nav_glyph(canvas, x, y, key, color, size):
    """Paint a 16px linear icon; no icon font or bitmap assets required."""
    s = size
    left, top = x, y - s / 2
    right, bottom = x + s, y + s / 2
    mid = (left + right) / 2
    line = max(1, T.px(1))
    if key == "home":
        canvas.create_polygon(left, y, mid, top, right, y, fill="", outline=color, width=line)
        canvas.create_rectangle(left + s * 0.18, y, right - s * 0.18, bottom,
                                fill="", outline=color, width=line)
    elif key == "practice":
        canvas.create_polygon(left + s * 0.2, top, right - s * 0.1, y,
                              left + s * 0.2, bottom, fill="", outline=color, width=line)
    elif key in ("notebook", "questions"):
        canvas.create_rectangle(left + s * 0.15, top, right - s * 0.15, bottom,
                                fill="", outline=color, width=line)
        for offset in (0.35, 0.55, 0.75):
            canvas.create_line(left + s * 0.3, top + s * offset,
                               right - s * 0.3, top + s * offset, fill=color, width=line)
    elif key == "history":
        for index, height in enumerate((0.4, 0.7, 1.0)):
            bx = left + s * (0.12 + index * 0.3)
            canvas.create_line(bx, bottom, bx, bottom - s * height,
                               fill=color, width=T.px(2))
    elif key == "settings":
        canvas.create_oval(mid - s * 0.3, y - s * 0.3, mid + s * 0.3, y + s * 0.3,
                           fill="", outline=color, width=line)
        canvas.create_oval(mid - s * 0.08, y - s * 0.08, mid + s * 0.08, y + s * 0.08,
                           fill="", outline=color, width=line)
    else:  # users
        canvas.create_oval(mid - s * 0.18, top + s * 0.05, mid + s * 0.18, y + s * 0.1,
                           fill="", outline=color, width=line)
        canvas.create_arc(left + s * 0.1, y, right - s * 0.1, bottom + s * 0.1,
                          start=0, extent=180, style="arc", outline=color, width=line)


class NavItem(tk.Frame, Interactive):
    """Sidebar row: soft-blue selected face + 3px primary bar + 8px radius."""

    def __init__(self, parent, text="", icon="", command=None, **kwargs):
        self._h = T.px(40)
        super().__init__(parent, bg=T.NAV_BG, height=self._h, takefocus=1, **kwargs)
        self.pack_propagate(False)
        self._text = text
        self._icon = icon
        self._selected = False
        self.canvas = tk.Canvas(self, bg=T.NAV_BG, highlightthickness=0, bd=0, takefocus=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self._label = tk.Label(
            self, text=text, bg=T.NAV_BG, fg=T.TEXT, font=T.TYPE_BODY_LARGE,
            anchor="w",
        )
        # Place the label to the right of the 16px glyph so it cannot cover the
        # canvas-painted icon or the 3px selected indicator.
        self._label.place(x=T.px(44), y=0, anchor="nw")
        self._init_state(command)
        self.bind("<Configure>", lambda _e: self._draw())
        for widget in (self._label,):
            widget.bind("<ButtonPress-1>", self._st_press, add="+")
            widget.bind("<ButtonRelease-1>", self._st_release, add="+")
            widget.bind("<Enter>", self._st_enter, add="+")
            widget.bind("<Leave>", self._st_leave, add="+")

    def set_text(self, text):
        self._text = text
        self._label.configure(text=text)

    def set_selected(self, selected):
        self._selected = bool(selected)
        self._draw()

    def cget(self, key):
        if key == "text":
            return self._text
        return super().cget(key)

    def _face(self):
        if self._disabled:
            return T.DISABLED_FILL, T.DISABLED_INK
        if self._selected:
            return T.NAV_SELECTED, T.PRIMARY
        if self._pressed:
            return T.PRESSED, T.TEXT
        if self._hover:
            return T.HOVER, T.TEXT
        return T.NAV_BG, T.TEXT

    def _draw(self):
        if not self.winfo_exists():
            return
        cv = self.canvas
        cv.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 2 or h <= 2:
            return
        g = T.px(T.FOCUS_RING)
        r = T.px(T.RADIUS_CHIP)
        self._glow_ring(cv, g, g, w - g, h - g, r)
        fill, ink = self._face()
        round_rect(cv, g, g, w - g, h - g, r, fill=fill)
        if self._selected:
            bar = T.px(T.NAV_INDICATOR)
            round_rect(cv, g, g + T.px(8), g + bar, h - g - T.px(8), bar // 2,
                       fill=T.PRIMARY)
        nav_glyph(cv, g + T.px(12), h / 2, self._icon, ink, T.px(T.ICON))
        self._label.configure(bg=fill, fg=ink)
        self._label.place(
            x=g + T.px(36), y=g,
            width=max(w - 2 * g - T.px(36) - T.px(T.RADIUS_CHIP), 1),
            height=max(h - 2 * g, 1),
        )

    def refresh(self):
        self._draw()


class SubjectCard(tk.Frame, Interactive):
    """Subject tile: soft-blue selected face, primary outline, check dot."""

    def __init__(self, parent, name, count_text, command=None, **kwargs):
        self._h = T.px(88)
        super().__init__(parent, bg=T.SURFACE, height=self._h, takefocus=1, **kwargs)
        self.pack_propagate(False)
        self.name = name
        self._selected = False
        self.canvas = tk.Canvas(self, bg=T.SURFACE, highlightthickness=0, bd=0, takefocus=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self._name_label = tk.Label(
            self, text=name, bg=T.SURFACE, fg=T.TEXT, font=T.TYPE_HEADING, anchor="w",
        )
        self._count_label = tk.Label(
            self, text=count_text, bg=T.SURFACE, fg=T.TEXT_SECONDARY,
            font=T.TYPE_CAPTION, anchor="w",
        )
        self._name_label.pack(anchor="w", padx=T.px(T.SPACE_4), pady=(T.px(T.SPACE_4), 0))
        self._count_label.pack(anchor="w", padx=T.px(T.SPACE_4), pady=(T.px(T.SPACE_1), 0))
        self._init_state(command)
        self.bind("<Configure>", lambda _e: self._draw())
        for widget in (self._name_label, self._count_label):
            widget.bind("<ButtonPress-1>", self._st_press, add="+")
            widget.bind("<ButtonRelease-1>", self._st_release, add="+")
            widget.bind("<Enter>", self._st_enter, add="+")
            widget.bind("<Leave>", self._st_leave, add="+")

    def set_selected(self, selected):
        self._selected = bool(selected)
        self._draw()

    def _face(self):
        if self._disabled:
            return T.DISABLED_FILL, T.DISABLED_FILL
        if self._selected:
            return T.PRIMARY_SOFT, T.PRIMARY
        if self._pressed:
            return T.PRESSED, T.BORDER_LIGHT
        if self._hover:
            return T.HOVER, T.BORDER_CONTROL
        return T.SURFACE, T.BORDER_LIGHT

    def _draw(self):
        if not self.winfo_exists():
            return
        cv = self.canvas
        cv.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 2 or h <= 2:
            return
        g = T.px(T.FOCUS_RING)
        r = T.px(T.RADIUS_CARD)
        self._glow_ring(cv, g, g, w - g, h - g, r)
        fill, edge = self._face()
        round_rect(cv, g, g, w - g, h - g, r, fill=fill)
        round_rect(
            cv, g, g, w - g, h - g, r, outline=edge,
            width=T.px(2) if self._selected else T.px(T.HAIRLINE),
        )
        if self._selected:
            dot = T.px(14)
            cx, cy = w - g - dot - T.px(T.SPACE_3), g + dot + T.px(T.SPACE_2)
            cv.create_oval(cx - dot // 2, cy - dot // 2, cx + dot // 2, cy + dot // 2,
                           fill=T.PRIMARY, outline="")
            cv.create_line(cx - T.px(3), cy, cx - T.px(1), cy + T.px(2),
                           fill=T.ON_PRIMARY, width=T.px(2))
            cv.create_line(cx - T.px(1), cy + T.px(2), cx + T.px(3), cy - T.px(2),
                           fill=T.ON_PRIMARY, width=T.px(2))
        self._name_label.configure(bg=fill, fg=T.PRIMARY if self._selected else T.TEXT)
        self._count_label.configure(bg=fill, fg=T.TEXT_SECONDARY)
        cv.configure(bg=fill)

    def refresh(self):
        self._draw()


def labelled_field(parent, text, control, caption=None):
    """Label -> 8px gap -> control, with an optional caption underneath."""
    box = tk.Frame(parent, bg=T.SURFACE)
    tk.Label(box, text=text, bg=T.SURFACE, fg=T.TEXT, font=T.TYPE_HEADING,
             anchor="w").pack(fill="x")
    control.pack(fill="x", pady=(T.px(T.FIELD_GAP), 0))
    if caption:
        tk.Label(box, text=caption, bg=T.SURFACE, fg=T.TEXT_MUTED,
                 font=T.TYPE_CAPTION, anchor="w", wraplength=T.px(420)).pack(
            fill="x", pady=(T.px(T.SPACE_1), 0),
        )
    return box
