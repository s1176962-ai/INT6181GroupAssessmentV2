"""One Tkinter interface for setup, quizzes, notebook and learning history."""

import gc
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .auth import AuthService
from .display import DisplaySettings, window_size
from .editor_ui import EditorPage
from .i18n import Translator
from .importing import QuestionImportService
from .motion import Motion
from .models import option_label
from .repositories import (
    LearningPlanRepository,
    PersonalQuestionRepository,
    ProgressRepository,
    QuestionRepository,
)
from .services import QuizEngine, image_path, select_questions, subject_image
from .storage import DataError
from .ui_tokens import (
    BG,
    BORDER,
    CARD_WIDTH,
    CONTENT_MAX,
    PAGE_PAD,
    COLOR_PRIMARY_DARK,
    ERROR,
    ERROR_BG,
    FONT,
    HOVER,
    INFO_BG,
    ROW_H,
    WARNING,
    WARNING_BG,
    MUTED,
    ON_PRIMARY,
    PRIMARY,
    PRIMARY_ACTIVE,
    PRIMARY_DISABLED,
    PRIMARY_HOVER,
    PROGRESS_H,
    SELECTED_BG,
    SHADOW_CARD,
    SKY,
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
    SPACE_6,
    SPLIT_WIDE,
    BUTTON_FILL,
    BUTTON_INK,
    SUCCESS_BG,
    SUCCESS_FG,
    SURFACE,
    TEXT,
    TRACK,
    TYPE_BODY,
    TYPE_BUTTON,
    TYPE_CARD,
    TYPE_FOOT,
    TYPE_HINT,
    TYPE_LABEL,
    TYPE_MARK,
    TYPE_TITLE,
    TYPE_TOOL,
    TYPE_NUM,
    HIT,
)
from .user_ui import UserPage
from .widgets import bind_whole, card_frame, subject_icon

ROOT = Path(__file__).resolve().parent.parent
CARD = SURFACE
RAISED = HOVER
NAVY = TEXT
PRIMARY_DARK = COLOR_PRIMARY_DARK
PRIMARY_INK = ON_PRIMARY
ERROR_FG = ERROR
ACCENT = PRIMARY
SHADOW = SHADOW_CARD
SPACE_XS = SPACE_1
SPACE_SM = SPACE_2
SPACE_MD = SPACE_4
SPACE_LG = SPACE_5
SPACE_XL = SPACE_6


