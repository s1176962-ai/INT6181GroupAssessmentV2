"""Optional, interruptible Tk after() motion. Scoring never waits on it."""

import tkinter as tk

from .ui_tokens import BG, ERROR, PRIMARY, SUCCESS_BG, SUCCESS_FG, SURFACE


class Motion:
    def __init__(self, root):
        self.root = root
        self.enabled = True
        self._jobs = []
        self._overlay = None

    def active(self):
        try:
            return bool(self.enabled and self.root.winfo_exists() and self.root.winfo_viewable())
        except tk.TclError:
            return False

    def cancel(self):
        for job in list(self._jobs):
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        self._jobs.clear()
        self._drop_overlay()

    def schedule(self, delay, callback):
        job = {"id": None}

        def run():
            if job["id"] in self._jobs:
                self._jobs.remove(job["id"])
            try:
                if not self.root.winfo_exists():
                    return
            except tk.TclError:
                return
            callback()

        job["id"] = self.root.after(delay, run)
        self._jobs.append(job["id"])
        return job["id"]

    def _drop_overlay(self):
        overlay = self._overlay
        self._overlay = None
        if overlay is not None:
            try:
                overlay.destroy()
            except tk.TclError:
                pass

    def fade_in(self, host, duration=220):
        if not self.active() or not host.winfo_exists():
            return
        self._drop_overlay()
        overlay = tk.Frame(host, bg=BG)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._overlay = overlay
        self.schedule(duration, self._drop_overlay)

    def circle_transition(self, host, callback, x=None, y=None, color=SUCCESS_BG):
        if not self.active() or not host.winfo_exists():
            callback()
            return
        self._drop_overlay()
        host.update_idletasks()
        width = max(host.winfo_width(), 1)
        height = max(host.winfo_height(), 1)
        cx = width // 2 if x is None else x
        cy = height // 2 if y is None else y
        overlay = tk.Canvas(host, bg=BG, highlightthickness=0, bd=0)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._overlay = overlay
        max_radius = int((width**2 + height**2) ** 0.5) + 40

        def expand(radius=0):
            if not overlay.winfo_exists():
                callback()
                return
            overlay.delete("all")
            overlay.create_oval(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                fill=color,
                outline="",
            )
            if radius < max_radius:
                self.schedule(12, lambda: expand(radius + 55))
            else:
                self._drop_overlay()
                callback()

        expand()

    def slide_prepare(self, host, direction="left"):
        """Brief nudge before a page rebuild. Returns False if skipped."""
        if not self.active() or not host.winfo_exists():
            return False
        try:
            host.place_configure(x=-28 if direction == "left" else 28)
        except tk.TclError:
            return False
        return True

    def submit_feedback(self, button, ok, on_done):
        """Text-only stages: clear → mark → restore label. Never blocks scoring."""
        mark = "OK" if ok else "X"
        if not self.active() or not button.winfo_exists():
            on_done()
            return

        def stage(step=0):
            if not button.winfo_exists():
                on_done()
                return
            if step == 0:
                button.configure(text="")
                self.schedule(100, lambda: stage(1))
            elif step == 1:
                button.configure(text=mark)
                self._spark(button, ok)
                self.schedule(180, lambda: stage(2))
            else:
                on_done()

        stage()

    def _spark(self, near, ok):
        if not self.active() or not near.winfo_exists():
            return
        try:
            parent = near.nametowidget(near.winfo_parent())
        except tk.TclError:
            return
        color = SUCCESS_FG if ok else ERROR
        canvas = tk.Canvas(parent, width=120, height=48, bg=BG, highlightthickness=0, bd=0)
        canvas.place(in_=near, relx=0.5, rely=0, anchor="s")
        self._overlay = canvas
        dots = []
        for dx, dy in ((-20, 20), (-6, 8), (8, 6), (22, 18), (0, 28)):
            dots.append(canvas.create_oval(60 + dx, dy, 60 + dx + 6, dy + 6, fill=color, outline=""))

        def tick(n=0):
            if not canvas.winfo_exists():
                return
            for item in dots:
                canvas.move(item, 0, -2 if n < 4 else 1)
            if n < 8:
                self.schedule(28, lambda: tick(n + 1))
            else:
                self._drop_overlay()

        tick()

    def grow_progress(self, bar, target):
        if not bar.winfo_exists():
            return
        if not self.active():
            bar.configure(value=target)
            return
        current = [float(bar.cget("value") or 0)]
        steps = max(int(abs(target - current[0]) * 5), 1)
        delta = (target - current[0]) / steps

        def tick(left=steps):
            if not bar.winfo_exists():
                return
            if left <= 0:
                bar.configure(value=target)
                return
            current[0] += delta
            bar.configure(value=current[0])
            self.schedule(28, lambda: tick(left - 1))

        tick()

    def roll_count(self, label, formatter, start, end):
        if not label.winfo_exists():
            return
        if not self.active() or start == end:
            label.configure(text=formatter(end))
            return
        current = [float(start)]
        steps = min(abs(end - start), 12) or 1
        delta = (end - start) / steps

        def tick(left=steps):
            if not label.winfo_exists():
                return
            if left <= 0:
                label.configure(text=formatter(end))
                return
            current[0] += delta
            label.configure(text=formatter(int(round(current[0]))))
            self.schedule(24, lambda: tick(left - 1))

        tick()

    def paint_path(self, canvas, total, current, done=False):
        if not canvas.winfo_exists():
            return
        canvas.delete("all")
        width = max(canvas.winfo_width(), 1)
        if width < 20:
            canvas.after(16, lambda: self.paint_path(canvas, total, current, done))
            return
        total = max(total, 1)
        pad = 16
        span = max(width - pad * 2, 1)
        y = 14
        for index in range(total):
            x = pad + span * index / max(total - 1, 1)
            filled = index < current or (done and index < total)
            color = PRIMARY if filled else "#D8D2C6"
            if index < total - 1:
                x2 = pad + span * (index + 1) / max(total - 1, 1)
                canvas.create_line(x + 7, y, x2 - 7, y, fill=PRIMARY if index < current - (0 if done else 1) else "#D8D2C6", width=3)
            canvas.create_oval(x - 7, y - 7, x + 7, y + 7, fill=SURFACE if not filled else PRIMARY, outline=color, width=2)