class Application:
    def __init__(self, root, project_root=ROOT, progress_path=None):
        self.root = root
        self.aqua = root.tk.call("tk", "windowingsystem") == "aqua"
        self.project_root = Path(project_root)
        self.bank = QuestionRepository(self.project_root / "data" / "questions")
        self.progress = ProgressRepository(
            progress_path or self.project_root / "data" / "progress.json"
        )
        self.guest_progress_path = self.progress.store.path
        self.personal_bank = PersonalQuestionRepository(
            self.guest_progress_path.parent / "guest_questions.json"
        )
        self.learning_plan = LearningPlanRepository(
            self.guest_progress_path.parent / "learning_plan.json"
        )
        self.auth = AuthService(self.guest_progress_path.parent)
        self.tr = Translator(self.guest_progress_path.parent)
        self.display_store = DisplaySettings(self.guest_progress_path.parent)
        self.display_warning = ""
        try:
            self.display = self.display_store.load()
        except DataError as exc:
            self.display = {"size": "auto", "compact": True}
            self.display_warning = str(exc)
        self.motion = Motion(root)
        self.motion.enabled = self.tr.motion_enabled()
        self.signed_in = False
        self.users_page = None
        self.user = None
        self.editor = None
        self.engine = None
        self.images = []
        self.timer_seconds = tk.StringVar(value="0")
        root.title(self.tr("Quiz App"))
        self.apply_window_size()
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Destroy>", self._on_root_destroy, add="+")
        self._style(root)
        self.chrome = ttk.Frame(root, style="Shell.TFrame", padding=(20, 14))
        self.chrome_title = ttk.Label(
            self.chrome, text=self.tr("首页"), style="Shell.TLabel"
        )
        self.chrome_title.pack(side="left")
        self.timer_label = ttk.Label(self.chrome, text="", style="Shell.TLabel")
        self.timer_label.pack(side="left", padx=12)
        self.chrome_user = ttk.Label(self.chrome, text="", style="Muted.TLabel")
        self.chrome_user.pack(side="right")
        root.bind("<Configure>", self._on_root_resize, add="+")
        self.rule = ttk.Separator(root, orient="horizontal")
        outer = ttk.Frame(root, style="App.TFrame")
        outer.pack(fill="both", expand=True)
        self.outer = outer
        self.login_split = None
        self.login_host = None
        self.login_form = None
        self._login_after = None
        self._login_layout_busy = False
        self.show_password = False
        self._login_busy = False
        self._login_result = None
        self._quiz_keys_bound = False
        self._last_filters = None
        self._last_session = None
        self.canvas = tk.Canvas(outer, highlightthickness=0, bg=BG, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = ttk.Frame(self.canvas, style="App.TFrame", padding=(12, 10) if self.display["compact"] else (24, 20))
        self.window = self.canvas.create_window((0, 0), window=self.body, anchor="n")
        self.body.bind(
            "<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        root.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-int(e.delta / 120), "units"))
        root.bind("<Configure>", lambda e: self._layout_login() if e.widget is root else None, add="+")
        self.load_bank()
        self.login_page()

    def _on_root_destroy(self, event):
        if event.widget is not self.root:
            return
        if self._login_after:
            try:
                self.root.after_cancel(self._login_after)
            except tk.TclError:
                pass
            self._login_after = None
        self.motion.cancel()

    def _style(self, root):
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", font=(FONT, 11), background=BG, foreground=TEXT)
        style.configure("App.TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("Shell.TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=(FONT, 11))
        style.configure("Card.TLabel", background=CARD, foreground=TEXT, font=(FONT, 11))
        style.configure("Shell.TLabel", background=BG, foreground=TEXT, font=(FONT, 11, "bold"))
        style.configure("Mark.TLabel", background=BG, foreground=ACCENT, font=(FONT, 18, "bold"))
        style.configure("Brand.TFrame", background=SKY)
        style.configure("Brand.TLabel", background=SKY, foreground=MUTED, font=TYPE_HINT)
        style.configure("BrandTitle.TLabel", background=SKY, foreground=TEXT, font=TYPE_TITLE)
        style.configure("BrandMark.TLabel", background=SKY, foreground=MUTED, font=TYPE_MARK)
        style.configure("Chip.TLabel", background=HOVER, foreground=TEXT, font=TYPE_HINT)
        style.configure("Demo.TLabel", background=SURFACE, foreground=MUTED, font=TYPE_HINT)
        style.configure("Stat.TLabel", background=SURFACE, foreground=TEXT, font=(FONT, 16, "bold"))
        style.configure("StatHint.TLabel", background=SURFACE, foreground=MUTED, font=(FONT, 8))
        style.configure("Foot.TLabel", background=BG, foreground=MUTED, font=(FONT, 8))
        style.configure(
            "Tool.TButton",
            padding=(12, 7),
            font=(FONT, 10),
            background=CARD,
            foreground=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            relief="flat",
        )
        style.map("Tool.TButton", background=[("active", HOVER), ("pressed", RAISED)])
        style.configure(
            "Tool.TMenubutton",
            padding=(12, 7),
            font=(FONT, 10),
            background=CARD,
            foreground=TEXT,
            bordercolor=BORDER,
            relief="flat",
            arrowcolor=TEXT,
        )
        style.map("Tool.TMenubutton", background=[("active", HOVER)])
        style.configure("Hint.TLabel", background=CARD, foreground=MUTED, font=(FONT, 10))
        style.configure("Title.TLabel", font=(FONT, 18), background=BG, foreground=TEXT)
        style.configure("Kpi.TLabel", font=(FONT, 28), background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=(FONT, 10))
        style.configure("Question.TLabel", background=BG, foreground=TEXT, font=(FONT, 14))
        style.configure(
            "Warning.TLabel",
            background=WARNING_BG,
            foreground=WARNING,
            font=(FONT, 10),
            padding=8,
        )
        style.configure(
            "Info.TLabel",
            background=INFO_BG,
            foreground=TEXT,
            font=(FONT, 10),
            padding=8,
        )
        style.configure(
            "Success.TLabel",
            background=SUCCESS_BG,
            foreground=SUCCESS_FG,
            font=(FONT, 11),
            padding=8,
        )
        style.configure(
            "Error.TLabel",
            background=ERROR_BG,
            foreground=ERROR_FG,
            font=(FONT, 11),
            padding=8,
        )
        style.configure(
            "TButton",
            padding=(12, 10),
            font=(FONT, 11),
            background=CARD,
            foreground=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            relief="flat",
        )
        style.map("TButton", background=[("active", HOVER), ("pressed", RAISED), ("disabled", BG)])
        style.configure("Nav.TFrame", background=BG)
        style.configure("Nav.TLabel", background=BG, foreground=MUTED, font=(FONT, 10))
        style.configure(
            "Accent.TButton",
            padding=(12, 12),
            font=(FONT, 12, "bold"),
            background=BUTTON_FILL,
            foreground=BUTTON_INK,
            bordercolor=BUTTON_FILL,
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#1A8CD8"), ("pressed", "#1878B8"), ("disabled", "#2F3336")],
            foreground=[("disabled", MUTED), ("!disabled", "#FFFFFF")],
        )
        style.configure(
            "Link.TButton",
            padding=(0, 2),
            font=(FONT, 10),
            background=CARD,
            foreground=ACCENT,
            bordercolor=CARD,
            relief="flat",
        )
        style.map("Link.TButton", foreground=[("active", PRIMARY_DARK)], background=[("active", CARD)])
        style.configure(
            "Ghost.TButton",
            padding=(8, 4),
            font=(FONT, 10),
            background=BG,
            foreground=MUTED,
            bordercolor=BG,
            relief="flat",
        )
        style.map("Ghost.TButton", foreground=[("active", TEXT)], background=[("active", BG)])
        style.configure(
            "Icon.TButton",
            padding=(2, 2),
            font=(FONT, 9),
            background=HOVER,
            foreground=MUTED,
            bordercolor=HOVER,
            relief="flat",
        )
        style.map("Icon.TButton", background=[("active", SKY)], foreground=[("active", TEXT)])
        style.configure(
            "TEntry",
            padding=8,
            fieldbackground=CARD,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
        )
        style.map(
            "TEntry",
            bordercolor=[("focus", ACCENT)],
            lightcolor=[("focus", ACCENT)],
            darkcolor=[("focus", ACCENT)],
        )
        style.configure(
            "Error.TEntry",
            padding=8,
            fieldbackground=ERROR_BG,
            bordercolor=ERROR_FG,
            lightcolor=ERROR_FG,
            darkcolor=ERROR_FG,
        )
        style.configure("TRadiobutton", background=CARD, foreground=TEXT, font=(FONT, 11), padding=6)
        style.map("TRadiobutton", background=[("active", RAISED)])
        style.configure("TLabelframe", background=CARD, bordercolor=BORDER, relief="solid")
        style.configure(
            "TLabelframe.Label",
            background=CARD,
            foreground=TEXT,
            font=(FONT, 11),
        )
        style.configure("TCombobox", padding=6, fieldbackground=CARD, background=CARD)
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", CARD)],
            selectbackground=[("focus", SELECTED_BG)],
            selectforeground=[("focus", TEXT)],
        )
        style.configure(
            "TCheckbutton",
            background=BG,
            foreground=TEXT,
            font=(FONT, 11),
            padding=4,
        )
        style.map("TCheckbutton", background=[("active", HOVER)])
        style.configure("TSpinbox", foreground="#111111", fieldbackground="#FFFFFF", insertcolor="#111111")
        style.map("TSpinbox", foreground=[("!disabled", "#111111")], fieldbackground=[("!disabled", "#FFFFFF")])
        self.check_images = []
        for selected in (False, True):
            icon = tk.PhotoImage(master=root, width=18, height=18)
            icon.put("#FFFFFF", to=(0, 0, 18, 18))
            icon.put("#526675", to=(0, 0, 18, 2))
            icon.put("#526675", to=(0, 16, 18, 18))
            icon.put("#526675", to=(0, 0, 2, 18))
            icon.put("#526675", to=(16, 0, 18, 18))
            if selected:
                for x, y in [(4, 8), (5, 9), (6, 10), (7, 11), (8, 10), (9, 9), (10, 8), (11, 7), (12, 6), (13, 5)]:
                    icon.put("#137C72", to=(x, y, x + 2, y + 2))
            self.check_images.append(icon)
        if "Checkmark.indicator" not in style.element_names():
            style.element_create("Checkmark.indicator", "image", self.check_images[0], ("selected", self.check_images[1]))
        style.layout("TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
            ("Checkmark.indicator", {"side": "left", "sticky": ""}),
            ("Checkbutton.label", {"side": "left", "sticky": "nswe"})]})])

        style.configure(
            "Treeview",
            background=SURFACE,
            fieldbackground=SURFACE,
            foreground=TEXT,
            rowheight=ROW_H,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            font=(FONT, 10),
        )
        style.configure(
            "Treeview.Heading",
            background=HOVER,
            foreground=TEXT,
            font=(FONT, 10, "bold"),
            relief="flat",
        )
        style.map(
            "Treeview",
            background=[("selected", SELECTED_BG)],
            foreground=[("selected", TEXT)],
        )
        style.configure("Vertical.TScrollbar", background=HOVER, troughcolor=TRACK, bordercolor=BORDER)
        style.configure("Horizontal.TScrollbar", background=HOVER, troughcolor=TRACK, bordercolor=BORDER)
        style.configure("TNotebook", background=BG, bordercolor=BORDER)
        style.configure("TNotebook.Tab", background=HOVER, foreground=TEXT, padding=(12, 8))
        style.map("TNotebook.Tab", background=[("selected", SURFACE)])
        style.configure("Horizontal.TProgressbar", troughcolor=TRACK, background=TEXT, thickness=3)
        style.configure("TSeparator", background=BORDER)

    def _ensure_nav(self):
        if getattr(self, "nav", None) and self.nav.winfo_exists():
            self._paint_nav()
            return
        self.nav = tk.Frame(
            self.root,
            bg="#0D1014",
            width=196,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        self.nav.pack_propagate(False)
        tk.Label(
            self.nav,
            text="Quiz App",
            bg="#0D1014",
            fg=TEXT,
            font=(FONT, 15, "bold"),
        ).pack(
            anchor="w", padx=28, pady=(24, 24)
        )
        self._nav_buttons = {}
        items = (
            ("home", "⌂", "首页", self.home),
            ("practice", "▷", "开始练习", self.configure),
            ("personal", "▤", "导入题库", self.personal_bank_page),
            ("notebook", "▣", "错题本与复习", self.notebook),
            ("history", "▥", "学习统计与历史", self.history),
            ("settings", "⚙", "设置 / 语言", self.settings),
        )
        for key, icon, caption, command in items:
            button = tk.Label(
                self.nav,
                text=f"{icon}   {self.tr(caption)}",
                bg="#0D1014",
                fg=TEXT,
                anchor="w",
                padx=14,
                pady=12,
                font=(FONT, 11),
                cursor="hand2",
            )
            button.pack(fill="x", padx=10, pady=3)
            button._nav_key = key
            button._icon = icon
            button._caption = caption
            self._nav_buttons[key] = button
            button.bind(
                "<Button-1>",
                lambda _e, action=command, item=key: self._nav_go(item, action),
            )
            button.bind("<Enter>", lambda _e, w=button: self._nav_hover(w, True))
            button.bind("<Leave>", lambda _e, w=button: self._nav_hover(w, False))
        foot = tk.Frame(self.nav, bg="#0D1014")
        foot.pack(side="bottom", fill="x", padx=10, pady=16)
        self.nav_user = tk.Label(
            foot,
            text="",
            bg="#0D1014",
            fg=TEXT,
            anchor="w",
            padx=10,
            pady=11,
            font=(FONT, 10),
            cursor="hand2",
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        self.nav_user.pack(fill="x")
        self.nav_user.bind("<Button-1>", lambda _e: self._account_menu())
        self.nav_user.bind("<Enter>", lambda _e: self.nav_user.configure(bg=HOVER))
        self.nav_user.bind("<Leave>", lambda _e: self.nav_user.configure(bg="#0D1014"))
        self._account_popup = tk.Menu(self.root, tearoff=0, bg=SURFACE, fg=TEXT, activebackground=HOVER)
        self._paint_nav()

    def _account_menu(self):
        menu = self._account_popup
        menu.delete(0, "end")
        menu.add_command(label=self.tr("重新加载题库"), command=self.home)
        menu.add_command(label=self.tr("退出登录 / 切换账户"), command=self.logout)
        menu.add_command(label=self.tr("退出"), command=self.close)
        menu.tk_popup(self.nav_user.winfo_rootx(), self.nav_user.winfo_rooty() - 90)

    def _nav_go(self, key, command):
        self._nav_key = key
        command()

    def _nav_hover(self, button, entering):
        if getattr(self, "_nav_key", None) == button._nav_key:
            return
        button.configure(bg=HOVER if entering else "#0D1014")

    def _paint_nav(self):
        current = getattr(self, "_nav_key", None)
        for key, button in getattr(self, "_nav_buttons", {}).items():
            if not button.winfo_exists():
                continue
            button.configure(text=f"{button._icon}   {self.tr(button._caption)}")
            selected = key == current
            button.configure(
                bg=PRIMARY if selected else "#0D1014",
                fg="#FFFFFF" if selected else TEXT,
                font=(FONT, 10, "bold") if selected else (FONT, 10),
            )
        label = getattr(self, "nav_user", None)
        if label and label.winfo_exists():
            if self.user:
                label.configure(text=self.user["name"])
            elif self.signed_in:
                label.configure(text=self.tr("访客"))
            else:
                label.configure(text="")

    def _set_chrome(self, visible):
        if visible:
            self._ensure_nav()
            if not self.nav.winfo_ismapped():
                self.nav.pack(side="left", fill="y", before=self.outer)
            if not self.chrome.winfo_ismapped():
                self.chrome.pack(fill="x", before=self.outer)
                self.rule.pack(fill="x", before=self.outer)
        else:
            if getattr(self, "nav", None) and self.nav.winfo_ismapped():
                self.nav.pack_forget()
            self.chrome.pack_forget()
            self.rule.pack_forget()

    def _show_scroll_shell(self, show):
        if show:
            if self.login_host and self.login_host.winfo_exists():
                self.login_host.destroy()
            self.login_host = None
            self.login_form = None
            if not self.canvas.winfo_ismapped():
                self.canvas.pack(side="left", fill="both", expand=True)
        else:
            self.scrollbar.pack_forget()
            self.canvas.pack_forget()

    def _on_login_host(self, event=None):
        """Relayout login without embedding the form in a Canvas (avoids IME lag)."""
        if self._login_layout_busy:
            return
        if not getattr(self, "login_split", None) or not self.login_split.winfo_exists():
            return
        self._login_layout_busy = True
        try:
            self._layout_login()
        finally:
            self._login_layout_busy = False

    def _on_canvas_configure(self, event):
        width = max(event.width, 1)
        content_w = min(CONTENT_MAX, max(width - PAGE_PAD * 2, 520))
        self.canvas.coords(self.window, width // 2, 0)
        self.canvas.itemconfigure(self.window, width=content_w)
        self._sync_scroll()

    def _sync_scroll(self):
        if self.login_split and self.login_split.winfo_exists():
            return
        if not self.canvas.winfo_ismapped():
            return
        self.root.update_idletasks()
        needed = self.body.winfo_reqheight() > self.canvas.winfo_height() + 4
        mapped = self.scrollbar.winfo_ismapped()
        if needed and not mapped:
            self.scrollbar.pack(side="right", fill="y")
        elif not needed and mapped:
            self.scrollbar.pack_forget()
            self.canvas.yview_moveto(0)

    def _layout_login(self, event=None):
        if not self.login_split or not self.login_split.winfo_exists():
            return
        wide = self.root.winfo_width() >= SPLIT_WIDE
        self.login_split.columnconfigure(0, weight=1, minsize=0)
        self.login_split.columnconfigure(1, weight=1 if wide else 0, minsize=0)
        if wide:
            self.login_split.rowconfigure(0, weight=1)
            self.login_split.rowconfigure(1, weight=0)
            self.brand.grid_configure(row=0, column=0, rowspan=2, columnspan=1, sticky="nsew")
            self.login_pane.grid_configure(row=0, column=1, rowspan=2, columnspan=1, sticky="nsew")
        else:
            self.login_split.rowconfigure(0, weight=0)
            self.login_split.rowconfigure(1, weight=1)
            self.login_pane.grid_configure(row=0, column=0, rowspan=1, columnspan=2, sticky="new")
            self.brand.grid_configure(row=1, column=0, rowspan=1, columnspan=2, sticky="nsew")
        pad = SPACE_XL if wide else SPACE_4
        if self.brand.winfo_exists():
            self.brand.configure(padx=pad, pady=pad)
        self._center_login_form()

    def _center_login_form(self):
        form = getattr(self, "login_form", None)
        pane = getattr(self, "login_pane", None)
        if not form or not pane or not form.winfo_exists() or not pane.winfo_exists():
            return
        pane.update_idletasks()
        form_w = min(CARD_WIDTH, max(pane.winfo_width() - SPACE_4, 280))
        wide = self.root.winfo_width() >= SPLIT_WIDE
        if not wide:
            if form.winfo_manager() == "place":
                form.place_forget()
            form.pack_propagate(True)
            if form.winfo_manager() != "pack":
                form.pack(fill="x", padx=SPACE_4, pady=SPACE_4)
            return
        if form.winfo_manager() == "pack":
            form.pack_forget()
        form.pack_propagate(True)
        self.root.update_idletasks()
        height = form.winfo_reqheight()
        form.pack_propagate(False)
        form.configure(width=form_w, height=height)
        view = pane.winfo_height()
        y = max((view - height) // 2, SPACE_4) if view > height else SPACE_4
        form.place(relx=0.5, y=y, anchor="n", width=form_w, height=height)

    def _draw_login_art(self, canvas):
        if not canvas.winfo_exists():
            return
        canvas.delete("all")
        width = max(canvas.winfo_width(), 200)
        height = max(canvas.winfo_height(), 80)
        canvas.create_oval(width * 0.12, 18, width * 0.34, height - 10, outline=PRIMARY, width=2)
        canvas.create_rectangle(
            width * 0.40, 28, width * 0.62, height - 14, outline=PRIMARY, width=2
        )
        canvas.create_line(
            width * 0.70, height - 18, width * 0.82, 24, width * 0.90, height - 18, fill=PRIMARY, width=2
        )
        canvas.create_text(width * 0.23, height / 2, text="Aa", fill=PRIMARY, font=(FONT, 12, "bold"))
        canvas.create_text(width * 0.51, height / 2, text="123", fill=PRIMARY, font=(FONT, 11, "bold"))
        canvas.create_text(width * 0.81, height / 2 + 4, text="Sci", fill=PRIMARY, font=(FONT, 10, "bold"))

    def _apply_login_language(self, language):
        try:
            self.tr.set_language(language)
        except ValueError as exc:
            messagebox.showerror(self.tr("保存失败"), self.tr(str(exc)), parent=self.root)
            return
        self.root.title(self.tr("Quiz App"))
        self.login_page(getattr(self, "_login_registering", False))

    def _toggle_password(self):
        self.show_password = not self.show_password
        show = "" if self.show_password else "•"
        for entry in self.password_entries:
            entry.configure(show=show)
        self.password_toggle.configure(text=self.tr("隐藏") if self.show_password else self.tr("显示"))

    def _field_border(self, widget, color, fill=None):
        shell = getattr(widget, "_shell", widget)
        shell.configure(bg=color)
        if fill is not None and widget.winfo_exists():
            widget.configure(bg=fill)

    def _focus_field(self, entry, focused):
        if entry in getattr(self, "_login_error_fields", ()):
            return
        self._field_border(entry, PRIMARY if focused else BORDER, SURFACE)

    def _wire_field(self, entry):
        entry.bind("<FocusIn>", lambda _e, field=entry: self._focus_field(field, True), add="+")
        entry.bind("<FocusOut>", lambda _e, field=entry: self._focus_field(field, False), add="+")

    def _mark_login_error(self, message, fields=None):
        self.login_error.configure(text=message)
        if not self.login_error.winfo_ismapped():
            self.login_error.pack(anchor="w", fill="x", before=self.login_button._shell, pady=(0, SPACE_SM))
        targets = fields or list(getattr(self, "login_fields", []))
        self._login_error_fields = set(targets)
        for entry in getattr(self, "login_fields", []):
            if entry in targets:
                self._field_border(entry, ERROR, ERROR_BG)
            else:
                self._field_border(entry, BORDER, SURFACE)
        self._center_login_form()

    def _clear_login_error(self, event=None):
        self._login_error_fields = set()
        had_error = False
        if getattr(self, "login_error", None) and self.login_error.winfo_exists():
            had_error = bool(self.login_error.winfo_ismapped())
            self.login_error.configure(text="")
            self.login_error.pack_forget()
        for entry in getattr(self, "login_fields", []):
            if entry.winfo_exists():
                color = PRIMARY if entry == self.root.focus_get() else BORDER
                self._field_border(entry, color, SURFACE)
        if had_error:
            self._center_login_form()

    def _draw_progress(self, canvas, percent):
        canvas.delete("all")
        width = max(canvas.winfo_width(), 40)
        height = PROGRESS_H
        canvas.create_rectangle(0, 0, width, height, fill=TRACK, outline="")
        fill_to = max(2, int(width * percent / 100))
        canvas.create_rectangle(0, 0, fill_to, height, fill=PRIMARY, outline="")

    def _bind_chrome(self, button, idle, hover, active, idle_fg, hover_fg=None):
        idle_fg = self._native_button_ink(idle_fg)
        hover_fg = self._native_button_ink(hover_fg or idle_fg)

        def enter(_e):
            if str(button["state"]) == "normal":
                button.configure(bg=hover, fg=hover_fg, activebackground=hover, activeforeground=hover_fg)

        def leave(_e):
            if str(button["state"]) == "normal":
                button.configure(bg=idle, fg=idle_fg, activebackground=active, activeforeground=hover_fg)

        def press(_e):
            if str(button["state"]) == "normal":
                button.configure(bg=active)

        button.bind("<Enter>", enter)
        button.bind("<Leave>", leave)
        button.bind("<ButtonPress-1>", press)
        button.bind("<ButtonRelease-1>", enter)

    def _flat_button(self, parent, text, command, font, bg, fg, padx, pady):
        fg = self._native_button_ink(fg)
        button = tk.Button(
            parent,
            text=text,
            command=command,
            font=font,
            bg=bg,
            fg=fg,
            activebackground=bg,
            activeforeground=fg,
            bd=0,
            borderwidth=0,
            relief="flat",
            overrelief="flat",
            highlightthickness=0,
            padx=padx,
            pady=pady,
            cursor="hand2",
        )
        return button

    def _native_button_ink(self, color):
        """Keep text readable when macOS renders classic Tk buttons with a white face."""
        if self.aqua and color in {TEXT, BUTTON_INK}:
            return "#111111"
        return color

    def _tool_button(self, parent, text, command):
        button = self._flat_button(parent, text, command, TYPE_TOOL, BG, TEXT, SPACE_3, max(8, (HIT - 18) // 2))
        self._bind_chrome(button, BG, HOVER, TRACK, TEXT)
        button._button = button
        return button

    def _text_button(self, parent, text, command, bg=SURFACE):
        button = self._flat_button(parent, text, command, TYPE_HINT, bg, PRIMARY, 0, 2)

        def enter(_e):
            if str(button["state"]) == "normal":
                button.configure(fg=PRIMARY_HOVER, font=(FONT, 10, "underline"))

        def leave(_e):
            if str(button["state"]) == "normal":
                button.configure(fg=PRIMARY, font=TYPE_HINT)

        button.bind("<Enter>", enter)
        button.bind("<Leave>", leave)
        return button

    def _primary_button(self, parent, text, command):
        shell = tk.Frame(parent, bg=BUTTON_FILL, highlightthickness=0, bd=0)
        button = self._flat_button(shell, text, command, TYPE_BUTTON, BUTTON_FILL, BUTTON_INK, 16, 12)
        button.configure(anchor="center", justify="center")
        shell.configure(height=48)
        shell.pack_propagate(False)
        button.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._bind_chrome(button, BUTTON_FILL, "#1A8CD8", "#1878B8", BUTTON_INK, BUTTON_INK)
        button._shell = shell
        return button

    def _text_entry(self, parent, variable, show=None):
        shell = tk.Frame(parent, bg=BORDER, highlightthickness=0, bd=0)
        entry = tk.Entry(
            shell,
            textvariable=variable,
            font=TYPE_BODY,
            bg=SURFACE,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            borderwidth=0,
            highlightthickness=0,
            show=show or "",
        )
        entry.pack(fill="x", ipady=12, padx=1, pady=1)
        entry._shell = shell
        return entry

    def _set_login_button(self, text, disabled):
        color = "#2F3336" if disabled else BUTTON_FILL
        if self.aqua:
            ink = "#666666" if disabled else "#111111"
        else:
            ink = MUTED if disabled else "#FFFFFF"
        self.login_button.configure(
            text=text,
            state="disabled" if disabled else "normal",
            bg=color,
            fg=ink,
            cursor="arrow" if disabled else "hand2",
        )
        if getattr(self.login_button, "_shell", None):
            self.login_button._shell.configure(bg=color)
        for entry in getattr(self, "login_fields", []):
            entry.configure(state="disabled" if disabled else "normal")
        toggle = getattr(self, "password_toggle", None)
        if toggle and toggle.winfo_exists():
            toggle.configure(state="disabled" if disabled else "normal")

    def login_page(self, registering=False):
        """A local account owns progress; guest mode preserves the V1 data file."""
        self.engine = None
        self.editor = None
        self.users_page = None
        self.signed_in = False
        self.show_password = False
        self._login_busy = False
        self._login_registering = registering
        self._set_chrome(False)
        self.body.configure(padding=0)
        self.clear(self.tr("QUIZ STUDIO · 学习空间"), heading=False)
        self._show_scroll_shell(False)
        self.login_host = tk.Frame(self.outer, bg=BG)
        self.login_host.pack(fill="both", expand=True)
        # Pack the split directly: Canvas create_window + Entry causes Windows IME lag.
        self.login_split = tk.Frame(self.login_host, bg=BG)
        self.login_split.pack(fill="both", expand=True)
        self.login_host.bind("<Configure>", self._on_login_host)
        self.login_split.columnconfigure(0, weight=1)
        self.login_split.columnconfigure(1, weight=1)
        self.login_split.rowconfigure(0, weight=1)
        self.login_split.rowconfigure(1, weight=1)
        self.brand = tk.Frame(self.login_split, bg=SKY, padx=SPACE_XL, pady=SPACE_XL)
        brand_inner = tk.Frame(self.brand, bg=SKY)
        brand_inner.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.86)
        ttk.Label(brand_inner, text=self.tr("Quiz App"), style="BrandMark.TLabel").pack(anchor="center")
        title = ttk.Label(
            brand_inner,
            text=self.tr("每天进步一点点，让学习变得更有趣。"),
            style="BrandTitle.TLabel",
            wraplength=360,
            justify="center",
            anchor="center",
        )
        title.pack(anchor="center", pady=(SPACE_2, SPACE_5))
        brand_inner.bind("<Configure>", lambda e: title.configure(wraplength=max(e.width - SPACE_MD, 200)))
        art = tk.Canvas(brand_inner, height=96, bg=SKY, highlightthickness=0, bd=0)
        art.pack(fill="x", pady=(0, SPACE_4))
        self._draw_login_art(art)
        art.bind("<Configure>", lambda e, canvas=art: self._draw_login_art(canvas))
        progress_card = tk.Frame(
            brand_inner,
            bg=SURFACE,
            padx=SPACE_MD,
            pady=SPACE_MD,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        progress_card.pack(fill="x")
        tk.Label(
            progress_card,
            text=self.tr("题库题目数量（登录后可查看个人错题和成绩）"),
            bg=SURFACE,
            fg=TEXT,
            font=TYPE_LABEL,
            wraplength=360,
            justify="center",
            anchor="center",
        ).pack(anchor="center")
        counts = {}
        for question in self.questions:
            counts[question.subject] = counts.get(question.subject, 0) + 1
        total_bank = sum(counts.values()) or 1
        for subject, count in sorted(counts.items()):
            row = tk.Frame(progress_card, bg=SURFACE)
            row.pack(fill="x", pady=(SPACE_SM, 0))
            meta = tk.Frame(row, bg=SURFACE)
            meta.pack(fill="x")
            subject_icon(meta, subject, size=28, bg=SURFACE).pack(side="left", padx=(0, SPACE_2))
            tk.Label(meta, text=subject, bg=SURFACE, fg=MUTED, font=TYPE_FOOT).pack(side="left")
            tk.Label(
                meta,
                text=self.tr("{0} 道题", count),
                bg=SURFACE,
                fg=TEXT,
                font=TYPE_NUM,
            ).pack(side="right")
            bar = tk.Canvas(row, height=PROGRESS_H, bg=SURFACE, highlightthickness=0, bd=0, takefocus=0)
            bar.pack(fill="x", pady=(SPACE_1, 0))
            percent = round(count / total_bank * 100)
            bar.bind(
                "<Configure>",
                lambda e, canvas=bar, value=percent: self._draw_progress(canvas, value),
            )
        tk.Label(
            brand_inner,
            text=self.tr("登录后继续个人错题本和学习历史，题库学科为 English、Mathematics、Science。"),
            bg=SKY,
            fg=MUTED,
            font=TYPE_FOOT,
            wraplength=360,
            justify="center",
            anchor="center",
        ).pack(anchor="center", pady=(SPACE_SM, 0))
        self.login_pane = tk.Frame(self.login_split, bg=BG)
        self.login_form = tk.Frame(self.login_pane, bg=BG, width=CARD_WIDTH)
        self.login_tools = tk.Frame(self.login_form, bg=BG)
        self.login_tools.pack(fill="x", pady=(0, SPACE_MD))
        self._tool_button(self.login_tools, self.tr("退出"), self.close).pack(side="right")
        lang_menu = tk.Menu(self.root, tearoff=0, bg=SURFACE, fg=TEXT, activebackground=HOVER, bd=0)
        lang_menu.add_command(label=self.tr("简体中文"), command=lambda: self._apply_login_language("zh"))
        lang_menu.add_command(label="English", command=lambda: self._apply_login_language("en"))
        lang = self._tool_button(
            self.login_tools, "中文 ▾" if self.tr.language == "zh" else "EN ▾", lambda: None
        )
        lang._button.configure(
            command=lambda: lang_menu.tk_popup(lang.winfo_rootx(), lang.winfo_rooty() + lang.winfo_height())
        )
        lang.pack(side="right", padx=(0, SPACE_2))
        self._tool_button(self.login_tools, self.tr("设置"), self.settings).pack(side="right", padx=(0, SPACE_2))
        card = tk.Frame(
            self.login_form,
            bg=SURFACE,
            padx=SPACE_6,
            pady=SPACE_6,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        card.pack(fill="x")
        tk.Label(
            card,
            text=self.tr("创建本地账户") if registering else self.tr("欢迎回来"),
            font=TYPE_CARD,
            bg=SURFACE,
            fg=TEXT,
        ).pack(anchor="w")
        tk.Label(
            card,
            text=self.tr("用户名 3–32 位；密码 6–16 位。")
            if registering
            else self.tr("继续你的学习旅程"),
            font=TYPE_HINT,
            bg=SURFACE,
            fg=MUTED,
        ).pack(anchor="w", pady=(SPACE_XS, SPACE_MD))
        self.login_name = tk.StringVar()
        self.login_password = tk.StringVar()
        self.login_confirm = tk.StringVar()
        self.password_entries = []
        tk.Label(card, text=self.tr("用户名"), font=TYPE_LABEL, bg=SURFACE, fg=TEXT).pack(anchor="w")
        name_entry = self._text_entry(card, self.login_name)
        name_entry._shell.pack(anchor="w", fill="x", pady=(SPACE_XS, SPACE_MD))
        tk.Label(card, text=self.tr("密码"), font=TYPE_LABEL, bg=SURFACE, fg=TEXT).pack(anchor="w")
        password_box = tk.Frame(card, bg=BORDER, highlightthickness=0, bd=0)
        password_box.pack(anchor="w", fill="x", pady=(SPACE_XS, SPACE_MD))
        password_inner = tk.Frame(password_box, bg=SURFACE)
        password_inner.pack(fill="x", padx=1, pady=1)
        password_entry = tk.Entry(
            password_inner,
            textvariable=self.login_password,
            font=TYPE_BODY,
            bg=SURFACE,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            borderwidth=0,
            highlightthickness=0,
            show="•",
        )
        password_entry._shell = password_box
        password_entry.pack(side="left", fill="x", expand=True, ipady=12, padx=SPACE_SM)
        self.password_entries.append(password_entry)
        self.password_toggle = self._text_button(password_inner, self.tr("显示"), self._toggle_password)
        self.password_toggle.configure(padx=SPACE_3, pady=11)
        self.password_toggle.pack(side="right", padx=SPACE_SM)
        if registering:
            tk.Label(card, text=self.tr("确认密码"), font=TYPE_LABEL, bg=SURFACE, fg=TEXT).pack(anchor="w")
            confirm = self._text_entry(card, self.login_confirm, show="•")
            confirm._shell.pack(anchor="w", fill="x", pady=(SPACE_XS, SPACE_MD))
            self.password_entries.append(confirm)
        self.login_fields = [name_entry, *self.password_entries]
        self._login_error_fields = set()
        self.login_error = tk.Label(
            card,
            text="",
            font=TYPE_HINT,
            bg=SURFACE,
            fg=ERROR,
            wraplength=CARD_WIDTH - 48,
            justify="left",
            anchor="w",
        )
        self.login_button = self._primary_button(
            card,
            self.tr("注册并进入") if registering else self.tr("登录"),
            lambda: self.authenticate(registering),
        )
        self.login_button._shell.pack(anchor="w", fill="x", pady=(0, SPACE_MD))
        account_row = tk.Frame(card, bg=SURFACE)
        account_row.pack(anchor="w")
        if registering:
            self._text_button(account_row, self.tr("已有账户，去登录"), lambda: self.login_page(False)).pack(side="left")
        else:
            tk.Label(account_row, text=self.tr("还没有账户？"), font=TYPE_HINT, bg=SURFACE, fg=MUTED).pack(side="left")
            self._text_button(account_row, self.tr("创建账户"), lambda: self.login_page(True)).pack(side="left", padx=(SPACE_XS, 0))
        guest = tk.Frame(self.login_form, bg=BG)
        guest.pack(fill="x", pady=(SPACE_MD, 0))
        guest_btn = self._text_button(guest, self.tr("以访客身份继续"), self.enter_guest, bg=BG)
        guest_btn.configure(padx=SPACE_3, pady=11, anchor="center")
        guest_btn.pack()
        tk.Label(
            guest,
            text=self.tr("练习记录将保存在当前设备"),
            font=TYPE_FOOT,
            bg=BG,
            fg=MUTED,
            anchor="center",
        ).pack(fill="x", pady=(SPACE_SM, 0))
        if self.tr.warning:
            tk.Label(guest, text=self.tr.warning, font=TYPE_HINT, bg=BG, fg=MUTED, wraplength=CARD_WIDTH).pack(pady=SPACE_SM)
        for widget in self.login_fields:
            widget.bind("<Return>", lambda e, mode=registering: self.authenticate(mode))
            widget.bind("<Key>", self._clear_login_error)
            self._wire_field(widget)
        self._layout_login()
        if self._login_after:
            self.root.after_cancel(self._login_after)

        def _safe_layout():
            try:
                if self.root.winfo_exists():
                    self._layout_login()
            except tk.TclError:
                return

        self._login_after = self.root.after(1, _safe_layout)

    def authenticate(self, registering=False):
        if self._login_busy or not getattr(self, "login_button", None):
            return
        action = self.tr("注册并进入") if registering else self.tr("登录")
        if not self.login_name.get().strip():
            self._mark_login_error(self.tr("请输入用户名"), [self.login_fields[0]])
            return
        if not self.login_password.get():
            self._mark_login_error(self.tr("请输入密码"), [self.login_fields[1]])
            return
        # Capture values on the UI thread; PBKDF2 runs in a worker so the UI stays responsive.
        # Worker only writes _login_result; Tk callbacks stay on the main thread via after-poll.
        name = self.login_name.get()
        password = self.login_password.get()
        confirmation = self.login_confirm.get()
        self._login_busy = True
        self._login_result = None
        self._set_login_button(self.tr("登录中…"), True)
        self.root.update_idletasks()

        def work():
            try:
                if registering:
                    user = self.auth.register(name, password, confirmation)
                else:
                    user = self.auth.login(name, password)
                self._login_result = ("ok", user)
            except ValueError as exc:
                self._login_result = ("err", exc)

        # Finalize detached Tk widgets on the UI thread before starting a worker.
        gc.collect()
        threading.Thread(target=work, daemon=True).start()
        self._poll_login(registering, action)

    def _poll_login(self, registering, action):
        if not self.root.winfo_exists():
            return
        result = self._login_result
        if result is None:
            self.root.after(20, lambda: self._poll_login(registering, action))
            return
        self._login_result = None
        kind, payload = result
        if kind == "err":
            self._mark_login_error(self.tr(str(payload)), list(self.login_fields))
            self._set_login_button(action, False)
            self._login_busy = False
            return
        self.login_password.set("")
        self.login_confirm.set("")
        self._login_busy = False
        self.user = payload
        self.progress = ProgressRepository(self.auth.progress_path(payload))
        self.personal_bank = PersonalQuestionRepository(
            self.auth.personal_questions_path(payload)
        )
        self.learning_plan = LearningPlanRepository(self.auth.learning_plan_path(payload))
        self.home()

    def wait_login(self, timeout=8.0):
        """Process UI events until authenticate() finishes (tests / automation)."""
        deadline = time.monotonic() + timeout
        while self._login_busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.02)
        if self._login_busy:
            self.root.update()
        return not self._login_busy

    def enter_guest(self):
        self.user = None
        self.progress = ProgressRepository(self.guest_progress_path)
        self.personal_bank = PersonalQuestionRepository(
            self.guest_progress_path.parent / "guest_questions.json"
        )
        self.learning_plan = LearningPlanRepository(
            self.guest_progress_path.parent / "learning_plan.json"
        )
        self.home()

    def logout(self):
        self.user = None
        self.progress = ProgressRepository(self.guest_progress_path)
        self.personal_bank = PersonalQuestionRepository(
            self.guest_progress_path.parent / "guest_questions.json"
        )
        self.learning_plan = LearningPlanRepository(
            self.guest_progress_path.parent / "learning_plan.json"
        )
        self.login_page()

    def manage_questions(self):
        if not self.check_admin():
            return
        self.editor = EditorPage(self)
        self.editor.show_list()

    def access_error(self, exc):
        messagebox.showinfo(self.tr("权限提示"), self.tr(str(exc)), parent=self.root)
        try:
            self.user = self.auth.require_session(self.user)
        except ValueError:
            self.logout()
        else:
            self.home()

    def check_admin(self):
        try:
            self.user = self.auth.require_admin(self.user)
            return True
        except ValueError as exc:
            self.access_error(exc)
            return False

    def check_session(self):
        if self.user is None:
            return True
        try:
            self.user = self.auth.require_session(self.user)
            return True
        except ValueError as exc:
            self.access_error(exc)
            return False

    def manage_users(self):
        if self.check_admin():
            self.users_page = UserPage(self)
            self.users_page.show_list()

    def settings(self):
        self._nav_key = "settings"
        self.clear(self.tr("设置"))
        card = ttk.LabelFrame(self.body, text=self.tr("界面语言"), padding=16)
        card.pack(fill="x", pady=8)
        self.language = tk.StringVar(value=self.tr.language)
        ttk.Radiobutton(
            card, text=self.tr("简体中文"), variable=self.language, value="zh"
        ).pack(anchor="w")
        ttk.Radiobutton(card, text="English", variable=self.language, value="en").pack(anchor="w")
        ttk.Label(
            card,
            text=self.tr("切换立即生效并记住选择；题库内容保留原文。"),
            style="Card.TLabel",
            wraplength=640,
        ).pack(anchor="w", pady=8)
        motion = ttk.LabelFrame(self.body, text=self.tr("动画效果"), padding=16)
        motion.pack(fill="x", pady=8)
        self.motion_choice = tk.BooleanVar(value=self.motion.enabled)
        ttk.Radiobutton(
            motion, text=self.tr("开启"), variable=self.motion_choice, value=True
        ).pack(anchor="w")
        ttk.Radiobutton(
            motion, text=self.tr("关闭"), variable=self.motion_choice, value=False
        ).pack(anchor="w")
        ttk.Label(
            motion,
            text=self.tr("关闭后页面直接切换，仍保留颜色和文字反馈。"),
            style="Card.TLabel",
            wraplength=640,
        ).pack(anchor="w", pady=(8, 0))
        self.button(self.tr("保存语言设置"), self.save_language, "Accent.TButton")
        self.label(self.tr("窗口与布局"))
        self.window_choices = [self.tr("自动适应屏幕"), "960x640", "1080x720", "1280x800"]
        self.window_choice = tk.StringVar(value=self.window_choices[0] if self.display["size"] == "auto" else self.display["size"])
        ttk.Combobox(self.body, textvariable=self.window_choice, values=self.window_choices, state="readonly").pack(anchor="w", pady=4)
        self.compact_choice = tk.BooleanVar(value=self.display["compact"])
        ttk.Checkbutton(self.body, text=self.tr("紧凑页边距"), variable=self.compact_choice).pack(anchor="w", pady=4)
        self.label(self.tr("调整程序窗口大小，不改变电脑分辨率。"))
        self.button(self.tr("应用窗口与布局"), self.save_display, "Accent.TButton")
        if self.display_warning:
            self.label(self.display_warning)
        self.button(self.tr("返回"), self.home if self.signed_in else self.login_page)

    def apply_window_size(self):
        width, height = window_size(self.display["size"], self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        self.root.minsize(min(720, width), min(480, height))
        self.root.geometry(f"{width}x{height}")

    def save_display(self):
        size = "auto" if self.window_choice.get() == self.window_choices[0] else self.window_choice.get()
        try:
            self.display_store.save(size, self.compact_choice.get())
        except (ValueError, DataError) as exc:
            messagebox.showerror(self.tr("保存失败"), str(exc), parent=self.root)
            return
        self.display = self.display_store.load()
        self.root.state("normal")
        self.apply_window_size()
        self.body.configure(padding=(12, 10) if self.display["compact"] else (24, 20))
        self.settings()

    def save_language(self):
        try:
            self.tr.set_language(self.language.get())
            if getattr(self, "motion_choice", None) is not None:
                self.tr.set_motion(bool(self.motion_choice.get()))
                self.motion.enabled = bool(self.motion_choice.get())
        except (ValueError, DataError) as exc:
            messagebox.showerror(self.tr("保存失败"), self.tr(str(exc)), parent=self.root)
            return
        self.root.title(self.tr("Quiz App"))
        self.settings()

    def clear(self, title, heading=True, show_heading=True):
        if self._login_after:
            self.root.after_cancel(self._login_after)
            self._login_after = None
        self.motion.cancel()
        self._unbind_quiz_keys()
        self._show_scroll_shell(True)
        for widget in self.body.winfo_children():
            widget.destroy()
        self.images = []
        self.login_split = None
        self.home_rail = None
        self.canvas.yview_moveto(0)
        if heading:
            self._set_chrome(True)
            self.body.configure(padding=(24, 20))
        self.chrome_title.configure(text=title)
        if self.user:
            self.chrome_user.configure(text=self.user["name"])
        elif self.signed_in:
            self.chrome_user.configure(text=self.tr("访客"))
        else:
            self.chrome_user.configure(text="")
        if heading:
            if show_heading:
                ttk.Label(
                    self.body,
                    text=title,
                    style="Title.TLabel",
                    anchor="w",
                    justify="left",
                ).pack(fill="x", pady=(0, 8))
            self._paint_nav()
            self.motion.fade_in(self.outer)

    def _on_root_resize(self, event):
        if event.widget is not self.root:
            return
        rail = getattr(self, "home_rail", None)
        if not rail or not rail.winfo_exists():
            return
        if event.width < 1020:
            if rail.winfo_ismapped():
                rail.pack_forget()
        elif not rail.winfo_ismapped():
            rail.pack(side="right", fill="y")

    def _relative_time(self, value):
        try:
            stamp = datetime.fromisoformat(value)
            if stamp.tzinfo is not None:
                stamp = stamp.astimezone().replace(tzinfo=None)
            now = datetime.now()
            delta = now - stamp
            minutes = int(delta.total_seconds() // 60)
            if minutes < 1:
                return self.tr("刚刚")
            if minutes < 60:
                return self.tr("{0} 分钟前", minutes)
            if stamp.date() == now.date():
                return self.tr("今天 {0}", stamp.strftime("%H:%M"))
            if (now.date() - stamp.date()).days == 1:
                return self.tr("昨天 {0}", stamp.strftime("%H:%M"))
            return stamp.strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            return str(value)

    def label(self, text, style="TLabel"):
        widget = ttk.Label(
            self.body,
            text=text,
            wraplength=CONTENT_MAX - 48,
            justify="left",
            anchor="w",
            style=style,
        )
        widget.pack(fill="x", pady=4)
        return widget

    def button(self, text, command, style="TButton"):
        widget = ttk.Button(self.body, text=text, command=command, style=style)
        widget.pack(anchor="w", pady=4)
        return widget

    def _mock_action(self, parent, text, command, primary=True, padx=18, pady=11):
        """Canvas-friendly action used by the approved dark mock-up."""
        idle = PRIMARY if primary else HOVER
        hover = "#168BDD" if primary else "#272A30"
        label = tk.Label(
            parent,
            text=text,
            bg=idle,
            fg="#FFFFFF" if primary else TEXT,
            font=(FONT, 11, "bold"),
            padx=padx,
            pady=pady,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground=PRIMARY if primary else BORDER,
        )
        label.bind("<Button-1>", lambda _e: command())
        label.bind("<Enter>", lambda _e: label.configure(bg=hover))
        label.bind("<Leave>", lambda _e: label.configure(bg=idle))
        return label

    def load_bank(self):
        self.public_questions = self.bank.all()
        self.personal_bank_error = ""
        if self.user:
            try:
                self.personal_questions = self.personal_bank.all()
            except DataError as exc:
                self.personal_questions = []
                self.personal_bank_error = str(exc)
        else:
            self.personal_questions = []
        self.questions = self.public_questions
        self.by_id = {
            question.id: question
            for question in [*self.public_questions, *self.personal_questions]
        }

    def _plan_ring(self, parent, plan):
        """Render the concept mock-up's circular daily-goal indicator."""
        size = 152
        canvas = tk.Canvas(
            parent, width=size, height=size, bg=SURFACE, highlightthickness=0, bd=0
        )
        canvas.create_oval(15, 15, size - 15, size - 15, outline=TRACK, width=12)
        if plan["percent"]:
            canvas.create_arc(
                15,
                15,
                size - 15,
                size - 15,
                start=90,
                extent=-min(100, plan["percent"]) * 3.6,
                style="arc",
                outline=PRIMARY,
                width=12,
            )
        canvas.create_text(
            size / 2,
            62,
            text=f"{plan['today']} / {plan['daily_goal']}",
            fill=TEXT,
            font=(FONT, 18, "bold"),
        )
        canvas.create_text(
            size / 2, 91, text=self.tr("今日进度"), fill=MUTED, font=TYPE_HINT
        )
        canvas.create_text(
            size / 2,
            112,
            text=f"{plan['percent']:.0f}%",
            fill=PRIMARY,
            font=(FONT, 11, "bold"),
        )
        return canvas

    def _weekly_chart(self, parent, weekly):
        """Render a compact seven-day activity chart."""
        width, height = 330, 142
        canvas = tk.Canvas(
            parent, width=width, height=height, bg=SURFACE, highlightthickness=0, bd=0
        )
        top, baseline = 18, 105
        maximum = max([item["count"] for item in weekly] + [1])
        canvas.create_line(8, baseline, width - 8, baseline, fill=BORDER, width=1)
        gap = (width - 24) / max(1, len(weekly))
        for index, item in enumerate(weekly):
            center = 12 + gap * index + gap / 2
            bar_height = (
                0
                if not item["count"]
                else max(7, item["count"] / maximum * (baseline - top))
            )
            canvas.create_rectangle(
                center - 10,
                baseline - bar_height,
                center + 10,
                baseline,
                fill=PRIMARY,
                outline="",
            )
            canvas.create_text(
                center,
                baseline - bar_height - 9,
                text=str(item["count"]),
                fill=TEXT if item["count"] else MUTED,
                font=(FONT, 8),
            )
            canvas.create_text(
                center,
                125,
                text=item["date"][5:],
                fill=MUTED,
                font=(FONT, 8),
            )
        return canvas

    def _legacy_home(self):
        if not self.check_session():
            return
        self.signed_in = True
        self.users_page = None
        self.editor = None
        self.engine = None
        self.load_bank()
        self._nav_key = "home"
        self.clear(self.tr("首页"), show_heading=False)
        name = self.user["name"] if self.user else self.tr("访客")
        subjects = sorted({q.subject for q in self.public_questions})
        wrong = {}
        history = []
        accuracy_text = "—"
        bank_error = None
        try:
            data = self.progress.load()
            wrong = data.get("wrong") or {}
            history = data.get("history") or []
            answered = sum(record["total"] for record in history)
            correct = sum(record["correct"] for record in history)
            if answered:
                accuracy_text = f"{correct / answered * 100:.0f}%"
        except DataError as exc:
            bank_error = str(exc)
        shell = ttk.Frame(self.body, style="App.TFrame")
        shell.pack(fill="both", expand=True)
        feed = ttk.Frame(shell, style="App.TFrame")
        feed.pack(side="left", fill="both", expand=True, padx=(0, 16))
        rail = tk.Frame(shell, bg=BG, width=280)
        self.home_rail = rail
        if self.root.winfo_width() >= 1020:
            rail.pack(side="right", fill="y")
        rail.pack_propagate(False)
        composer = card_frame(feed, pad=16)
        composer.pack(fill="x", pady=(0, 16))
        tk.Label(composer, text=name, bg=SURFACE, fg=MUTED, font=TYPE_HINT).pack(anchor="w")
        tk.Label(
            composer,
            text=self.tr("有什么想练习的？"),
            bg=SURFACE,
            fg=TEXT,
            font=(FONT, 16, "bold"),
        ).pack(anchor="w", pady=(6, 10))
        entry_actions = ttk.Frame(composer, style="Card.TFrame")
        entry_actions.pack(anchor="w")
        ttk.Button(
            entry_actions,
            text=self.tr("公共题库练习"),
            command=self.configure,
            style="Accent.TButton",
        ).pack(side="left", padx=(0, 8))
        if self.user:
            ttk.Button(
                entry_actions,
                text=self.tr("我的题库"),
                command=self.personal_bank_page,
                style="Tool.TButton",
            ).pack(side="left")
        try:
            plan = self.learning_plan.summary()
        except DataError as exc:
            plan = None
            bank_error = bank_error or str(exc)
        if plan:
            plan_card = card_frame(feed, pad=16)
            plan_card.pack(fill="x", pady=(0, 16))
            plan_head = tk.Frame(plan_card, bg=SURFACE)
            plan_head.pack(fill="x")
            tk.Label(
                plan_head,
                text=self.tr("每日学习计划"),
                bg=SURFACE,
                fg=TEXT,
                font=(FONT, 14, "bold"),
            ).pack(side="left")
            ttk.Button(
                plan_head,
                text=self.tr("调整每日目标"),
                command=self.set_daily_goal,
                style="Tool.TButton",
            ).pack(side="right")
            dashboard = tk.Frame(plan_card, bg=SURFACE)
            dashboard.pack(fill="x", pady=(12, 0))
            self._plan_ring(dashboard, plan).pack(side="left", padx=(0, 18))
            goal_stats = tk.Frame(dashboard, bg=SURFACE)
            goal_stats.pack(side="left", fill="y", padx=(0, 18))
            for value, title in (
                (plan["daily_goal"], self.tr("每日目标")),
                (plan["remaining"], self.tr("还差题数")),
                (plan["streak"], self.tr("连续学习天数")),
            ):
                stat = tk.Frame(goal_stats, bg=HOVER, padx=14, pady=8)
                stat.pack(fill="x", pady=(0, 7))
                tk.Label(
                    stat,
                    text=str(value),
                    bg=HOVER,
                    fg=TEXT,
                    font=(FONT, 15, "bold"),
                ).pack(side="left")
                tk.Label(
                    stat, text=title, bg=HOVER, fg=MUTED, font=TYPE_HINT
                ).pack(side="left", padx=(9, 0))
            chart = tk.Frame(dashboard, bg=SURFACE)
            chart.pack(side="left", fill="both", expand=True)
            tk.Label(
                chart,
                text=self.tr("最近 7 天"),
                bg=SURFACE,
                fg=TEXT,
                font=(FONT, 11, "bold"),
            ).pack(anchor="w")
            self._weekly_chart(chart, plan["weekly"]).pack(anchor="w")
        tk.Label(
            feed,
            text=self.tr(
                "已答题 {0} · 完成 {1} 次 · 错题 {2} · 正确率 {3}",
                sum(record["total"] for record in history),
                len(history),
                len(wrong),
                accuracy_text,
            ),
            bg=BG,
            fg=MUTED,
            font=TYPE_HINT,
        ).pack(anchor="w", pady=(0, 12))
        tk.Label(feed, text=self.tr("你的学习动态"), bg=BG, fg=TEXT, font=(FONT, 15, "bold")).pack(
            anchor="w", pady=(4, 8)
        )
        if bank_error:
            empty = card_frame(feed, pad=16)
            empty.pack(fill="x")
            tk.Label(empty, text=self.tr("学习数据加载失败"), bg=SURFACE, fg=TEXT, font=(FONT, 13, "bold")).pack(
                anchor="w"
            )
            tk.Label(empty, text=self.tr(bank_error), bg=SURFACE, fg=MUTED, wraplength=520, justify="left").pack(
                anchor="w", pady=8
            )
            ttk.Button(empty, text=self.tr("重新加载题库"), command=self.home, style="Accent.TButton").pack(anchor="w")
        elif not history:
            empty = card_frame(feed, pad=16)
            empty.pack(fill="x")
            tk.Label(empty, text=self.tr("还没有学习记录"), bg=SURFACE, fg=TEXT, font=(FONT, 13, "bold")).pack(
                anchor="w"
            )
            tk.Label(
                empty,
                text=self.tr("完成第一次练习后，学习动态会显示在这里。"),
                bg=SURFACE,
                fg=MUTED,
                wraplength=520,
                justify="left",
            ).pack(anchor="w", pady=8)
            ttk.Button(empty, text=self.tr("开始第一次练习"), command=self.configure, style="Accent.TButton").pack(
                anchor="w"
            )
        for record in list(reversed(history))[:6]:
            post = card_frame(feed, pad=14)
            post.pack(fill="x", pady=(0, 10))
            tk.Label(
                post,
                text=f"{name}  ·  {self._relative_time(record['date'])}",
                bg=SURFACE,
                fg=MUTED,
                font=TYPE_HINT,
            ).pack(anchor="w")
            tk.Label(
                post,
                text=self.tr("完成了 {0} · 正确率 {1}%", record["subject"], f"{record['accuracy']:.0f}"),
                bg=SURFACE,
                fg=TEXT,
                font=TYPE_BODY,
                wraplength=520,
                justify="left",
            ).pack(anchor="w", pady=(6, 4))
            tk.Label(
                post,
                text=self.tr("{0} 道题", record["total"]),
                bg=SURFACE,
                fg=MUTED,
                font=TYPE_HINT,
            ).pack(anchor="w", pady=(0, 8))
            actions = tk.Frame(post, bg=SURFACE)
            actions.pack(anchor="w")
            self._text_button(actions, self.tr("查看详情"), self.history, bg=SURFACE).pack(side="left", padx=(0, 12))
            subject_name = record["subject"].split(",")[0].strip()
            self._text_button(
                actions, self.tr("再练一次"), lambda value=subject_name: self.configure(value), bg=SURFACE
            ).pack(side="left")
        search_shell = tk.Frame(rail, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        search_shell.pack(fill="x", pady=(0, 8))
        self.home_search = tk.StringVar()
        search = tk.Entry(
            search_shell,
            textvariable=self.home_search,
            bg=SURFACE,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=TYPE_BODY,
        )
        search.pack(fill="x", padx=10, ipady=9)
        self._search_hint = self.tr("搜索题目、科目或错题")
        search.insert(0, self._search_hint)
        search.configure(fg=MUTED)

        def _focus_in(_e):
            if search.get() == self._search_hint:
                search.delete(0, "end")
                search.configure(fg=TEXT)

        def _focus_out(_e):
            if not search.get().strip():
                search.insert(0, self._search_hint)
                search.configure(fg=MUTED)

        search.bind("<FocusIn>", _focus_in)
        search.bind("<FocusOut>", _focus_out)
        search.bind("<KeyRelease>", self._filter_home_search)
        self.search_hits = tk.Frame(rail, bg=BG)
        self.search_hits.pack(fill="x", pady=(0, 12))
        tk.Label(rail, text=self.tr("学习进度"), bg=BG, fg=TEXT, font=(FONT, 13, "bold")).pack(
            anchor="w", pady=(4, 6)
        )
        tk.Label(
            rail,
            text=self.tr("综合正确率 {0} · 待复习 {1}", accuracy_text, len(wrong)),
            bg=BG,
            fg=MUTED,
            font=TYPE_HINT,
            wraplength=250,
            justify="left",
        ).pack(anchor="w")
        bar = ttk.Progressbar(
            rail, maximum=100, value=0 if accuracy_text == "—" else float(accuracy_text.strip("%"))
        )
        bar.pack(fill="x", pady=(8, 16))
        tk.Label(rail, text=self.tr("推荐练习"), bg=BG, fg=TEXT, font=(FONT, 13, "bold")).pack(
            anchor="w", pady=(4, 8)
        )
        counts = {}
        for question in self.public_questions:
            counts[question.subject] = counts.get(question.subject, 0) + 1
        subject_accuracy = {}
        for record in history:
            for part in str(record["subject"]).split(","):
                key = part.strip()
                bucket = subject_accuracy.setdefault(key, [0, 0])
                bucket[0] += record["correct"]
                bucket[1] += record["total"]
        self._subject_rows = []
        self._search_index = []
        for subject in subjects:
            row = card_frame(rail, pad=12)
            row.pack(fill="x", pady=(0, 8))
            tk.Label(row, text=subject, bg=SURFACE, fg=TEXT, font=(FONT, 12, "bold")).pack(anchor="w")
            tk.Label(
                row,
                text=self.tr("{0} 道题", counts.get(subject, 0)),
                bg=SURFACE,
                fg=MUTED,
                font=TYPE_HINT,
            ).pack(anchor="w")
            got = subject_accuracy.get(subject)
            rate = f"{got[0] / got[1] * 100:.0f}%" if got and got[1] else "—"
            tk.Label(
                row,
                text=self.tr("最近正确率 {0}", rate),
                bg=SURFACE,
                fg=MUTED,
                font=TYPE_HINT,
            ).pack(anchor="w", pady=(4, 8))
            self._text_button(
                row, self.tr("开始练习"), lambda value=subject: self.configure(value), bg=SURFACE
            ).pack(anchor="w")
            self._subject_rows.append((subject.lower(), row))
            self._search_index.append(("subject", subject, subject, lambda value=subject: self.configure(value)))
        for question in self.public_questions:
            self._search_index.append(
                (
                    "question",
                    f"{question.id} {question.subject} {question.topic} {question.question}".lower(),
                    f"{question.id} · {question.question}",
                    lambda qid=question.id: self._open_question_preview(qid),
                )
            )
        for key, record in wrong.items():
            question = self.by_id.get(key)
            label = question.question if question else key
            self._search_index.append(
                (
                    "wrong",
                    f"{key} {label}".lower(),
                    self.tr("错题 · {0}", label),
                    self.notebook,
                )
            )
        if self.user and self.user["role"] == "admin":
            admin = ttk.Frame(feed, style="App.TFrame")
            admin.pack(fill="x", pady=(8, 0))
            ttk.Button(admin, text=self.tr("题库管理 / 上传图片"), command=self.manage_questions, style="Tool.TButton").pack(
                side="left", padx=(0, 8)
            )
            ttk.Button(admin, text=self.tr("用户管理"), command=self.manage_users, style="Tool.TButton").pack(
                side="left"
            )
        if self.bank.warnings:
            self.label(
                self.tr("题库提示（其他有效题目仍可使用）：\n") + "\n".join(self.bank.warnings),
                "Warning.TLabel",
            )
        if self.personal_bank_error:
            self.label(self.tr(self.personal_bank_error), "Warning.TLabel")

    def home(self):
        """Dashboard matching the approved items 2/4 mock-up."""
        if not self.check_session():
            return
        self.signed_in = True
        self.users_page = None
        self.editor = None
        self.engine = None
        self.load_bank()
        self._nav_key = "home"
        self.clear(self.tr("首页"), show_heading=False)
        self.chrome.pack_forget()
        self.rule.pack_forget()
        self.body.configure(padding=(18, 18))

        name = self.user["name"] if self.user else self.tr("访客")
        hour = datetime.now().hour
        greeting = self.tr("早上好") if hour < 12 else self.tr("下午好") if hour < 18 else self.tr("晚上好")
        tk.Label(
            self.body,
            text=f"{greeting}，{name}",
            bg=BG,
            fg=TEXT,
            font=(FONT, 24, "bold"),
        ).pack(anchor="w", pady=(0, 16))

        wrong, history, data_error = {}, [], ""
        try:
            progress = self.progress.load()
            wrong = progress.get("wrong") or {}
            history = progress.get("history") or []
        except DataError as exc:
            data_error = str(exc)
        try:
            plan = self.learning_plan.summary()
        except DataError as exc:
            plan = {
                "daily_goal": 20,
                "today": 0,
                "remaining": 20,
                "percent": 0,
                "streak": 0,
                "weekly": [],
            }
            data_error = data_error or str(exc)

        top = tk.Frame(self.body, bg=BG)
        top.pack(fill="x")
        goal = card_frame(top, pad=20)
        goal.pack(side="left", fill="both", expand=True, padx=(0, 12))
        tk.Label(
            goal,
            text=self.tr("今日目标"),
            bg=SURFACE,
            fg=TEXT,
            font=(FONT, 15, "bold"),
        ).pack(anchor="w")
        score = tk.Frame(goal, bg=SURFACE)
        score.pack(anchor="w", pady=(16, 2))
        tk.Label(
            score,
            text=str(plan["today"]),
            bg=SURFACE,
            fg=PRIMARY,
            font=(FONT, 36, "bold"),
        ).pack(side="left")
        tk.Label(
            score,
            text=f" / {plan['daily_goal']} {self.tr('题')}",
            bg=SURFACE,
            fg=TEXT,
            font=(FONT, 22, "bold"),
        ).pack(side="left", pady=(10, 0))
        tk.Label(
            goal,
            text=self.tr("已完成 {0}%", f"{plan['percent']:.0f}"),
            bg=SURFACE,
            fg=TEXT,
            font=TYPE_BODY,
        ).pack(anchor="w", pady=(0, 8))
        progress_canvas = tk.Canvas(
            goal, height=18, bg=SURFACE, highlightthickness=0, bd=0
        )
        progress_canvas.pack(fill="x", pady=(0, 20))

        def draw_goal_bar(_event=None):
            progress_canvas.delete("all")
            width = max(progress_canvas.winfo_width(), 20)
            progress_canvas.create_rectangle(0, 2, width, 16, fill="#363A40", outline="")
            progress_canvas.create_rectangle(
                0,
                2,
                width * plan["percent"] / 100,
                16,
                fill=PRIMARY,
                outline="",
            )

        progress_canvas.bind("<Configure>", draw_goal_bar)
        self._mock_action(
            goal,
            self.tr("继续今日练习"),
            lambda: self.configure(bank_kind="public"),
            True,
            padx=24,
            pady=12,
        ).pack(fill="x")

        side = tk.Frame(top, bg=BG)
        side.pack(side="left", fill="both", expand=True)
        streak = card_frame(side, pad=18)
        streak.pack(fill="x", pady=(0, 12))
        tk.Label(
            streak,
            text=self.tr("连续学习"),
            bg=SURFACE,
            fg=TEXT,
            font=(FONT, 14, "bold"),
        ).pack(anchor="w")
        tk.Label(
            streak,
            text=self.tr("{0} 天", plan["streak"]),
            bg=SURFACE,
            fg=SUCCESS_FG,
            font=(FONT, 30, "bold"),
        ).pack(anchor="w", pady=(7, 6))
        days = tk.Frame(streak, bg=SURFACE)
        days.pack(fill="x")
        day_names = self.tr("一 二 三 四 五 六 日").split()
        weekly = plan["weekly"][-7:]
        for index, label in enumerate(day_names):
            cell = tk.Frame(days, bg=SURFACE)
            cell.pack(side="left", expand=True)
            tk.Label(cell, text=label, bg=SURFACE, fg=MUTED, font=(FONT, 8)).pack()
            done = index < len(weekly) and weekly[index]["count"] > 0
            tk.Label(
                cell,
                text="●" if done else "○",
                bg=SURFACE,
                fg=SUCCESS_FG if done else PRIMARY if index == len(day_names) - 1 else MUTED,
                font=(FONT, 15),
            ).pack()

        setting = card_frame(side, pad=18)
        setting.pack(fill="x")
        tk.Label(
            setting,
            text=self.tr("设置每日目标"),
            bg=SURFACE,
            fg=TEXT,
            font=(FONT, 14, "bold"),
        ).pack(anchor="w")
        goal_row = tk.Frame(setting, bg=SURFACE)
        goal_row.pack(fill="x", pady=(10, 0))
        goal_value = tk.Label(
            goal_row,
            text=str(plan["daily_goal"]),
            bg=HOVER,
            fg=TEXT,
            font=(FONT, 14),
            padx=18,
            pady=8,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        goal_value.pack(side="left")
        tk.Label(
            goal_row,
            text=self.tr("题 / 天"),
            bg=SURFACE,
            fg=TEXT,
            font=TYPE_BODY,
        ).pack(side="left", padx=12)
        self._mock_action(
            goal_row, self.tr("调整"), self.set_daily_goal, False, padx=12, pady=8
        ).pack(side="right")

        recent = card_frame(self.body, pad=18)
        recent.pack(fill="x", pady=(14, 0))
        tk.Label(
            recent,
            text=self.tr("最近学习"),
            bg=SURFACE,
            fg=TEXT,
            font=(FONT, 14, "bold"),
        ).pack(anchor="w", pady=(0, 8))
        if history:
            for record in list(reversed(history))[:5]:
                row = tk.Frame(recent, bg=SURFACE)
                row.pack(fill="x", pady=6)
                tk.Label(
                    row,
                    text=str(record["subject"]),
                    bg=SURFACE,
                    fg=TEXT,
                    font=(FONT, 10, "bold"),
                    anchor="w",
                ).pack(side="left", fill="x", expand=True)
                tk.Label(
                    row,
                    text=self.tr("{0} 题", record["total"]),
                    bg=SURFACE,
                    fg=TEXT,
                    font=TYPE_HINT,
                ).pack(side="left", padx=18)
                tk.Label(
                    row,
                    text=str(record["date"])[:10],
                    bg=SURFACE,
                    fg=MUTED,
                    font=TYPE_HINT,
                ).pack(side="right")
                tk.Frame(recent, bg=BORDER, height=1).pack(fill="x")
        else:
            tk.Label(
                recent,
                text=self.tr("还没有学习记录，完成第一次练习后会显示在这里。"),
                bg=SURFACE,
                fg=MUTED,
                font=TYPE_BODY,
            ).pack(anchor="w", pady=(10, 12))
            self._mock_action(
                recent,
                self.tr("开始第一次练习"),
                lambda: self.configure(bank_kind="public"),
                True,
            ).pack(anchor="w")
        if data_error:
            tk.Label(
                self.body,
                text=data_error,
                bg=BG,
                fg=ERROR,
                font=TYPE_HINT,
            ).pack(anchor="w", pady=(8, 0))
        if self.user and self.user["role"] == "admin":
            admin = tk.Frame(self.body, bg=BG)
            admin.pack(fill="x", pady=(12, 0))
            self._mock_action(admin, self.tr("题库管理 / 上传图片"), self.manage_questions, False).pack(
                side="left", padx=(0, 8)
            )
            self._mock_action(admin, self.tr("用户管理"), self.manage_users, False).pack(side="left")

    def set_daily_goal(self):
        try:
            current = self.learning_plan.load()["daily_goal"]
            goal = simpledialog.askinteger(
                self.tr("每日目标"),
                self.tr("请输入每天计划完成的题数（1–500）："),
                initialvalue=current,
                minvalue=1,
                maxvalue=500,
                parent=self.root,
            )
            if goal is not None:
                self.learning_plan.set_goal(goal)
                self.home()
        except (DataError, ValueError) as exc:
            messagebox.showerror(self.tr("保存失败"), self.tr(str(exc)), parent=self.root)

    def _legacy_personal_bank_page(self):
        if not self.user:
            messagebox.showinfo(
                self.tr("权限提示"),
                self.tr("请先登录账户，再导入或使用个人题库。"),
                parent=self.root,
            )
            return
        if not self.check_session():
            return
        self._nav_key = "personal"
        self.clear(self.tr("我的题库"))
        self.load_bank()
        self.import_preview = None
        intro = card_frame(self.body, pad=18)
        intro.pack(fill="x", pady=(0, 14))
        tk.Label(
            intro,
            text=self.tr("个人题库导入"),
            bg=SURFACE,
            fg=TEXT,
            font=(FONT, 16, "bold"),
        ).pack(anchor="w")
        tk.Label(
            intro,
            text=self.tr(
                "个人题库仅属于当前账户，不会修改管理员维护的公共题库。支持 JSON 和 CSV；先校验预览，确认后才会保存。"
            ),
            bg=SURFACE,
            fg=MUTED,
            font=TYPE_BODY,
            wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=(6, 14))
        workflow = tk.Frame(intro, bg=SURFACE)
        workflow.pack(fill="x")
        self.import_steps = []
        for number, title, hint in (
            ("1", self.tr("上传文件"), self.tr("选择 JSON 或 CSV")),
            ("2", self.tr("自动校验"), self.tr("检查格式与重复题")),
            ("3", self.tr("预览题目"), self.tr("查看有效与错误项目")),
            ("4", self.tr("确认合并"), self.tr("写入当前个人题库")),
        ):
            step = tk.Frame(workflow, bg=HOVER, padx=12, pady=10)
            step.pack(side="left", fill="x", expand=True, padx=(0, 8))
            badge = tk.Label(
                step,
                text=number,
                width=2,
                bg=PRIMARY if number == "1" else TRACK,
                fg=ON_PRIMARY if number == "1" else MUTED,
                font=(FONT, 10, "bold"),
            )
            badge.pack(anchor="w")
            title_label = tk.Label(
                step,
                text=title,
                bg=HOVER,
                fg=TEXT,
                font=(FONT, 10, "bold"),
            )
            title_label.pack(anchor="w", pady=(5, 1))
            tk.Label(
                step, text=hint, bg=HOVER, fg=MUTED, font=(FONT, 8)
            ).pack(anchor="w")
            self.import_steps.append((badge, title_label))

        upload_zone = tk.Frame(
            self.body,
            bg=SURFACE,
            highlightthickness=2,
            highlightbackground=PRIMARY,
            padx=18,
            pady=16,
        )
        upload_zone.pack(fill="x", pady=(0, 14))
        upload_copy = tk.Frame(upload_zone, bg=SURFACE)
        upload_copy.pack(side="left", fill="x", expand=True)
        tk.Label(
            upload_copy,
            text=self.tr("选择题库文件开始导入"),
            bg=SURFACE,
            fg=TEXT,
            font=(FONT, 12, "bold"),
        ).pack(anchor="w")
        tk.Label(
            upload_copy,
            text=self.tr("支持 .json 与 .csv；文件会先校验，不会直接覆盖现有题库。"),
            bg=SURFACE,
            fg=MUTED,
            font=TYPE_HINT,
        ).pack(anchor="w", pady=(4, 0))
        actions = tk.Frame(upload_zone, bg=SURFACE)
        actions.pack(side="right")
        ttk.Button(
            actions,
            text=self.tr("选择 JSON / CSV 文件"),
            command=self.choose_import_file,
            style="Accent.TButton",
        ).pack(side="left", padx=(0, 8))
        practice = ttk.Button(
            actions,
            text=self.tr("练习个人题库（{0} 题）", len(self.personal_questions)),
            command=lambda: self.configure(bank_kind="personal"),
            style="Tool.TButton",
        )
        practice.pack(side="left")
        if not self.personal_questions:
            practice.state(["disabled"])
        self.import_summary = ttk.Label(
            self.body,
            text=self.tr("等待选择文件"),
            style="Muted.TLabel",
        )
        self.import_summary.pack(anchor="w", pady=(0, 8))
        columns = ("row", "id", "status", "message")
        self.import_table = ttk.Treeview(
            self.body, columns=columns, show="headings", height=12
        )
        for key, title, width in (
            ("row", "#", 55),
            ("id", self.tr("题目 ID"), 130),
            ("status", self.tr("状态"), 100),
            ("message", self.tr("结果 / 错误原因"), 520),
        ):
            self.import_table.heading(key, text=title)
            self.import_table.column(key, width=width, anchor="w")
        self.import_table.pack(fill="both", expand=True)
        self.import_confirm = ttk.Button(
            self.body,
            text=self.tr("确认导入有效题目"),
            command=self.confirm_personal_import,
            style="Accent.TButton",
        )
        self.import_confirm.pack(anchor="w", pady=(12, 4))
        self.import_confirm.state(["disabled"])

    def personal_bank_page(self):
        """Import workflow matching the approved right-hand mock-up."""
        if not self.user:
            messagebox.showinfo(
                self.tr("权限提示"),
                self.tr("请先登录账户，再导入或使用个人题库。"),
                parent=self.root,
            )
            return
        if not self.check_session():
            return
        self._nav_key = "personal"
        self.clear(self.tr("导入题库"), show_heading=False)
        self.chrome.pack_forget()
        self.rule.pack_forget()
        self.body.configure(padding=(18, 18))
        self.load_bank()
        self.import_preview = None

        tk.Label(
            self.body,
            text=self.tr("导入题库"),
            bg=BG,
            fg=TEXT,
            font=(FONT, 24, "bold"),
        ).pack(anchor="w", pady=(0, 16))

        workflow = tk.Frame(self.body, bg=BG)
        workflow.pack(fill="x", pady=(0, 16))
        self.import_steps = []
        step_data = (
            ("1", self.tr("选择文件")),
            ("2", self.tr("数据校验")),
            ("3", self.tr("预览确认")),
            ("4", self.tr("合并完成")),
        )
        for index, (number, title) in enumerate(step_data):
            cell = tk.Frame(workflow, bg=BG)
            cell.pack(side="left", fill="x", expand=True)
            badge = tk.Label(
                cell,
                text=number,
                width=2,
                height=1,
                bg="#183C70" if index < 2 else PRIMARY if index == 2 else HOVER,
                fg="#FFFFFF" if index <= 2 else MUTED,
                font=(FONT, 13, "bold"),
                padx=5,
                pady=5,
                highlightthickness=1,
                highlightbackground=PRIMARY if index <= 2 else MUTED,
            )
            badge.pack()
            title_label = tk.Label(
                cell,
                text=title,
                bg=BG,
                fg=TEXT if index <= 2 else MUTED,
                font=(FONT, 10),
            )
            title_label.pack(pady=(6, 0))
            self.import_steps.append((badge, title_label))

        file_card = tk.Frame(
            self.body,
            bg=SURFACE,
            padx=16,
            pady=15,
            highlightthickness=1,
            highlightbackground=BORDER,
            cursor="hand2",
        )
        file_card.pack(fill="x", pady=(0, 14))
        self.import_file_name = tk.Label(
            file_card,
            text=self.tr("▤  选择 JSON / CSV 文件"),
            bg=SURFACE,
            fg=TEXT,
            font=(FONT, 12),
            cursor="hand2",
        )
        self.import_file_name.pack(side="left")
        self.import_file_total = tk.Label(
            file_card,
            text=self.tr("点击选择文件"),
            bg=SURFACE,
            fg=MUTED,
            font=TYPE_HINT,
            cursor="hand2",
        )
        self.import_file_total.pack(side="right")
        bind_whole(file_card, self.choose_import_file)

        stats = tk.Frame(self.body, bg=BG)
        stats.pack(fill="x", pady=(0, 14))
        self.import_stat_labels = {}
        for key, title, color in (
            ("valid", self.tr("有效"), SUCCESS_FG),
            ("warning", self.tr("警告"), "#F5C542"),
            ("error", self.tr("错误"), ERROR),
            ("duplicate", self.tr("重复"), MUTED),
        ):
            card = card_frame(stats, pad=14)
            card.pack(side="left", fill="x", expand=True, padx=(0, 10))
            tk.Label(card, text=title, bg=SURFACE, fg=color, font=TYPE_HINT).pack(anchor="w")
            value = tk.Label(
                card, text="0", bg=SURFACE, fg=color, font=(FONT, 22, "bold")
            )
            value.pack(anchor="w", pady=(4, 0))
            self.import_stat_labels[key] = value

        columns = ("status", "id", "subject", "topic", "difficulty", "question")
        self.import_table = ttk.Treeview(
            self.body, columns=columns, show="headings", height=9
        )
        for key, title, width in (
            ("status", self.tr("状态"), 95),
            ("id", "ID", 90),
            ("subject", self.tr("学科"), 105),
            ("topic", self.tr("主题"), 120),
            ("difficulty", self.tr("难度"), 90),
            ("question", self.tr("题目"), 390),
        ):
            self.import_table.heading(key, text=title)
            self.import_table.column(key, width=width, anchor="w")
        self.import_table.pack(fill="both", expand=True, pady=(0, 14))
        self.import_table.tag_configure("valid", foreground=SUCCESS_FG)
        self.import_table.tag_configure("duplicate", foreground=MUTED)
        self.import_table.tag_configure("error", foreground=ERROR)

        permissions = tk.Frame(self.body, bg=BG)
        permissions.pack(fill="x")
        tk.Label(
            permissions,
            text=self.tr("导入后权限"),
            bg=BG,
            fg=TEXT,
            font=(FONT, 13, "bold"),
        ).pack(anchor="w")
        option_row = tk.Frame(permissions, bg=BG)
        option_row.pack(anchor="w", pady=(8, 0))
        tk.Label(
            option_row,
            text="◉  " + self.tr("仅自己可用"),
            bg=BG,
            fg=TEXT,
            font=TYPE_BODY,
        ).pack(side="left")
        tk.Label(
            option_row,
            text="○  " + self.tr("共享给本机所有账户（需管理员批准）"),
            bg=BG,
            fg=MUTED,
            font=TYPE_BODY,
        ).pack(side="left", padx=(24, 0))

        footer = tk.Frame(self.body, bg=BG)
        footer.pack(fill="x", pady=(18, 0))
        self.import_summary = tk.Label(
            footer,
            text=self.tr("ⓘ 错误记录不会导入题库"),
            bg=BG,
            fg=MUTED,
            font=TYPE_HINT,
        )
        self.import_summary.pack(side="left")
        self.import_confirm = self._mock_action(
            footer,
            self.tr("合并 0 道有效题目"),
            self.confirm_personal_import,
            True,
            padx=16,
            pady=10,
        )
        self.import_confirm.pack(side="right")
        self._mock_action(
            footer,
            self.tr("返回修改"),
            self.choose_import_file,
            False,
            padx=14,
            pady=10,
        ).pack(side="right", padx=(0, 10))

    def _set_import_step(self, active):
        for index, (badge, title) in enumerate(getattr(self, "import_steps", []), 1):
            selected = index <= active
            badge.configure(
                bg=PRIMARY if selected else TRACK,
                fg=ON_PRIMARY if selected else MUTED,
            )
            title.configure(fg=TEXT if selected else MUTED)

    def choose_import_file(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title=self.tr("选择题库文件"),
            filetypes=(("JSON / CSV", "*.json *.csv"), ("JSON", "*.json"), ("CSV", "*.csv")),
        )
        if not path:
            return
        try:
            preview = QuestionImportService(
                self.personal_bank, self.public_questions
            ).preview(path)
        except (DataError, ValueError) as exc:
            messagebox.showerror(self.tr("导入文件无效"), self.tr(str(exc)), parent=self.root)
            return
        self.import_preview = preview
        self._set_import_step(3 if preview.valid else 2)
        self.import_table.delete(*self.import_table.get_children())
        labels = {
            "valid": self.tr("有效"),
            "duplicate": self.tr("重复"),
            "error": self.tr("错误"),
        }
        for row in preview.rows:
            self.import_table.insert(
                "",
                "end",
                values=(
                    labels[row["status"]],
                    row["id"],
                    row.get("subject", ""),
                    row.get("topic", ""),
                    row.get("difficulty", ""),
                    row.get("question", "") or self.tr(row["message"]),
                ),
                tags=(row["status"],),
            )
        if getattr(self, "import_file_name", None):
            self.import_file_name.configure(text=f"▤  {preview.path.name}")
            self.import_file_total.configure(text=self.tr("共 {0} 条", preview.total))
        for key, value in (
            ("valid", len(preview.valid)),
            ("warning", 0),
            ("error", preview.errors),
            ("duplicate", preview.duplicates),
        ):
            label = getattr(self, "import_stat_labels", {}).get(key)
            if label:
                label.configure(text=str(value))
        self.import_summary.configure(
            text=self.tr("ⓘ 错误记录不会导入题库，可下载校验报告")
        )
        self.import_confirm.configure(
            text=self.tr("合并 {0} 道有效题目", len(preview.valid)),
            bg=PRIMARY if preview.valid else PRIMARY_DISABLED,
        )

    def confirm_personal_import(self):
        preview = getattr(self, "import_preview", None)
        if not preview or not preview.valid:
            return
        if not messagebox.askyesno(
            self.tr("确认导入"),
            self.tr("将 {0} 道有效题目加入当前账户的个人题库？", len(preview.valid)),
            parent=self.root,
        ):
            return
        try:
            added = QuestionImportService(
                self.personal_bank, self.public_questions
            ).confirm(preview)
        except (DataError, ValueError) as exc:
            messagebox.showerror(self.tr("导入失败"), self.tr(str(exc)), parent=self.root)
            return
        messagebox.showinfo(
            self.tr("导入完成"),
            self.tr("已导入 {0} 道题；重复题目保持跳过。", len(added)),
            parent=self.root,
        )
        self.personal_bank_page()

    def _open_question_preview(self, question_id):
        question = self.by_id.get(question_id)
        if question:
            self.start_quiz([question])

    def _filter_home_search(self, _event=None):
        raw = self.home_search.get().strip()
        query = "" if raw == getattr(self, "_search_hint", "") else raw.lower()
        for name, row in getattr(self, "_subject_rows", []):
            if not row.winfo_exists():
                continue
            if not query or query in name:
                row.pack(fill="x", pady=(0, 8))
            else:
                row.pack_forget()
        host = getattr(self, "search_hits", None)
        if not host or not host.winfo_exists():
            return
        for child in host.winfo_children():
            child.destroy()
        if not query:
            return
        hits = [item for item in getattr(self, "_search_index", []) if query in item[1]][:8]
        if not hits:
            tk.Label(host, text=self.tr("没有匹配结果"), bg=BG, fg=MUTED, font=TYPE_HINT).pack(anchor="w")
            return
        for kind, _hay, label, action in hits:
            tag = {"subject": self.tr("科目"), "question": self.tr("题目"), "wrong": self.tr("错题")}.get(
                kind, kind
            )
            line = tk.Button(
                host,
                text=f"{tag} · {label[:48]}",
                command=action,
                bg=SURFACE,
                fg=self._native_button_ink(TEXT),
                activebackground=HOVER,
                activeforeground=self._native_button_ink(TEXT),
                relief="flat",
                bd=0,
                anchor="w",
                padx=10,
                pady=8,
                wraplength=240,
                justify="left",
                cursor="hand2",
                font=TYPE_HINT,
            )
            line.pack(fill="x", pady=2)

    def _toggle_subject_card(self, name):
        current = getattr(self, "_expanded_subject", None)
        for subject, (card, detail) in getattr(self, "_home_subjects", {}).items():
            if not card.winfo_exists():
                continue
            open_this = name == subject and current != name
            if open_this:
                detail.pack(fill="x", pady=(4, 0))
                card.configure(highlightbackground=PRIMARY, highlightthickness=2, bg=SELECTED_BG)
            else:
                detail.pack_forget()
                card.configure(highlightbackground=BORDER, highlightthickness=1, bg=SURFACE)
        self._expanded_subject = None if current == name else name

    def configure(self, subject=None, bank_kind="public"):
        if not self.check_session():
            return
        if bank_kind == "personal" and not self.user:
            self.personal_bank_page()
            return
        self.load_bank()
        self.questions = (
            self.personal_questions if bank_kind == "personal" else self.public_questions
        )
        self._practice_bank_kind = bank_kind
        self.clear(self.tr("配置练习"))
        if not self.questions:
            self.label(
                self.tr(
                    "个人题库为空，请先导入 JSON 或 CSV 文件。"
                    if bank_kind == "personal"
                    else "题库为空，请添加或修复 data/questions 中的 JSON 文件，然后重新加载。"
                )
            )
            self.button(
                self.tr("返回我的题库") if bank_kind == "personal" else self.tr("返回首页"),
                self.personal_bank_page if bank_kind == "personal" else self.home,
            )
            return
        subjects = sorted({q.subject for q in self.questions})
        start = subject if subject in subjects else subjects[0]
        self.subject = tk.StringVar(value=start)
        self.topic = tk.StringVar(value=self.tr("全部"))
        self.difficulty = tk.StringVar(value=self.tr("全部"))
        self.count = tk.StringVar(value="5")
        self.label(self.tr("整轮限时（秒，0 表示不限时）"))
        ttk.Spinbox(self.body, from_=0, to=86400, textvariable=self.timer_seconds, width=12).pack(anchor="w")
        card = ttk.LabelFrame(self.body, text=self.tr("练习设置"), padding=16)
        card.pack(fill="x", pady=8)
        ttk.Label(card, text=self.tr("学科"), style="Card.TLabel").pack(anchor="w", pady=(0, 8))
        picker = ttk.Frame(card, style="Card.TFrame")
        picker.pack(fill="x")
        self._subject_cards = []
        counts = {}
        for question in self.questions:
            counts[question.subject] = counts.get(question.subject, 0) + 1
        for name in subjects:
            item = card_frame(picker, pad=12)
            item.pack(side="left", expand=True, fill="x", padx=(0, 8))
            subject_icon(item, name).pack(anchor="w")
            ttk.Label(item, text=name, style="Stat.TLabel").pack(anchor="w", pady=(8, 0))
            ttk.Label(
                item, text=self.tr("{0} 道题", counts.get(name, 0)), style="StatHint.TLabel"
            ).pack(anchor="w")
            self._subject_cards.append((item, name))
            bind_whole(item, lambda value=name: self._select_subject(value))
        filters = ttk.Frame(card, style="Card.TFrame")
        filters.pack(fill="x", pady=(16, 0))
        ttk.Label(filters, text=self.tr("主题"), style="Card.TLabel").pack(anchor="w", pady=(0, 4))
        self.topic_box = ttk.Combobox(filters, textvariable=self.topic, state="readonly")
        self.topic_box.pack(fill="x")
        ttk.Label(filters, text=self.tr("难度"), style="Card.TLabel").pack(anchor="w", pady=(12, 4))
        self.difficulty_box = ttk.Combobox(filters, textvariable=self.difficulty, state="readonly")
        # Keep combobox for filter values; chips are the visible control.
        self.difficulty_chips = ttk.Frame(filters, style="Card.TFrame")
        self.difficulty_chips.pack(fill="x")
        ttk.Label(
            card,
            text=self.tr("题目数量（不足时使用所有匹配题目；顺序随机）"),
            style="Card.TLabel",
        ).pack(anchor="w", pady=(12, 4))
        stepper = ttk.Frame(card, style="Card.TFrame")
        stepper.pack(fill="x")
        ttk.Button(stepper, text="−", width=3, command=lambda: self._nudge_count(-1)).pack(side="left")
        self.count_box = ttk.Spinbox(stepper, from_=1, to=20, textvariable=self.count, width=8)
        self.count_box.pack(side="left", padx=8)
        ttk.Button(stepper, text="+", width=3, command=lambda: self._nudge_count(1)).pack(side="left")
        self.count_box.bind("<KeyRelease>", self.show_count)
        self.count_box.bind("<<Increment>>", self.show_count)
        self.count_box.bind("<<Decrement>>", self.show_count)
        self._match_count = 0
        self.available = ttk.Label(card, text="", style="Card.TLabel")
        self.available.pack(anchor="w", pady=(10, 4))
        self.config_summary = ttk.Label(card, text="", style="Muted.TLabel")
        self.config_summary.pack(anchor="w", pady=(0, 10))
        self.topic_box.bind("<<ComboboxSelected>>", self.refresh_difficulties)
        self.refresh_filters()
        self._paint_subject_cards()
        self.start_button = ttk.Button(
            self.body, text=self.tr("开始练习"), command=self.start_configured, style="Accent.TButton"
        )
        self.start_button.pack(anchor="w", pady=4)
        ttk.Button(self.body, text=self.tr("返回首页"), command=self.home, style="Tool.TButton").pack(
            anchor="w", pady=4
        )
        self._sync_start_button()

    def _select_subject(self, name):
        self.subject.set(name)
        self.refresh_filters()
        self._paint_subject_cards()

    def _paint_subject_cards(self):
        chosen = self.subject.get()
        for item, name in getattr(self, "_subject_cards", []):
            if not item.winfo_exists():
                continue
            selected = name == chosen
            color = SELECTED_BG if selected else SURFACE
            item.configure(
                highlightbackground=PRIMARY if selected else BORDER,
                highlightthickness=2 if selected else 1,
                bg=color,
            )
            stack = list(item.winfo_children())
            while stack:
                child = stack.pop()
                stack.extend(child.winfo_children())
                try:
                    child.configure(bg=color)
                except tk.TclError:
                    pass

    def _sync_start_button(self):
        button = getattr(self, "start_button", None)
        if button is None or not button.winfo_exists():
            return
        count = getattr(self, "_match_count", 0)
        if count <= 0:
            button.state(["disabled"])
            button.configure(text=self.tr("没有匹配题目"))
        else:
            button.state(["!disabled"])
            button.configure(text=self.tr("开始练习（{0} 道）", min(self._wanted_count(), count)))

    def _wanted_count(self):
        try:
            return max(int(self.count.get()), 1)
        except (TypeError, ValueError):
            return 1

    def _nudge_count(self, delta):
        limit = max(getattr(self, "_match_count", 1), 1)
        value = min(max(self._wanted_count() + delta, 1), limit)
        self.count.set(str(value))
        self.show_count()

    def refresh_filters(self, event=None):
        subset = [q for q in self.questions if q.subject == self.subject.get()]
        self.topic_box["values"] = [self.tr("全部")] + sorted({q.topic for q in subset})
        self.topic.set(self.tr("全部"))
        self.refresh_difficulties()

    def refresh_difficulties(self, event=None):
        subset = [
            q
            for q in self.questions
            if q.subject == self.subject.get()
            and (self.topic.get() == self.tr("全部") or q.topic == self.topic.get())
        ]
        values = [self.tr("全部")] + sorted({q.difficulty for q in subset})
        self.difficulty_box["values"] = values
        self.difficulty.set(self.tr("全部"))
        self._rebuild_difficulty_chips(values)
        self.show_count()

    def _rebuild_difficulty_chips(self, values):
        host = getattr(self, "difficulty_chips", None)
        if host is None or not host.winfo_exists():
            return
        for child in host.winfo_children():
            child.destroy()
        self._difficulty_chip_widgets = []
        for value in values:
            chip = tk.Label(
                host,
                text=value,
                bg=SURFACE,
                fg=TEXT,
                font=TYPE_HINT,
                padx=12,
                pady=8,
                highlightthickness=1,
                highlightbackground=BORDER,
                cursor="hand2",
            )
            chip.pack(side="left", padx=(0, 8), pady=2)
            chip.bind("<Button-1>", lambda _e, item=value: self._select_difficulty(item))
            self._difficulty_chip_widgets.append((chip, value))
        self._paint_difficulty_chips()

    def _select_difficulty(self, value):
        self.difficulty.set(value)
        self._paint_difficulty_chips()
        self.show_count()

    def _paint_difficulty_chips(self):
        chosen = self.difficulty.get()
        for chip, value in getattr(self, "_difficulty_chip_widgets", []):
            if not chip.winfo_exists():
                continue
            selected = value == chosen
            chip.configure(
                bg=SELECTED_BG if selected else SURFACE,
                fg=PRIMARY if selected else TEXT,
                highlightbackground=PRIMARY if selected else BORDER,
                highlightthickness=2 if selected else 1,
            )

    def show_count(self, event=None):
        count = sum(
            q.subject == self.subject.get()
            and (self.topic.get() == self.tr("全部") or q.topic == self.topic.get())
            and (self.difficulty.get() == self.tr("全部") or q.difficulty == self.difficulty.get())
            for q in self.questions
        )
        previous = getattr(self, "_match_count", count)
        self._match_count = count
        formatter = lambda value: self.tr("当前匹配：{0} 道题", value)
        if getattr(self, "available", None) and self.available.winfo_exists():
            self.motion.roll_count(self.available, formatter, previous, count)
        box = getattr(self, "count_box", None)
        if box is not None:
            box.configure(to=max(count, 1))
            if count and self._wanted_count() > count:
                self.count.set(str(count))
        wanted = self._wanted_count()
        extra = ""
        if count and wanted > count:
            extra = self.tr("将使用全部 {0} 道匹配题。", count)
        topics = len(self.topic_box["values"]) - 1 if getattr(self, "topic_box", None) else 0
        if getattr(self, "config_summary", None):
            self.config_summary.configure(
                text=self.tr(
                    "{0} · {1} · {2} · {3} 个主题",
                    self.subject.get(),
                    self.topic.get(),
                    self.difficulty.get(),
                    max(topics, 0),
                )
                + (("  " + extra) if extra else "")
            )
        self._sync_start_button()

    def start_configured(self):
        try:
            count = int(self.count.get())
            subject = self.subject.get()
            topic = None if self.topic.get() == self.tr("全部") else self.topic.get()
            difficulty = (
                None if self.difficulty.get() == self.tr("全部") else self.difficulty.get()
            )
            questions = select_questions(self.questions, subject, topic, difficulty, count)
            self._last_filters = {
                "subject": subject,
                "topic": topic,
                "difficulty": difficulty,
                "count": count,
                "bank_kind": self._practice_bank_kind,
            }
            self.start_quiz(questions)
        except ValueError as exc:
            messagebox.showerror(
                self.tr("无法开始练习"),
                self.tr("请输入正整数题数并检查筛选条件。\n{0}", exc),
                parent=self.root,
            )

    def start_quiz(self, questions, review=False):
        if not self.check_session():
            return
        try:
            seconds = int(self.timer_seconds.get())
            if not 0 <= seconds <= 86400:
                raise ValueError(self.tr("限时必须为 0–86400 秒。"))
            self.progress.load()
            self.engine = QuizEngine(
                questions, self.progress, review, learning_plan=self.learning_plan
            )
        except ValueError as exc:
            messagebox.showerror(self.tr("无法开始练习"), self.tr(str(exc)), parent=self.root)
            return
        self._last_session = {
            "review": review,
            "ids": [question.id for question in questions],
        }
        if not review:
            # Keep filters from configure; subject-card starts only store subject.
            filters = dict(self._last_filters or {})
            subjects = {question.subject for question in questions}
            if len(subjects) == 1:
                filters.setdefault("subject", next(iter(subjects)))
            filters.setdefault("count", len(questions))
            self._last_filters = filters
        self.deadline = time.monotonic() + seconds if seconds else None
        self.show_question()
        self._tick_timer(self.engine)

    def _tick_timer(self, engine):
        if self.engine is not engine or engine.complete:
            self.timer_label.configure(text="")
            return
        if self.deadline is None:
            self.timer_label.configure(text="")
            return
        remaining = max(0, int(self.deadline - time.monotonic() + 0.999))
        self.timer_label.configure(text=self.tr("剩余 {0} 秒", remaining))
        if time.monotonic() >= self.deadline:
            if not self.check_session():
                return
            try:
                engine.finish_timeout()
            except ValueError as exc:
                self.deadline = None
                messagebox.showerror(self.tr("保存失败"), str(exc), parent=self.root)
                return
            self.motion.cancel()
            self.timer_label.configure(text="")
            self.results()
            return
        self.root.after(200, lambda: self._tick_timer(engine))

    def export_progress(self, kind, format):
        if not self.check_session():
            return
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension="." + format,
            filetypes=[(format.upper(), "*." + format)], initialfile=kind + "." + format)
        if not path:
            return
        try:
            from .exports import export_progress
            export_progress(Path(path), kind, format, self.progress.load(), self.by_id)
        except (ValueError, OSError, ImportError) as exc:
            messagebox.showerror(self.tr("导出失败"), str(exc), parent=self.root)
            return
        messagebox.showinfo(self.tr("导出完成"), path, parent=self.root)

    def export_buttons(self, kind):
        bar = ttk.Frame(self.body)
        bar.pack(fill="x", pady=6)
        for format in ("csv", "pdf"):
            ttk.Button(bar, text=self.tr("导出 {0}", format.upper()),
                command=lambda f=format: self.export_progress(kind, f)).pack(side="left", padx=4)

    def show_image(self, value, parent=None, fallback_subject=None):
        host = parent or self.body
        try:
            if value:
                path = image_path(self.project_root, value)
            elif fallback_subject:
                path = subject_image(self.project_root, fallback_subject)
            else:
                return
            if not path.is_file():
                raise OSError(self.tr("图片文件不存在"))
            photo = tk.PhotoImage(master=self.root, file=str(path))
            scale = max(1, (photo.width() + 479) // 480, (photo.height() + 219) // 220)
            if scale > 1:
                photo = photo.subsample(scale)
            self.images.append(photo)
            frame = ttk.Frame(host, style="App.TFrame" if host is self.body else "Card.TFrame")
            frame.pack(anchor="w", pady=5)
            ttk.Label(frame, image=photo).pack(anchor="w")
            if not value and fallback_subject:
                ttk.Label(frame, text=self.tr("学科示意图"), style="Muted.TLabel").pack(anchor="w")
        except (tk.TclError, OSError, ValueError) as exc:
            try:
                path = image_path(self.project_root, "assets/images/placeholder.png")
                if path.is_file():
                    photo = tk.PhotoImage(master=self.root, file=str(path))
                    self.images.append(photo)
                    ttk.Label(host, image=photo).pack(anchor="w", pady=5)
            except (tk.TclError, OSError, ValueError):
                pass
            ttk.Label(
                host,
                text=self.tr("图片无法显示：{0}\n{1}", value or self.tr("缺图"), exc),
                wraplength=640,
            ).pack(anchor="w", pady=6)

    def question_content(self, q, selectable=False, parent=None):
        host = parent or self.body
        on_body = host is self.body or host is getattr(self, "question_shell", None)
        ttk.Label(
            host,
            text=f"{q.subject} / {q.topic} / {q.difficulty}  ·  {q.id}",
            style="Muted.TLabel" if on_body else "Card.TLabel",
        ).pack(fill="x")
        ttk.Label(
            host,
            text=q.question,
            wraplength=CONTENT_MAX - 48,
            justify="left",
            style="Question.TLabel" if on_body else "Card.TLabel",
        ).pack(fill="x", pady=(4, 10))
        self.show_image(q.question_image, host, fallback_subject=q.subject if selectable else None)
        self.option_buttons = []
        self.option_cards = []
        self.option_status = {}
        box = ttk.LabelFrame(host, text=self.tr("选项"), padding=12)
        box.pack(fill="x", pady=8)
        for index, option in enumerate(q.options):
            text = f"{option_label(index)}: {option}"
            if selectable:
                card = tk.Frame(
                    box,
                    bg=SURFACE,
                    highlightthickness=2,
                    highlightbackground=BORDER,
                    highlightcolor=PRIMARY,
                )
                card.pack(anchor="w", pady=6, fill="x")
                inner = tk.Frame(card, bg=SURFACE)
                inner.pack(fill="x", padx=8, pady=8)
                mark = tk.Label(
                    inner,
                    text=option_label(index),
                    bg=SURFACE,
                    fg=PRIMARY,
                    font=(FONT, 12, "bold"),
                    width=3,
                )
                mark.pack(side="left")
                widget = ttk.Radiobutton(inner, text=text, variable=self.answer, value=option)
                widget.pack(side="left", fill="x", expand=True, padx=8)
                status = tk.Label(inner, text="", bg=SURFACE, fg=MUTED, font=TYPE_HINT, width=6)
                status.pack(side="right")
                self.option_status[option] = status
                self.option_buttons.append(widget)
                self.option_cards.append((card, option))
                pick = lambda value=option: self._pick_option(value)
                bind_whole(card, pick)
                card.bind("<Enter>", lambda _e, frame=card: self._hover_option(frame, True))
                card.bind("<Leave>", lambda _e, frame=card: self._hover_option(frame, False))
                widget.bind("<Enter>", lambda _e, frame=card: self._hover_option(frame, True))
                widget.bind("<Leave>", lambda _e, frame=card: self._hover_option(frame, False))
            else:
                ttk.Label(box, text=text, wraplength=600, style="Card.TLabel").pack(anchor="w", pady=2)
            if q.option_images:
                self.show_image(q.option_images[index], box if not selectable else card)

    def _pick_option(self, option):
        if getattr(self, "_choices_locked", False):
            return
        self.answer.set(option)

    def _fill_option(self, frame, background, border):
        frame.configure(bg=background, highlightbackground=border)
        stack = list(frame.winfo_children())
        while stack:
            child = stack.pop()
            stack.extend(child.winfo_children())
            try:
                child.configure(bg=background)
            except tk.TclError:
                pass

    def _hover_option(self, frame, entering):
        if getattr(self, "_choices_locked", False) or not frame.winfo_exists():
            return
        selected = next((option for card, option in self.option_cards if card is frame), None)
        if selected and self.answer.get() == selected:
            self._fill_option(frame, SELECTED_BG, PRIMARY)
            return
        self._fill_option(frame, HOVER if entering else SURFACE, PRIMARY if entering else BORDER)

    def _paint_options(self, submitted=False, correct=False):
        chosen = self.answer.get()
        answer = self.engine.current.answer if self.engine else ""
        for frame, option in getattr(self, "option_cards", []):
            if not frame.winfo_exists():
                continue
            status = getattr(self, "option_status", {}).get(option)
            note = ""
            if submitted and option == answer:
                color = SUCCESS_BG
                border = SUCCESS_FG
                note = self.tr("正确")
            elif submitted and option == chosen and option != answer:
                color = ERROR_BG
                border = ERROR
                note = self.tr("你的选择")
            elif option == chosen:
                color = SELECTED_BG
                border = PRIMARY
                note = self.tr("已选")
            else:
                color = SURFACE
                border = BORDER
            self._fill_option(frame, color, border)
            if status is not None and status.winfo_exists():
                status.configure(text=note, bg=color, fg=SUCCESS_FG if note == self.tr("正确") else TEXT)

    def show_question(self):
        engine = self.engine
        mode = self.tr("错题复习") if engine.review else self.tr("练习")
        total = len(engine.questions)
        self._choices_locked = False
        self._submit_busy = False
        self.clear(self.tr("{0} · 第 {1} / {2} 题", mode, engine.index + 1, total))
        ttk.Label(
            self.body,
            text=self.tr("进度：第 {0} / {1} 题", engine.index + 1, total),
            style="Muted.TLabel",
        ).pack(fill="x")
        path = tk.Canvas(self.body, height=28, bg=BG, highlightthickness=0, bd=0)
        path.pack(fill="x", pady=(2, 4))
        path.bind(
            "<Configure>",
            lambda _e, canvas=path, n=total, i=engine.index + 1: self.motion.paint_path(canvas, n, i),
        )
        bar = ttk.Progressbar(self.body, maximum=total, value=engine.index)
        bar.pack(fill="x", pady=(4, 16))
        self.motion.grow_progress(bar, engine.index + 1)
        self.answer = tk.StringVar(value="")
        self.question_shell = ttk.Frame(self.body, style="App.TFrame")
        self.question_shell.pack(fill="x")
        self.question_content(engine.current, selectable=True, parent=self.question_shell)
        self.answer.trace_add("write", lambda *_: self._on_answer_changed())
        self.submit_button = self.button(self.tr("检查答案"), self.submit, "Accent.TButton")
        self.submit_button.state(["disabled"])
        self.feedback = self.label("")
        next_label = self.tr("查看结果") if engine.index == total - 1 else self.tr("继续")
        self.next_button = self.button(next_label, self.advance)
        self.next_button.state(["disabled"])
        ttk.Button(
            self.body, text=self.tr("结束练习并返回"), command=self.leave_quiz, style="Tool.TButton"
        ).pack(anchor="w", pady=4)
        ttk.Label(
            self.body,
            text=self.tr("快捷键：1–4 或 A–D 选择答案，Enter 检查或继续"),
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(8, 0))
        self._bind_quiz_keys()
        self.motion.fade_in(self.question_shell, duration=160)

    def _bind_quiz_keys(self):
        if self._quiz_keys_bound:
            return
        self._quiz_key_id = self.root.bind("<Key>", self._on_quiz_key, add="+")
        self._quiz_keys_bound = True

    def _unbind_quiz_keys(self):
        if not self._quiz_keys_bound:
            return
        try:
            self.root.unbind("<Key>", self._quiz_key_id)
        except (tk.TclError, AttributeError):
            pass
        self._quiz_keys_bound = False
        self._quiz_key_id = None

    def _on_quiz_key(self, event):
        if not self.engine or not getattr(self, "answer", None):
            return
        focused = self.root.focus_get()
        if focused is not None:
            cls = focused.winfo_class()
            if cls in {"Entry", "TEntry", "TCombobox", "Text"}:
                return
        key = event.keysym
        options = self.engine.current.options
        index = None
        if key in {"1", "2", "3", "4"}:
            index = int(key) - 1
        elif key.lower() in {"a", "b", "c", "d"}:
            index = ord(key.lower()) - ord("a")
        if index is not None and not getattr(self, "_choices_locked", False):
            if 0 <= index < len(options):
                self._pick_option(options[index])
            return "break"
        if key in {"Return", "KP_Enter"}:
            if getattr(self, "_choices_locked", False):
                if self.next_button.instate(["!disabled"]):
                    self.advance()
            elif self.answer.get() and not getattr(self, "_submit_busy", False):
                self.submit()
            return "break"

    def _on_answer_changed(self, *_):
        self._paint_options()
        self._sync_check_button()

    def _sync_check_button(self):
        button = getattr(self, "submit_button", None)
        if button is None or not button.winfo_exists() or getattr(self, "_choices_locked", False):
            return
        if self.answer.get():
            button.state(["!disabled"])
            button.configure(text=self.tr("检查答案"))
        else:
            button.state(["disabled"])
            button.configure(text=self.tr("请先选择答案"))

    def submit(self):
        if self.engine and getattr(self, "deadline", None) and time.monotonic() >= self.deadline:
            self._tick_timer(self.engine)
            return
        if not self.check_session():
            return
        if getattr(self, "_submit_busy", False) or getattr(self, "_choices_locked", False):
            return
        try:
            correct = self.engine.submit(self.answer.get())
        except ValueError as exc:
            messagebox.showerror(self.tr("提交失败"), self.tr(str(exc)), parent=self.root)
            return
        if self.engine.activity_warning:
            messagebox.showwarning(
                self.tr("学习计划未更新"),
                self.tr(
                    "答案和成绩已保存，但每日进度保存失败：{0}",
                    self.engine.activity_warning,
                ),
                parent=self.root,
            )
        self._submit_busy = True
        self._choices_locked = True
        self.submit_button.state(["disabled"])
        for widget in self.option_buttons:
            widget.state(["disabled"])
        self._paint_options(submitted=True, correct=correct)
        q = self.engine.current
        headline = self.tr("回答正确") if correct else self.tr("再想一想")
        detail = (
            self.tr("回答正确，继续保持。") if correct else self.tr("回答错误，已记入错题本。")
        )
        self.feedback.configure(
            style="Success.TLabel" if correct else "Error.TLabel",
            text=self.tr("{0}\n正确答案：{1}\n解析：{2}", f"{headline}\n{detail}", q.answer, q.explanation),
        )
        next_label = (
            self.tr("查看结果")
            if self.engine.index == len(self.engine.questions) - 1
            else self.tr("继续")
        )

        def finish():
            if not self.submit_button.winfo_exists():
                return
            # Keep submit disabled so a second invoke cannot rescore or skip ahead.
            self.submit_button.configure(text=next_label)
            self.submit_button.state(["disabled"])
            self.next_button.state(["!disabled"])
            self._submit_busy = False

        self.motion.submit_feedback(self.submit_button, correct, finish)

    def advance(self):
        if self.engine.complete:
            self.motion.circle_transition(self.outer, self.results)
            return

        def go():
            self.engine.next_question()
            self.show_question()

        if self.motion.active():
            self.motion.fade_in(self.outer, duration=120)
            self.motion.schedule(130, go)
        else:
            go()

    def results(self):
        result = self.engine.result()
        self.timer_label.configure(text="")
        self.clear(self.tr("练习完成"), show_heading=True)
        if getattr(self.engine, "timed_out", False):
            self.label(self.tr("本轮已超时，未答 {0} 题计为未得分；未答题不会加入错题本。", self.engine.unanswered))
        stats = ttk.Frame(self.body, style="App.TFrame")
        stats.pack(fill="x", pady=(4, 12))
        for title, value in (
            (self.tr("正确率"), f"{result['accuracy']:.0f}%"),
            (self.tr("答对题数"), f"{result['correct']} / {result['total']}"),
            (self.tr("总分"), f"{result['score']} / {result['max_score']}"),
        ):
            cell = card_frame(stats, pad=14)
            cell.pack(side="left", fill="x", expand=True, padx=(0, 10))
            tk.Label(cell, text=title, bg=SURFACE, fg=MUTED, font=TYPE_HINT).pack(anchor="w")
            tk.Label(cell, text=value, bg=SURFACE, fg=TEXT, font=(FONT, 20, "bold")).pack(anchor="w", pady=(4, 0))
        accuracy = result["accuracy"]
        if accuracy >= 80:
            advice = self.tr("本轮正确率较高，可以尝试更多题目或更高难度。")
        elif accuracy >= 60:
            advice = self.tr("本轮表现稳定，错题本里的题目值得再看一遍。")
        else:
            advice = self.tr("根据本轮正确率，建议先复习错题再开始下一组练习。")
        self.label(advice, "Muted.TLabel")
        self.label(self.tr("成绩已保存。每题 1 分，错题复习答对后从错题本移除。"), "Muted.TLabel")
        subjects = ", ".join(sorted({q.subject for q in self.engine.questions}))
        self.label(self.tr("本轮学科：{0}", subjects), "Muted.TLabel")
        self.engine = None
        actions = ttk.Frame(self.body, style="App.TFrame")
        actions.pack(fill="x", pady=12)
        ttk.Button(actions, text=self.tr("再练一次"), command=self.retry_quiz, style="Accent.TButton").pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(actions, text=self.tr("查看错题本"), command=self.notebook, style="Accent.TButton").pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(actions, text=self.tr("返回首页"), command=self.home, style="Tool.TButton").pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(actions, text=self.tr("查看学习历史"), command=self.history, style="Tool.TButton").pack(
            side="left"
        )

    def retry_quiz(self):
        if not self.check_session():
            return
        session = self._last_session or {}
        if session.get("review"):
            questions = [self.by_id[qid] for qid in session.get("ids", []) if qid in self.by_id]
            if not questions:
                messagebox.showinfo(
                    self.tr("无法开始练习"),
                    self.tr("没有可复习的错题，请返回首页重新选择。"),
                    parent=self.root,
                )
                self.home()
                return
            self.start_quiz(questions, True)
            return
        filters = self._last_filters or {}
        try:
            bank_kind = filters.get("bank_kind", "public")
            self.load_bank()
            self.questions = (
                self.personal_questions if bank_kind == "personal" else self.public_questions
            )
            count = int(filters.get("count") or len(session.get("ids") or []) or 5)
            questions = select_questions(
                self.questions,
                filters.get("subject"),
                filters.get("topic"),
                filters.get("difficulty"),
                count,
            )
            self.start_quiz(questions)
        except ValueError as exc:
            messagebox.showerror(
                self.tr("无法开始练习"),
                self.tr("请输入正整数题数并检查筛选条件。\n{0}", exc),
                parent=self.root,
            )
            self.configure(filters.get("subject"), filters.get("bank_kind", "public"))

    def leave_quiz(self):
        if self.can_leave():
            self.home()

    def can_leave(self):
        if self.users_page and not self.users_page.can_leave():
            return False
        if self.editor and not self.editor.can_leave():
            return False
        if self.engine and not self.engine.complete:
            return messagebox.askyesno(
                self.tr("结束练习？"),
                self.tr("本次练习尚未完成，退出后不会计入成绩历史。已经提交且答错的题目会保留在错题本，供以后复习。确定退出吗？"),
                parent=self.root,
            )
        return True

    def close(self):
        if self.can_leave():
            self.motion.cancel()
            self.root.destroy()

    def notebook(self):
        if not self.check_session():
            return
        self._nav_key = "notebook"
        self.clear(self.tr("错题本"), show_heading=True)
        self.export_buttons("wrong")
        try:
            wrong = self.progress.load()["wrong"]
        except DataError as exc:
            empty = card_frame(self.body, pad=16)
            empty.pack(fill="x")
            tk.Label(empty, text=self.tr("学习数据加载失败"), bg=SURFACE, fg=TEXT, font=(FONT, 13, "bold")).pack(
                anchor="w"
            )
            tk.Label(empty, text=self.tr(str(exc)), bg=SURFACE, fg=MUTED, wraplength=560, justify="left").pack(
                anchor="w", pady=8
            )
            ttk.Button(empty, text=self.tr("重新加载题库"), command=self.notebook, style="Accent.TButton").pack(
                anchor="w"
            )
            return
        if not wrong:
            empty = card_frame(self.body, pad=16)
            empty.pack(fill="x")
            tk.Label(empty, text=self.tr("还没有错题。开始一次练习吧！"), bg=SURFACE, fg=TEXT, font=(FONT, 13, "bold")).pack(
                anchor="w"
            )
            tk.Label(
                empty,
                text=self.tr("完成第一次练习后，学习动态会显示在这里。"),
                bg=SURFACE,
                fg=MUTED,
                wraplength=560,
                justify="left",
            ).pack(anchor="w", pady=8)
            ttk.Button(empty, text=self.tr("开始第一次练习"), command=self.configure, style="Accent.TButton").pack(
                anchor="w"
            )
            return
        available = [self.by_id[key] for key in wrong if key in self.by_id]
        self.label(self.tr("复习规则：复习答对后移除；普通练习答对不会移除。重复答错累计次数。"), "Muted.TLabel")
        actions = ttk.Frame(self.body, style="App.TFrame")
        actions.pack(fill="x", pady=(0, 8))
        if available:
            ttk.Button(
                actions,
                text=self.tr("复习全部可用错题（{0} 道）", len(available)),
                command=lambda: self.start_quiz(available, True),
                style="Accent.TButton",
            ).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text=self.tr("返回首页"), command=self.home, style="Tool.TButton").pack(side="left")
        for key, record in wrong.items():
            panel = card_frame(self.body, pad=14)
            panel.pack(fill="x", pady=(0, 10))
            if key not in self.by_id:
                tk.Label(
                    panel,
                    text=self.tr(
                        "{0}：题目已删除或无效，暂不能复习；记录保留，恢复题目后可继续。", key
                    ),
                    bg=SURFACE,
                    fg=MUTED,
                    wraplength=560,
                    justify="left",
                ).pack(anchor="w")
                continue
            q = self.by_id[key]
            tk.Label(panel, text=q.subject, bg=SURFACE, fg=PRIMARY, font=TYPE_HINT).pack(anchor="w")
            self.question_content(q, parent=panel)
            tk.Label(
                panel,
                text=self.tr("你选择：{0}", record["last_answer"]),
                bg=SURFACE,
                fg=MUTED,
                font=TYPE_HINT,
            ).pack(anchor="w", pady=(6, 0))
            tk.Label(
                panel,
                text=self.tr("正确答案：{0}", q.answer),
                bg=SURFACE,
                fg=TEXT,
                font=TYPE_HINT,
            ).pack(anchor="w")
            tk.Label(
                panel,
                text=self.tr("错误次数：{0}", record["count"]),
                bg=SURFACE,
                fg=MUTED,
                font=TYPE_HINT,
            ).pack(anchor="w", pady=(0, 8))
            explain = tk.Label(
                panel,
                text=self.tr("解析：{0}", q.explanation),
                bg=SURFACE,
                fg=MUTED,
                font=TYPE_HINT,
                wraplength=560,
                justify="left",
            )

            def toggle_explain(label=explain):
                if label.winfo_ismapped():
                    label.pack_forget()
                else:
                    label.pack(anchor="w", pady=(0, 8))

            row = tk.Frame(panel, bg=SURFACE)
            row.pack(anchor="w")
            self._text_button(row, self.tr("查看解析"), toggle_explain, bg=SURFACE).pack(side="left", padx=(0, 12))
            ttk.Button(
                row,
                text=self.tr("重新练习"),
                style="Accent.TButton",
                command=lambda question=q: self.start_quiz([question], True),
            ).pack(side="left")

    def history(self):
        if not self.check_session():
            return
        self._nav_key = "history"
        self.clear(self.tr("学习统计与历史"))
        self.button(self.tr("返回首页"), self.home)
        self.export_buttons("history")
        try:
            history = self.progress.load()["history"]
        except DataError as exc:
            self.label(self.tr(str(exc)))
            return
        total = sum(record["total"] for record in history)
        correct = sum(record["correct"] for record in history)
        accuracy = correct / total * 100 if total else 0
        summary = ttk.LabelFrame(self.body, text=self.tr("学习统计与历史"), padding=16)
        summary.pack(fill="x", pady=8)
        ttk.Label(
            summary,
            style="Card.TLabel",
            wraplength=640,
            text=self.tr(
                "完成 {0} 次练习（含复习） · 已答 {1} 题 · 正确 {2} 题 · 综合正确率 {3}%",
                len(history),
                total,
                correct,
                f"{accuracy:.2f}",
            ),
        ).pack(anchor="w")
        if not history:
            empty = card_frame(self.body, pad=16)
            empty.pack(fill="x", pady=(0, 8))
            tk.Label(empty, text=self.tr("还没有学习记录"), bg=SURFACE, fg=TEXT, font=(FONT, 13, "bold")).pack(
                anchor="w"
            )
            tk.Label(
                empty,
                text=self.tr("完成第一次练习后，学习动态会显示在这里。"),
                bg=SURFACE,
                fg=MUTED,
                wraplength=560,
                justify="left",
            ).pack(anchor="w", pady=8)
            ttk.Button(empty, text=self.tr("开始第一次练习"), command=self.configure, style="Accent.TButton").pack(
                anchor="w"
            )
        for record in reversed(history):
            card = ttk.LabelFrame(self.body, text=record["date"], padding=12)
            card.pack(fill="x", pady=8)
            ttk.Label(
                card,
                style="Card.TLabel",
                wraplength=640,
                text=self.tr(
                    "{0} · {1} · {2}\n题数 {3} | 正确 {4} | 错误 {5} | 正确率 {6}% | 得分 {7}/{8}",
                    record["date"],
                    record["subject"],
                    record["mode"],
                    record["total"],
                    record["correct"],
                    record["incorrect"],
                    f"{record['accuracy']:.2f}",
                    record["score"],
                    record["max_score"],
                ),
            ).pack(anchor="w")


def main():
    root = tk.Tk()
    Application(root)
    root.mainloop()
