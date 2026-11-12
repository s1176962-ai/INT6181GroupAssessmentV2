"""One Tkinter interface for setup, quizzes, notebook and learning history."""

import gc
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .ai_assistant import AiAssistant, AiSettings, question_message
from .auth import AuthService
from .display import DisplaySettings, window_size
from .editor_ui import EditorPage
from .i18n import Translator
from .importing import QuestionImportService
from .login_preferences import LoginPreferences
from .maintenance import QuestionEditor
from .models import option_label
from .motion import Motion
from .repositories import (
    LearningPlanRepository,
    PersonalQuestionRepository,
    ProgressRepository,
    QuestionRepository,
)
from .services import QuizEngine, image_path, select_questions, subject_image
from .storage import DataError
from . import modern
from . import ui_tokens as T
from .ui_tokens import (
    CARD_WIDTH,
    CONTENT_MAX,
    FONT,
    HIT,
    PAGE_PAD,
    ROW_H,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
    SPACE_6,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XL,
    SPACE_XS,
    SPLIT_WIDE,
    TYPE_BODY,
    TYPE_BUTTON,
    TYPE_CARD,
    TYPE_FOOT,
    TYPE_HINT,
    TYPE_LABEL,
    TYPE_MARK,
    TYPE_TITLE,
    TYPE_TOOL,
)
from .user_ui import UserPage
from .widgets import bind_whole, card_frame

ROOT = Path(__file__).resolve().parent.parent

# Difficulty data values stay unchanged (easy/medium/hard). The Chinese strings
# are i18n *keys*: tr() renders "All / Easy / Medium / Hard" in English mode, so
# the filter never leaks Chinese into an English screen.
DIFFICULTY_LABELS = {"easy": "简单", "medium": "中等", "hard": "困难"}

# Question art is rasterised at 1440x810 (3x the 480x270 design grid) so it can
# still be shown large on a high-DPI screen: Tk's PhotoImage can subsample only,
# so the biggest usable step is the source resolution itself.
ART_MAX_W = 720
ART_MAX_H = 420


def art_factor(width, height, limit_w, limit_h):
    """Smallest integer subsample that fits ``width``x``height`` into the box."""
    factor = 1
    while factor < 16 and (width / factor > limit_w or height / factor > limit_h):
        factor += 1
    return factor


class AssistantReply(tk.Text):
    """Read-only scrolling reply with the same update interface as a label."""

    def __init__(self, parent, **kwargs):
        text = kwargs.pop("text", "")
        self._on_text = kwargs.pop("on_text", None)
        super().__init__(parent, **kwargs)
        self.configure(text=text)

    def configure(self, cnf=None, **kwargs):
        text = kwargs.pop("text", None)
        result = super().configure(cnf, **kwargs)
        if text is not None:
            super().configure(state="normal")
            self.delete("1.0", "end")
            self.insert("1.0", text)
            self.yview_moveto(0)
            super().configure(state="disabled")
            if self._on_text is not None:
                self._on_text(text)
        return result


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
        T.set_theme(self.tr.theme)
        self.login_preferences = LoginPreferences(self.guest_progress_path.parent)
        self.ai_settings = AiSettings(self.guest_progress_path.parent)
        self.ai_assistant = AiAssistant(self.ai_settings)
        self._ai_asked = set()
        self._ai_pending = set()
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
        root.configure(bg=T.BG)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Destroy>", self._on_root_destroy, add="+")
        self._style(root)
        self.chrome = ttk.Frame(root, style="Shell.TFrame", padding=(T.px(24), 0))
        self.chrome.configure(height=T.px(T.TOPBAR_H))
        self.chrome.pack_propagate(False)  # fixed 54px top bar
        self.chrome_back = modern.CircleIconButton(
            self.chrome, glyph="←", command=self.home,
        )
        self.chrome_title = ttk.Label(self.chrome, text=self.tr("首页"), style="Shell.TLabel")
        self.chrome_title.pack(side="left", padx=(T.px(T.SPACE_2), 0))
        self.timer_label = ttk.Label(self.chrome, text="", style="Muted.TLabel")
        self.timer_label.pack(side="left", padx=T.px(T.SPACE_3))
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
        self.canvas = tk.Canvas(outer, highlightthickness=0, bg=T.BG, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = ttk.Frame(
            self.canvas,
            style="App.TFrame",
            padding=(
                (T.px(12), T.px(10)) if self.display["compact"]
                else (T.px(24), T.px(20))
            ),
        )
        self.window = self.canvas.create_window((0, 0), window=self.body, anchor="n")
        self.body.bind("<Configure>", self._on_body_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        root.bind("<MouseWheel>", self._page_wheel)
        root.bind_class("TCombobox", "<MouseWheel>", self._control_wheel)
        root.bind_class("TSpinbox", "<MouseWheel>", self._control_wheel)
        root.bind_class("TCombobox", "<Button-4>", self._control_wheel)
        root.bind_class("TCombobox", "<Button-5>", self._control_wheel)
        root.bind(
            "<Configure>", lambda e: self._layout_login() if e.widget is root else None, add="+"
        )
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

    def theme_labels(self):
        """Return (current label, other label, other theme key)."""
        dark = self.tr("深色模式")
        light = self.tr("浅色模式")
        if T.theme_name() == "dark":
            return dark, light, "light"
        return light, dark, "dark"

    def _theme_toggle_label(self):
        _current, other, _key = self.theme_labels()
        return f"→  {other}"

    def _login_theme_label(self):
        """Short, symbol-led label for the pre-sign-in theme switch."""
        _current, other, _key = self.theme_labels()
        return f"◐  {other}"

    def apply_theme(self, name):
        """Rebind tokens, refresh ttk styles, then rebuild the current screen."""
        if name not in T.THEMES or name == T.theme_name():
            return
        try:
            self.tr.set_theme(name)
        except (ValueError, DataError) as exc:
            messagebox.showerror(self.tr("保存失败"), self.tr(str(exc)), parent=self.root)
            return
        T.set_theme(name)
        self._style(self.root)
        self.root.configure(bg=T.BG)
        self.canvas.configure(bg=T.BG)
        if getattr(self, "chrome_back", None) is not None:
            self.chrome_back.refresh()
        if getattr(self, "chrome", None) is not None:
            self.chrome.configure(style="Shell.TFrame")
        nav = getattr(self, "nav", None)
        if nav is not None and nav.winfo_exists():
            nav.destroy()
            self.nav = None
        self._rebuild_screen()
        self.motion.fade_in(self.outer)

    def _rebuild_screen(self):
        """Pages are cheap to recreate; an in-flight quiz keeps its engine."""
        split = getattr(self, "login_split", None)
        if split is not None and split.winfo_exists():
            self.login_page(getattr(self, "_login_registering", False))
            return
        engine = getattr(self, "engine", None)
        if engine is not None:
            self.results() if engine.complete else self.show_question()
            return
        pages = {
            "home": self.home,
            "practice": self.configure,
            "notebook": self.notebook,
            "history": self.history,
            "settings": self.settings,
            "questions": self.manage_questions,
            "users": self.manage_users,
            "personal": self.personal_bank_page,
        }
        action = pages.get(getattr(self, "_nav_key", None))
        if action is None:
            action = self.home if self.signed_in else self.login_page
        action()

    def _style(self, root):
        style = ttk.Style(root)
        style.theme_use("clam")
        style.layout(
            "CardOption.TRadiobutton",
            [
                (
                    "Radiobutton.padding",
                    {"sticky": "nswe", "children": [("Radiobutton.label", {"sticky": "nswe"})]},
                )
            ],
        )
        style.configure(".", font=(FONT, 11), background=T.BG, foreground=T.TEXT)
        style.configure("App.TFrame", background=T.BG)
        style.configure("Card.TFrame", background=T.SURFACE)
        style.configure("Shell.TFrame", background=T.BG)
        style.configure("TLabel", background=T.BG, foreground=T.TEXT, font=(FONT, 11))
        style.configure("Card.TLabel", background=T.SURFACE, foreground=T.TEXT, font=(FONT, 11))
        style.configure("Shell.TLabel", background=T.BG, foreground=T.TEXT, font=(FONT, 11, "bold"))
        style.configure("Mark.TLabel", background=T.BG, foreground=T.ACCENT, font=(FONT, 18, "bold"))
        style.configure("Brand.TFrame", background=T.SKY)
        style.configure("Brand.TLabel", background=T.SKY, foreground=T.MUTED, font=TYPE_HINT)
        style.configure("BrandTitle.TLabel", background=T.SKY, foreground=T.TEXT, font=T.TYPE_HERO)
        style.configure("BrandMark.TLabel", background=T.SKY, foreground=T.MUTED, font=T.TYPE_KICKER)
        style.configure("Chip.TLabel", background=T.HOVER, foreground=T.TEXT, font=TYPE_HINT)
        style.configure("Demo.TLabel", background=T.SURFACE, foreground=T.MUTED, font=TYPE_HINT)
        style.configure("Stat.TLabel", background=T.SURFACE, foreground=T.TEXT, font=(FONT, 16, "bold"))
        style.configure("StatHint.TLabel", background=T.SURFACE, foreground=T.MUTED, font=(FONT, 8))
        style.configure("Foot.TLabel", background=T.BG, foreground=T.MUTED, font=(FONT, 8))
        style.configure(
            "Tool.TButton",
            padding=(12, 7),
            font=(FONT, 10),
            background=T.SURFACE,
            foreground=T.TEXT,
            bordercolor=T.BORDER,
            lightcolor=T.BORDER,
            darkcolor=T.BORDER,
            relief="flat",
        )
        style.map("Tool.TButton", background=[("active", T.HOVER), ("pressed", T.HOVER)])
        style.configure(
            "Tool.TMenubutton",
            padding=(12, 7),
            font=(FONT, 10),
            background=T.SURFACE,
            foreground=T.TEXT,
            bordercolor=T.BORDER,
            relief="flat",
            arrowcolor=T.TEXT,
        )
        style.map("Tool.TMenubutton", background=[("active", T.HOVER)])
        style.configure("Hint.TLabel", background=T.SURFACE, foreground=T.MUTED, font=(FONT, 10))
        style.configure("Title.TLabel", font=(FONT, 18), background=T.BG, foreground=T.TEXT)
        style.configure("Kpi.TLabel", font=(FONT, 28), background=T.BG, foreground=T.TEXT)
        style.configure("Muted.TLabel", background=T.BG, foreground=T.MUTED, font=(FONT, 10))
        style.configure("Question.TLabel", background=T.BG, foreground=T.TEXT, font=(FONT, 14))
        style.configure(
            "Warning.TLabel",
            background=T.WARNING_BG,
            foreground=T.WARNING,
            font=(FONT, 10),
            padding=8,
        )
        style.configure(
            "Info.TLabel",
            background=T.INFO_BG,
            foreground=T.TEXT,
            font=(FONT, 10),
            padding=8,
        )
        style.configure(
            "Success.TLabel",
            background=T.SUCCESS_BG,
            foreground=T.SUCCESS_FG,
            font=(FONT, 11),
            padding=8,
        )
        style.configure(
            "Error.TLabel",
            background=T.ERROR_BG,
            foreground=T.ERROR,
            font=(FONT, 11),
            padding=8,
        )
        style.configure(
            "TButton",
            padding=(T.px(12), T.px(8)),
            font=T.TYPE_BODY,
            background=T.SURFACE,
            foreground=T.TEXT,
            bordercolor=T.BORDER_CONTROL,
            lightcolor=T.BORDER_CONTROL,
            darkcolor=T.BORDER_CONTROL,
            relief="flat",
            focuscolor=T.BG,
        )
        style.map(
            "TButton",
            background=[
                ("focus", T.PRIMARY_SOFT),
                ("active", T.HOVER),
                ("pressed", T.PRESSED),
                ("disabled", T.DISABLED_FILL),
            ],
            foreground=[("disabled", T.DISABLED_INK), ("focus", T.PRIMARY)],
        )
        style.configure("Nav.TFrame", background=T.BG)
        style.configure("Nav.TLabel", background=T.BG, foreground=T.MUTED, font=(FONT, 10))
        style.configure(
            "Accent.TButton",
            padding=(T.px(12), T.px(8)),
            font=T.TYPE_BUTTON,
            background=T.BUTTON_FILL,
            foreground=T.BUTTON_INK,
            bordercolor=T.BUTTON_FILL,
            lightcolor=T.BUTTON_FILL,
            darkcolor=T.BUTTON_FILL,
            relief="flat",
            focuscolor=T.BG,
        )
        style.map(
            "Accent.TButton",
            background=[
                ("focus", T.PRIMARY_HOVER),
                ("active", T.PRIMARY_HOVER),
                ("pressed", T.PRIMARY_ACTIVE),
                ("disabled", T.PRIMARY_DISABLED),
            ],
            foreground=[("disabled", T.DISABLED_INK), ("!disabled", T.ON_PRIMARY)],
        )
        style.configure(
            "Link.TButton",
            padding=(0, 2),
            font=(FONT, 10),
            background=T.SURFACE,
            foreground=T.ACCENT,
            bordercolor=T.SURFACE,
            relief="flat",
        )
        style.map(
            "Link.TButton",
            background=[
                ("focus", T.PRIMARY_SOFT),
                ("active", T.SURFACE),
                ("pressed", T.PRESSED),
                ("disabled", T.DISABLED_FILL),
            ],
            foreground=[
                ("disabled", T.DISABLED_INK),
                ("focus", T.PRIMARY),
                ("active", T.COLOR_PRIMARY_DARK),
            ],
        )
        style.configure(
            "Ghost.TButton",
            padding=(8, 4),
            font=(FONT, 10),
            background=T.BG,
            foreground=T.MUTED,
            bordercolor=T.BG,
            relief="flat",
        )
        style.map(
            "Ghost.TButton",
            background=[
                ("focus", T.PRIMARY_SOFT),
                ("active", T.HOVER),
                ("pressed", T.PRESSED),
                ("disabled", T.DISABLED_FILL),
            ],
            foreground=[
                ("disabled", T.DISABLED_INK),
                ("focus", T.PRIMARY),
                ("active", T.TEXT),
            ],
        )
        style.configure(
            "Icon.TButton",
            padding=(2, 2),
            font=(FONT, 9),
            background=T.HOVER,
            foreground=T.MUTED,
            bordercolor=T.HOVER,
            relief="flat",
        )
        style.map(
            "Icon.TButton",
            background=[
                ("focus", T.PRIMARY_SOFT),
                ("active", T.SKY),
                ("pressed", T.PRESSED),
                ("disabled", T.DISABLED_FILL),
            ],
            foreground=[
                ("disabled", T.DISABLED_INK),
                ("focus", T.PRIMARY),
                ("active", T.TEXT),
            ],
        )
        style.configure(
            "TEntry",
            padding=T.px(8),
            fieldbackground=T.SURFACE,
            foreground=T.TEXT,
            insertcolor=T.TEXT,
            bordercolor=T.BORDER_CONTROL,
            lightcolor=T.SURFACE,
            darkcolor=T.SURFACE,
            relief="flat",
            focuscolor=T.BG,
        )
        style.map(
            "TEntry",
            bordercolor=[("focus", T.PRIMARY), ("hover", T.BORDER_CONTROL)],
            lightcolor=[("focus", T.PRIMARY)],
            darkcolor=[("focus", T.PRIMARY)],
        )
        style.configure(
            "Error.TEntry",
            padding=8,
            fieldbackground=T.ERROR_BG,
            bordercolor=T.ERROR,
            lightcolor=T.ERROR,
            darkcolor=T.ERROR,
        )
        style.configure(
            "TRadiobutton", background=T.SURFACE, foreground=T.TEXT, font=(FONT, 11), padding=6
        )
        style.map(
            "TRadiobutton",
            background=[
                ("disabled", T.SURFACE),
                ("focus", T.PRIMARY_SOFT),
                ("active", T.HOVER),
                ("pressed", T.PRESSED),
            ],
            foreground=[("disabled", T.DISABLED_INK), ("focus", T.PRIMARY)],
        )
        style.configure(
            "TLabelframe",
            background=T.SURFACE,
            bordercolor=T.BORDER_LIGHT,
            lightcolor=T.BORDER_LIGHT,
            darkcolor=T.BORDER_LIGHT,
            relief="flat",
        )
        style.configure(
            "TLabelframe.Label",
            background=T.SURFACE,
            foreground=T.TEXT,
            font=(FONT, 11),
        )
        style.configure(
            "TCombobox",
            padding=T.px(8),
            fieldbackground=T.SURFACE,
            background=T.SURFACE,
            bordercolor=T.BORDER_CONTROL,
            arrowcolor=T.TEXT_SECONDARY,
            arrowsize=T.px(12),
            relief="flat",
            focuscolor=T.BG,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", T.SURFACE)],
            bordercolor=[("focus", T.PRIMARY)],
            selectbackground=[("focus", T.SELECTED_BG)],
            selectforeground=[("focus", T.TEXT)],
        )
        style.configure(
            "TCheckbutton",
            background=T.BG,
            foreground=T.TEXT,
            font=(FONT, 11),
            padding=4,
        )
        style.map(
            "TCheckbutton",
            background=[
                ("disabled", T.BG),
                ("focus", T.PRIMARY_SOFT),
                ("active", T.HOVER),
                ("pressed", T.PRESSED),
            ],
            foreground=[("disabled", T.DISABLED_INK), ("focus", T.PRIMARY)],
        )
        # Checkbuttons that sit on a SURFACE card need a matching face, otherwise
        # the default page-coloured background shows through as a dark rectangle.
        style.configure(
            "Card.TCheckbutton", background=T.SURFACE, foreground=T.TEXT, font=(FONT, 11), padding=4
        )
        style.map(
            "Card.TCheckbutton",
            background=[
                ("disabled", T.SURFACE),
                ("focus", T.PRIMARY_SOFT),
                ("active", T.HOVER),
                ("pressed", T.PRESSED),
            ],
            foreground=[("disabled", T.DISABLED_INK), ("focus", T.PRIMARY)],
        )
        style.configure(
            "TSpinbox",
            foreground=T.TEXT,
            fieldbackground=T.SURFACE,
            insertcolor=T.TEXT,
            bordercolor=T.BORDER_CONTROL,
            arrowcolor=T.TEXT_SECONDARY,
            arrowsize=T.px(10),
            relief="flat",
            focuscolor=T.BG,
        )
        style.map(
            "TSpinbox",
            foreground=[("!disabled", T.TEXT)],
            fieldbackground=[("!disabled", T.SURFACE)],
            bordercolor=[("focus", T.PRIMARY)],
        )
        # ttk cannot rebind element images, so repaint the same PhotoImage pair in
        # place on every re-style. The element keeps its reference and picks up the
        # new palette automatically.
        if not getattr(self, "check_images", None):
            self.check_images = [
                tk.PhotoImage(master=root, width=18, height=18),
                tk.PhotoImage(master=root, width=18, height=18),
            ]
            style.element_create(
                "Checkmark.indicator",
                "image",
                self.check_images[0],
                ("selected", self.check_images[1]),
            )
        for selected, icon in enumerate(self.check_images):
            icon.blank()
            icon.put(T.SURFACE, to=(0, 0, 18, 18))
            icon.put(T.CHECK_BORDER, to=(0, 0, 18, 2))
            icon.put(T.CHECK_BORDER, to=(0, 16, 18, 18))
            icon.put(T.CHECK_BORDER, to=(0, 0, 2, 18))
            icon.put(T.CHECK_BORDER, to=(16, 0, 18, 18))
            if selected:
                for x, y in [
                    (4, 8),
                    (5, 9),
                    (6, 10),
                    (7, 11),
                    (8, 10),
                    (9, 9),
                    (10, 8),
                    (11, 7),
                    (12, 6),
                    (13, 5),
                ]:
                    icon.put(T.CHECK_MARK, to=(x, y, x + 2, y + 2))
        style.layout(
            "TCheckbutton",
            [
                (
                    "Checkbutton.padding",
                    {
                        "sticky": "nswe",
                        "children": [
                            ("Checkmark.indicator", {"side": "left", "sticky": ""}),
                            ("Checkbutton.label", {"side": "left", "sticky": "nswe"}),
                        ],
                    },
                )
            ],
        )

        style.configure(
            "Treeview",
            background=T.SURFACE,
            fieldbackground=T.SURFACE,
            foreground=T.TEXT,
            rowheight=ROW_H,
            bordercolor=T.BORDER_LIGHT,
            lightcolor=T.BORDER_LIGHT,
            darkcolor=T.BORDER_LIGHT,
            font=(FONT, 10),
        )
        style.configure(
            "Treeview.Heading",
            background=T.HOVER,
            foreground=T.TEXT,
            font=(FONT, 10, "bold"),
            relief="flat",
        )
        style.map(
            "Treeview",
            background=[("selected", T.SELECTED_BG)],
            foreground=[("selected", T.TEXT)],
        )
        for orientation in ("Vertical", "Horizontal"):
            name = f"{orientation}.TScrollbar"
            style.layout(
                name,
                [
                    (
                        f"{orientation}.Scrollbar.trough",
                        {
                            "sticky": "nswe",
                            "children": [(f"{orientation}.Scrollbar.thumb", {"sticky": "nswe"})],
                        },
                    )
                ],
            )
            style.configure(
                name,
                background=T.SCROLL_THUMB,
                troughcolor=T.SURFACE,
                bordercolor=T.SURFACE,
                lightcolor=T.SCROLL_THUMB,
                darkcolor=T.SCROLL_THUMB,
                arrowsize=10,
                width=9,
                borderwidth=0,
                relief="flat",
            )
            style.map(
                name,
                background=[("pressed", T.SCROLL_ACTIVE), ("active", T.SCROLL_HOVER)],
                lightcolor=[("pressed", T.SCROLL_ACTIVE), ("active", T.SCROLL_HOVER)],
                darkcolor=[("pressed", T.SCROLL_ACTIVE), ("active", T.SCROLL_HOVER)],
            )
        style.configure("TNotebook", background=T.BG, bordercolor=T.BORDER)
        style.configure("TNotebook.Tab", background=T.HOVER, foreground=T.TEXT, padding=(12, 8))
        style.map("TNotebook.Tab", background=[("selected", T.SURFACE)])
        style.configure("Horizontal.TProgressbar", troughcolor=T.TRACK, background=T.PRIMARY, thickness=T.px(T.PROGRESS_H))
        style.configure("TSeparator", background=T.BORDER_LIGHT)
        style.configure("Card.TLabel", background=T.SURFACE, foreground=T.TEXT, font=T.TYPE_BODY_LARGE)
        style.configure("StatHint.TLabel", background=T.SURFACE, foreground=T.TEXT_MUTED, font=T.TYPE_CAPTION)
        style.configure("Hint.TLabel", background=T.SURFACE, foreground=T.TEXT_SECONDARY, font=T.TYPE_CAPTION)
        style.configure("Muted.TLabel", background=T.BG, foreground=T.TEXT_SECONDARY, font=T.TYPE_CAPTION)

        # Remove the system 1-2px dotted focus rectangle. Modern controls draw a
        # 3px primary glow themselves; legacy ttk widgets keep a 1px primary
        # focus border instead (Tk cannot draw a glow around a native widget).
        def _strip_focus(node):
            """Delete ttk's dotted focus element but KEEP the elements inside it.

            In the clam theme Radiobutton.focus / Checkbutton.focus / Button.focus
            wrap the label element. Dropping the wrapper wholesale also drops the
            text, which is why radio buttons rendered as bare circles on Windows.
            Hoist the wrapper's children into its parent and carry over the
            wrapper's side/sticky so the label keeps its original position.
            """
            if isinstance(node, list):
                result = []
                for item in node:
                    stripped = _strip_focus(item)
                    if stripped is None:
                        continue
                    if isinstance(stripped, list):
                        result.extend(stripped)
                    else:
                        result.append(stripped)
                return result
            if isinstance(node, tuple) and len(node) == 2:
                name, spec = node
                if not isinstance(spec, dict):
                    return (name, spec)
                children = spec.get("children")
                stripped = _strip_focus(children) if children else None
                if name.endswith(".focus"):
                    hoisted = []
                    for child in stripped or []:
                        if not (isinstance(child, tuple) and len(child) == 2):
                            hoisted.append(child)
                            continue
                        child_spec = dict(child[1]) if isinstance(child[1], dict) else child[1]
                        if isinstance(child_spec, dict):
                            if spec.get("side"):
                                child_spec.setdefault("side", spec["side"])
                            if spec.get("sticky"):
                                child_spec.setdefault("sticky", spec["sticky"])
                        hoisted.append((child[0], child_spec))
                    return hoisted
                if stripped is not None:
                    spec = dict(spec)
                    spec["children"] = stripped
                return (name, spec)
            return node

        for name in (
            "TButton", "Accent.TButton", "Tool.TButton", "Link.TButton",
            "Ghost.TButton", "Icon.TButton", "TEntry", "Error.TEntry",
            "TCombobox", "TSpinbox", "TCheckbutton", "Card.TCheckbutton",
            "TRadiobutton", "Treeview",
        ):
            try:
                layout = _strip_focus(style.layout(name))
                if layout:
                    style.layout(name, layout)
            except (tk.TclError, ValueError):
                pass

    def _ensure_nav(self):
        if getattr(self, "nav", None) and self.nav.winfo_exists():
            self._paint_nav()
            return
        self.nav = tk.Frame(
            self.root,
            bg=T.NAV_BG,
            width=T.px(T.NAV_W),
            highlightthickness=0,
        )
        self.nav.pack_propagate(False)
        tk.Label(
            self.nav,
            text="Quiz App",
            bg=T.NAV_BG,
            fg=T.TEXT,
            font=T.TYPE_HEADING,
        ).pack(anchor="w", padx=T.px(T.SPACE_5), pady=(T.px(T.SPACE_5), T.px(T.SPACE_5)))
        self._nav_buttons = {}
        items = [
            ("home", "home", "首页", self.home),
            ("practice", "practice", "开始练习", self.configure),
            ("notebook", "notebook", "错题本与复习", self.notebook),
            ("history", "history", "学习统计与历史", self.history),
            ("settings", "settings", "设置 / 语言", self.settings),
        ]
        if self.user:
            items.insert(2, ("questions", "questions", "题库管理", self.manage_questions))
            if self.user["role"] == "admin":
                items.insert(3, ("users", "users", "用户管理", self.manage_users))
        for key, glyph, caption, command in items:
            button = modern.NavItem(
                self.nav,
                icon=glyph,
                command=lambda action=command, item=key: self._nav_go(item, action),
            )
            button.set_text(self.tr(caption))
            button.pack(fill="x", padx=T.px(T.SPACE_2), pady=T.px(T.SPACE_1))
            button._nav_key = key
            button._icon = glyph
            button._caption = caption
            self._nav_buttons[key] = button
        foot = tk.Frame(self.nav, bg=T.NAV_BG)
        foot.pack(side="bottom", fill="x", padx=T.px(T.SPACE_2), pady=T.px(T.SPACE_4))
        self.nav_user = tk.Label(
            foot,
            text="",
            bg=T.NAV_BG,
            fg=T.TEXT_SECONDARY,
            anchor="w",
            padx=T.px(T.SPACE_3),
            pady=T.px(T.SPACE_3),
            font=T.TYPE_CAPTION,
            cursor="hand2",
            highlightthickness=0,
        )
        self.nav_user.pack(fill="x")
        self.nav_theme = tk.Label(
            foot,
            text=self._theme_toggle_label(),
            bg=T.NAV_BG,
            fg=T.TEXT_MUTED,
            anchor="w",
            padx=T.px(T.SPACE_3),
            pady=T.px(T.SPACE_2),
            font=T.TYPE_CAPTION,
            cursor="hand2",
        )
        self.nav_theme.pack(fill="x", pady=(T.px(T.SPACE_2), 0))
        self.nav_theme.bind("<Button-1>", lambda _e: self.apply_theme(self.theme_labels()[2]))
        self.nav_theme.bind("<Enter>", lambda _e: self.nav_theme.configure(fg=T.TEXT))
        self.nav_theme.bind("<Leave>", lambda _e: self.nav_theme.configure(fg=T.TEXT_MUTED))
        self.nav_user.bind("<Button-1>", lambda _e: self._account_menu())
        self.nav_user.bind("<Enter>", lambda _e: self.nav_user.configure(bg=T.HOVER))
        self.nav_user.bind("<Leave>", lambda _e: self.nav_user.configure(bg=T.NAV_BG))
        self._account_popup = tk.Menu(
            self.root, tearoff=0, bg=T.SURFACE, fg=T.TEXT, activebackground=T.HOVER
        )
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
        # Hover / pressed / focus / disabled states are handled inside NavItem.
        return None

    def _paint_nav(self):
        expected = {"home", "practice", "notebook", "history", "settings"}
        if self.user:
            expected.add("questions")
            if self.user["role"] == "admin":
                expected.add("users")
        if getattr(self, "_nav_buttons", None) and set(self._nav_buttons) != expected:
            self.nav.destroy()
            self.nav = None
            self._ensure_nav()
            return
        current = getattr(self, "_nav_key", None)
        for key, button in getattr(self, "_nav_buttons", {}).items():
            if not button.winfo_exists():
                continue
            button.set_text(self.tr(button._caption))
            button.set_selected(key == current)
        label = getattr(self, "nav_user", None)
        if label and label.winfo_exists():
            if self.user:
                label.configure(text=self.user["name"])
            elif self.signed_in:
                label.configure(text=self.tr("访客"))
            else:
                label.configure(text="")
        theme_label = getattr(self, "nav_theme", None)
        if theme_label and theme_label.winfo_exists():
            theme_label.configure(text=self._theme_toggle_label(), bg=T.NAV_BG, fg=T.TEXT_MUTED)

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
        content_w = min(
            T.px(T.CONTENT_MAX),
            max(width - T.px(T.PAGE_PAD) * 2, T.px(T.CONTENT_MIN)),
        )
        self.canvas.coords(self.window, width // 2, 0)
        self.canvas.itemconfigure(self.window, width=content_w)
        self._sync_body_height()
        self._sync_scroll()

    def _sync_body_height(self):
        """Let short pages (dashboard) use the full viewport height.

        The Canvas window item otherwise adopts only the body's requested
        height, so ``pack(expand=True)`` has nothing to expand into and a
        maximized window shows a large dead area under the cards. For pages
        taller than the viewport the requested height wins, so scrolling and
        the quiz action dock keep working exactly as before.
        """
        try:
            viewport = max(self.canvas.winfo_height(), 1)
            needed = max(self.body.winfo_reqheight(), 1)
            wanted = str(max(viewport, needed))
            if self.canvas.itemcget(self.window, "height") != wanted:
                self.canvas.itemconfigure(self.window, height=wanted)
        except tk.TclError:
            pass

    def _on_body_configure(self, _event=None):
        self._sync_body_height()
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except tk.TclError:
            pass

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
        wide = self.root.winfo_width() >= SPLIT_WIDE
        if not wide:
            if form.winfo_manager() == "place":
                form.place_forget()
            form.pack_propagate(True)
            form.configure(width=0, height=0)
            if form.winfo_manager() != "pack":
                form.pack(fill="x", padx=T.px(SPACE_4), pady=T.px(SPACE_4))
            return
        if form.winfo_manager() == "pack":
            form.pack_forget()
        # A previous pass pins width/height with propagation off. Re-enable it
        # BEFORE measuring, otherwise winfo_reqwidth() returns that stale value
        # and the toolbar (4 buttons) is permanently clipped at high DPI.
        form.pack_propagate(True)
        form.configure(width=0, height=0)
        pane.update_idletasks()
        self.root.update_idletasks()
        needed = form.winfo_reqwidth()
        height = form.winfo_reqheight()
        min_w = max(T.px(CARD_WIDTH), needed)
        room = pane.winfo_width() - T.px(T.SPACE_6)
        form_w = min_w if room >= min_w else max(room, T.px(280))
        form.pack_propagate(False)
        form.configure(width=form_w, height=height)
        view = pane.winfo_height()
        gap = T.px(T.SPACE_5)
        y = max((view - height) // 2, gap) if view > height else gap
        form.place(relx=0.5, y=y, anchor="n", width=form_w, height=height)

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
        self.password_toggle.configure(
            text=self.tr("隐藏") if self.show_password else self.tr("显示")
        )

    def _field_border(self, widget, color, fill=None):
        shell = getattr(widget, "_shell", widget)
        shell.configure(bg=color)
        if fill is not None and widget.winfo_exists():
            widget.configure(bg=fill)

    def _focus_field(self, entry, focused):
        if entry in getattr(self, "_login_error_fields", ()):
            return
        self._field_border(entry, T.PRIMARY if focused else T.BORDER, T.SURFACE)

    def _wire_field(self, entry):
        entry.bind("<FocusIn>", lambda _e, field=entry: self._focus_field(field, True), add="+")
        entry.bind("<FocusOut>", lambda _e, field=entry: self._focus_field(field, False), add="+")

    def _mark_login_error(self, message, fields=None):
        self.login_error.configure(text=message)
        if not self.login_error.winfo_ismapped():
            self.login_error.pack(
                anchor="w", fill="x", before=self.login_button._shell, pady=(0, SPACE_SM)
            )
        targets = fields or list(getattr(self, "login_fields", []))
        self._login_error_fields = set(targets)
        for entry in getattr(self, "login_fields", []):
            if entry in targets:
                self._field_border(entry, T.ERROR, T.ERROR_BG)
            else:
                self._field_border(entry, T.BORDER, T.SURFACE)
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
                color = T.PRIMARY if entry == self.root.focus_get() else T.BORDER
                self._field_border(entry, color, T.SURFACE)
        if had_error:
            self._center_login_form()

    def _bind_chrome(self, button, idle, hover, active, idle_fg, hover_fg=None):
        idle_fg = self._native_button_ink(idle_fg)
        hover_fg = self._native_button_ink(hover_fg or idle_fg)

        def enter(_e):
            if str(button["state"]) == "normal":
                button.configure(
                    bg=hover, fg=hover_fg, activebackground=hover, activeforeground=hover_fg
                )

        def leave(_e):
            if str(button["state"]) == "normal":
                button.configure(
                    bg=idle, fg=idle_fg, activebackground=active, activeforeground=hover_fg
                )

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
        if self.aqua and color in {T.TEXT, T.BUTTON_INK}:
            return "#111111"
        return color

    def _tool_button(self, parent, text, command):
        button = self._flat_button(
            parent, text, command, TYPE_TOOL, T.BG, T.TEXT, SPACE_3, max(8, (HIT - 18) // 2)
        )
        self._bind_chrome(button, T.BG, T.HOVER, T.TRACK, T.TEXT)
        button._button = button
        return button

    def _text_button(self, parent, text, command, bg=None):
        # Resolve at call time: the palette is rebound when the theme changes.
        button = self._flat_button(parent, text, command, TYPE_HINT, bg or T.SURFACE, T.PRIMARY, 0, 2)

        def enter(_e):
            if str(button["state"]) == "normal":
                button.configure(fg=T.PRIMARY_HOVER, font=(FONT, 10, "underline"))

        def leave(_e):
            if str(button["state"]) == "normal":
                button.configure(fg=T.PRIMARY, font=TYPE_HINT)

        button.bind("<Enter>", enter)
        button.bind("<Leave>", leave)
        return button

    def _primary_button(self, parent, text, command):
        shell = tk.Frame(parent, bg=T.BUTTON_FILL, highlightthickness=0, bd=0)
        button = self._flat_button(
            shell, text, command, TYPE_BUTTON, T.BUTTON_FILL, T.BUTTON_INK, 16, 12
        )
        button.configure(anchor="center", justify="center")
        shell.configure(height=T.px(48))
        shell.pack_propagate(False)
        button.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._bind_chrome(button, T.BUTTON_FILL, T.PRIMARY_HOVER, T.PRIMARY_ACTIVE, T.BUTTON_INK, T.BUTTON_INK)
        button._shell = shell
        return button

    def _text_entry(self, parent, variable, show=None):
        shell = tk.Frame(parent, bg=T.BORDER, highlightthickness=0, bd=0)
        entry = tk.Entry(
            shell,
            textvariable=variable,
            font=TYPE_BODY,
            bg=T.SURFACE,
            fg=T.TEXT,
            insertbackground=T.TEXT,
            relief="flat",
            bd=0,
            borderwidth=0,
            highlightthickness=0,
            show=show or "",
        )
        entry.pack(fill="x", ipady=T.px(12), padx=T.px(1), pady=T.px(1))
        entry._shell = shell
        return entry

    def _set_login_button(self, text, disabled):
        color = T.PRIMARY_DISABLED if disabled else T.BUTTON_FILL
        if self.aqua:
            ink = T.MUTED if disabled else "#111111"
        else:
            ink = T.MUTED if disabled else T.ON_PRIMARY
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
        remember = getattr(self, "remember_check", None)
        if remember and remember.winfo_exists():
            remember.configure(state="disabled" if disabled else "normal")

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
        self.login_host = tk.Frame(self.outer, bg=T.BG)
        self.login_host.pack(fill="both", expand=True)
        # Pack the split directly: Canvas create_window + Entry causes Windows IME lag.
        self.login_split = tk.Frame(self.login_host, bg=T.BG)
        self.login_split.pack(fill="both", expand=True)
        self.login_host.bind("<Configure>", self._on_login_host)
        self.login_split.columnconfigure(0, weight=1)
        self.login_split.columnconfigure(1, weight=1)
        self.login_split.rowconfigure(0, weight=1)
        self.login_split.rowconfigure(1, weight=1)
        # Left panel: one quiet wordmark, one sentence, one hairline, one fact.
        # The old geometric art and per-subject progress bars were decorative only.
        self.brand = tk.Frame(
            self.login_split, bg=T.SKY,
            padx=T.px(T.SPACE_6), pady=T.px(T.SPACE_6),
        )
        brand_inner = tk.Frame(self.brand, bg=T.SKY)
        brand_inner.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.9)
        ttk.Label(brand_inner, text="QUIZ STUDIO", style="BrandMark.TLabel").pack(
            anchor="center", pady=(0, T.px(T.SPACE_4))
        )
        headline = self.tr(
            "每天一点练习，看见自己的进步。\n英语 · 数学 · 科学 | 本地保存 · 离线使用"
        )
        lead, subline = headline.split("\n", 1)
        title = ttk.Label(
            brand_inner,
            text=lead,
            style="BrandTitle.TLabel",
            wraplength=T.px(560),
            justify="center",
            anchor="center",
        )
        title.pack(anchor="center", pady=(T.px(T.SPACE_5), T.px(T.SPACE_3)))
        brand_inner.bind(
            "<Configure>",
            lambda e: title.configure(
                wraplength=max(e.width - T.px(T.SPACE_2), T.px(320))
            ),
        )
        tk.Label(
            brand_inner,
            text=subline,
            bg=T.SKY,
            fg=T.MUTED,
            font=T.TYPE_BODY_LARGE,
            wraplength=T.px(560),
            justify="center",
            anchor="center",
        ).pack(anchor="center", pady=(0, T.px(T.SPACE_6)))
        tk.Frame(brand_inner, bg=T.BORDER, height=T.px(1)).pack(
            fill="x", pady=T.px(T.SPACE_5)
        )
        counts = {}
        for question in self.questions:
            counts[question.subject] = counts.get(question.subject, 0) + 1
        tk.Label(
            brand_inner,
            text=self.tr(
                "离线学习 · 即时反馈 · 错题复习\n已加载 {0} 道题，{1} 个学科。",
                sum(counts.values()),
                len(counts),
            ),
            bg=T.SKY,
            fg=T.MUTED,
            font=T.TYPE_HINT,
            wraplength=T.px(560),
            justify="center",
            anchor="center",
        ).pack(anchor="center", pady=(T.px(T.SPACE_5), 0))
        self.login_pane = tk.Frame(self.login_split, bg=T.BG)
        self.login_form = tk.Frame(self.login_pane, bg=T.BG, width=T.px(CARD_WIDTH))
        self.login_tools = tk.Frame(self.login_form, bg=T.BG)
        self.login_tools.pack(fill="x", pady=(0, T.px(T.SPACE_4)))
        self._tool_button(self.login_tools, self.tr("退出"), self.close).pack(side="right")
        lang_menu = tk.Menu(self.root, tearoff=0, bg=T.SURFACE, fg=T.TEXT, activebackground=T.HOVER, bd=0)
        lang_menu.add_command(
            label=self.tr("简体中文"), command=lambda: self._apply_login_language("zh")
        )
        lang_menu.add_command(label="English", command=lambda: self._apply_login_language("en"))
        lang = self._tool_button(
            self.login_tools, "中文 ▾" if self.tr.language == "zh" else "EN ▾", lambda: None
        )
        lang._button.configure(
            command=lambda: lang_menu.tk_popup(
                lang.winfo_rootx(), lang.winfo_rooty() + lang.winfo_height()
            )
        )
        lang.pack(side="right", padx=(0, T.px(T.SPACE_2)))
        self._tool_button(self.login_tools, self.tr("设置"), self.settings).pack(
            side="right", padx=(0, T.px(T.SPACE_2))
        )
        # Theme must be reachable before sign-in, when the sidebar is hidden.
        self._tool_button(
            self.login_tools,
            self._login_theme_label(),
            lambda: self.apply_theme(self.theme_labels()[2]),
        ).pack(side="right", padx=(0, T.px(T.SPACE_2)))
        # Rounded soft card instead of a 1px hard rectangle; card_frame keeps
        # the same tk.Frame API so all the fields below stay unchanged.
        card = card_frame(self.login_form, pad=T.SPACE_6)
        card.pack(fill="x")
        tk.Label(
            card,
            text=self.tr("创建本地账户") if registering else self.tr("欢迎回来"),
            font=TYPE_CARD,
            bg=T.SURFACE,
            fg=T.TEXT,
        ).pack(anchor="w")
        tk.Label(
            card,
            text=self.tr("用户名 3–32 位；密码 6–16 位。")
            if registering
            else self.tr("继续你的学习旅程"),
            font=TYPE_HINT,
            bg=T.SURFACE,
            fg=T.MUTED,
            anchor="w",
            justify="left",
            wraplength=T.px(CARD_WIDTH - 64),
        ).pack(anchor="w", pady=(T.px(SPACE_XS), T.px(SPACE_MD)))
        saved_login = (
            self.login_preferences.load()
            if not registering
            else {"username": "", "password": "", "remember": False}
        )
        self.login_name = tk.StringVar(value=saved_login["username"])
        self.login_password = tk.StringVar(value=saved_login["password"])
        self.login_confirm = tk.StringVar()
        self.remember_password = tk.BooleanVar(value=saved_login["remember"])
        self.password_entries = []
        tk.Label(card, text=self.tr("用户名"), font=TYPE_LABEL, bg=T.SURFACE, fg=T.TEXT).pack(
            anchor="w"
        )
        name_entry = self._text_entry(card, self.login_name)
        name_entry._shell.pack(anchor="w", fill="x", pady=(T.px(SPACE_XS), T.px(SPACE_MD)))
        tk.Label(card, text=self.tr("密码"), font=TYPE_LABEL, bg=T.SURFACE, fg=T.TEXT).pack(anchor="w")
        password_box = tk.Frame(card, bg=T.BORDER, highlightthickness=0, bd=0)
        password_box.pack(anchor="w", fill="x", pady=(T.px(SPACE_XS), T.px(SPACE_MD)))
        password_inner = tk.Frame(password_box, bg=T.SURFACE)
        password_inner.pack(fill="x", padx=T.px(1), pady=T.px(1))
        password_entry = tk.Entry(
            password_inner,
            textvariable=self.login_password,
            font=TYPE_BODY,
            bg=T.SURFACE,
            fg=T.TEXT,
            insertbackground=T.TEXT,
            relief="flat",
            bd=0,
            borderwidth=0,
            highlightthickness=0,
            show="•",
        )
        password_entry._shell = password_box
        password_entry.pack(side="left", fill="x", expand=True, ipady=T.px(12), padx=T.px(SPACE_SM))
        self.password_entries.append(password_entry)
        self.password_toggle = self._text_button(
            password_inner, self.tr("显示"), self._toggle_password
        )
        self.password_toggle.configure(padx=T.px(SPACE_3), pady=T.px(11))
        self.password_toggle.pack(side="right", padx=T.px(SPACE_SM))
        if not registering:
            self.remember_check = ttk.Checkbutton(
                card,
                text=self.tr("记住密码"),
                variable=self.remember_password,
                style="Card.TCheckbutton",
            )
            self.remember_check.pack(anchor="w", pady=(0, T.px(SPACE_MD)))
        if registering:
            tk.Label(card, text=self.tr("确认密码"), font=TYPE_LABEL, bg=T.SURFACE, fg=T.TEXT).pack(
                anchor="w"
            )
            confirm = self._text_entry(card, self.login_confirm, show="•")
            confirm._shell.pack(anchor="w", fill="x", pady=(T.px(SPACE_XS), T.px(SPACE_MD)))
            self.password_entries.append(confirm)
        self.login_fields = [name_entry, *self.password_entries]
        self._login_error_fields = set()
        self.login_error = tk.Label(
            card,
            text="",
            font=TYPE_HINT,
            bg=T.SURFACE,
            fg=T.ERROR,
            wraplength=T.px(CARD_WIDTH - 48),
            justify="left",
            anchor="w",
        )
        self.login_button = self._primary_button(
            card,
            self.tr("注册并进入") if registering else self.tr("登录"),
            lambda: self.authenticate(registering),
        )
        self.login_button._shell.pack(anchor="w", fill="x", pady=(0, T.px(SPACE_MD)))
        account_row = tk.Frame(card, bg=T.SURFACE)
        account_row.pack(anchor="w")
        if registering:
            self._text_button(
                account_row, self.tr("已有账户，去登录"), lambda: self.login_page(False)
            ).pack(side="left")
        else:
            tk.Label(
                account_row, text=self.tr("还没有账户？"), font=TYPE_HINT, bg=T.SURFACE, fg=T.MUTED
            ).pack(side="left")
            self._text_button(account_row, self.tr("创建账户"), lambda: self.login_page(True)).pack(
                side="left", padx=(T.px(SPACE_XS), 0)
            )
        guest = tk.Frame(self.login_form, bg=T.BG)
        guest.pack(fill="x", pady=(T.px(SPACE_MD), 0))
        guest_btn = self._text_button(guest, self.tr("以访客身份继续"), self.enter_guest, bg=T.BG)
        guest_btn.configure(padx=T.px(SPACE_3), pady=T.px(11), anchor="center")
        guest_btn.pack()
        tk.Label(
            guest,
            text=self.tr("练习记录将保存在当前设备"),
            font=TYPE_FOOT,
            bg=T.BG,
            fg=T.MUTED,
            anchor="center",
            wraplength=T.px(CARD_WIDTH - 40),
        ).pack(fill="x", pady=(T.px(SPACE_SM), 0))
        if self.tr.warning:
            tk.Label(
                guest, text=self.tr.warning, font=TYPE_HINT, bg=T.BG, fg=T.MUTED,
            wraplength=T.px(CARD_WIDTH),
            ).pack(pady=T.px(SPACE_SM))
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
        self._pending_login_credentials = (
            name,
            password,
            bool(self.remember_password.get()) if not registering else False,
        )
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
        name, password, remember = self._pending_login_credentials
        try:
            self.login_preferences.save(name, password, remember)
        except (DataError, OSError, ValueError) as exc:
            messagebox.showwarning(self.tr("保存失败"), self.tr(str(exc)), parent=self.root)
        self.login_password.set("")
        self.login_confirm.set("")
        self._login_busy = False
        self.user = payload
        self.progress = ProgressRepository(self.auth.progress_path(payload))
        self.personal_bank = PersonalQuestionRepository(self.auth.personal_questions_path(payload))
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
        if not self.user or not self.check_session():
            messagebox.showinfo(
                self.tr("权限提示"),
                self.tr("请先登录账户，再管理个人题库。"),
                parent=self.root,
            )
            return
        self._nav_key = "questions"
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
            self._nav_key = "users"
            self.users_page = UserPage(self)
            self.users_page.show_list()

    def settings(self):
        self._nav_key = "settings"
        self.clear(self.tr("设置"), show_heading=False)
        gap = T.px(T.SPACE_3)
        pad = T.px(T.SPACE_5)

        def fit(widget):
            """Let a fill="x" description use the whole card instead of a
            fixed 640px column (which looks clipped on a maximized window)."""
            def on_resize(event):
                target = max(event.width - T.px(T.SPACE_1), 1)
                try:
                    if widget.cget("wraplength") != target:
                        widget.configure(wraplength=target)
                except tk.TclError:
                    pass
            widget.bind("<Configure>", on_resize, add="+")
            return widget

        appearance = ttk.LabelFrame(self.body, text=self.tr("外观"), padding=pad)
        appearance.pack(fill="x", pady=gap)
        self.theme_choice = tk.StringVar(value=T.theme_name())
        theme_row = tk.Frame(appearance, bg=T.SURFACE)
        theme_row.pack(fill="x")
        tk.Label(
            theme_row, text=self.tr("深色模式"), bg=T.SURFACE, fg=T.TEXT,
            font=T.TYPE_BODY_LARGE, anchor="w",
        ).pack(side="left")
        modern.Toggle(
            theme_row,
            value=T.theme_name() == "dark",
            command=lambda: self.apply_theme(
                "light" if T.theme_name() == "dark" else "dark"
            ),
        ).pack(side="right")
        fit(tk.Label(
            appearance,
            text=self.tr("主题会立即生效并记住选择。"),
            bg=T.SURFACE, fg=T.TEXT_MUTED, font=T.TYPE_CAPTION, anchor="w",
        )).pack(fill="x", pady=(T.px(T.SPACE_2), 0))

        card = ttk.LabelFrame(self.body, text=self.tr("界面语言"), padding=pad)
        card.pack(fill="x", pady=gap)
        self.language = tk.StringVar(value=self.tr.language)
        ttk.Radiobutton(card, text=self.tr("简体中文"), variable=self.language, value="zh").pack(
            anchor="w", pady=T.px(T.SPACE_1)
        )
        ttk.Radiobutton(card, text="English", variable=self.language, value="en").pack(
            anchor="w", pady=T.px(T.SPACE_1)
        )
        fit(ttk.Label(
            card,
            text=self.tr("切换立即生效并记住选择；题库内容保留原文。"),
            style="Card.TLabel",
        )).pack(fill="x", pady=(T.px(T.SPACE_3), 0))

        motion = ttk.LabelFrame(self.body, text=self.tr("动画效果"), padding=pad)
        motion.pack(fill="x", pady=gap)
        self.motion_choice = tk.BooleanVar(value=self.motion.enabled)
        ttk.Radiobutton(motion, text=self.tr("开启"), variable=self.motion_choice, value=True).pack(
            anchor="w", pady=T.px(T.SPACE_1)
        )
        ttk.Radiobutton(
            motion, text=self.tr("关闭"), variable=self.motion_choice, value=False
        ).pack(anchor="w", pady=T.px(T.SPACE_1))
        fit(ttk.Label(
            motion,
            text=self.tr("关闭后页面直接切换，仍保留颜色和文字反馈。"),
            style="Card.TLabel",
        )).pack(fill="x", pady=(T.px(T.SPACE_3), 0))

        self.button(self.tr("保存语言设置"), self.save_language, "Accent.TButton")
        self.label(self.tr("窗口与布局"))
        self.window_choices = [self.tr("自动适应屏幕"), "960x640", "1080x720", "1280x800"]
        self.window_choice = tk.StringVar(
            value=self.window_choices[0] if self.display["size"] == "auto" else self.display["size"]
        )
        modern.Dropdown(
            self.body,
            textvariable=self.window_choice,
            values=self.window_choices,
            width=T.px(360),
        ).pack(anchor="w", pady=(T.px(T.FIELD_GAP), 0))
        self.compact_choice = tk.BooleanVar(value=self.display["compact"])
        ttk.Checkbutton(self.body, text=self.tr("紧凑页边距"), variable=self.compact_choice).pack(
            anchor="w", pady=T.px(T.SPACE_1)
        )
        self.label(self.tr("调整程序窗口大小，不改变电脑分辨率。"))
        self.wheel_choice = tk.BooleanVar(value=self.display.get("wheel_controls", False))
        ttk.Checkbutton(
            self.body, text=self.tr("允许滚轮更改下拉选项和题数"), variable=self.wheel_choice
        ).pack(anchor="w", pady=T.px(T.SPACE_1))
        self.button(self.tr("应用窗口与布局"), self.save_display, "Accent.TButton")

        ai_card = ttk.LabelFrame(self.body, text=self.tr("问问 AI 设置"), padding=pad)
        ai_card.pack(fill="x", pady=gap)
        ai_config = self.ai_settings.load()
        self.ai_endpoint = tk.StringVar(value=ai_config["endpoint"])
        self.ai_model = tk.StringVar(value=ai_config["model"])
        self.ai_key = tk.StringVar()
        for title, variable, secret in (
            (self.tr("API 地址"), self.ai_endpoint, False),
            (self.tr("模型"), self.ai_model, False),
            (self.tr("DeepSeek API Key（留空表示不修改）"), self.ai_key, True),
        ):
            ttk.Label(ai_card, text=title, style="Card.TLabel").pack(
                anchor="w", pady=(T.px(T.SPACE_1), T.px(T.SPACE_1))
            )
            ttk.Entry(ai_card, textvariable=variable, show="•" if secret else "").pack(fill="x")
        fit(ttk.Label(
            ai_card,
            text=self.tr("API Key 使用当前系统账户加密保存，不会写入代码或提交到 Git。"),
            style="Card.TLabel",
        )).pack(fill="x", pady=(T.px(T.SPACE_3), T.px(T.SPACE_1)))
        ttk.Button(
            ai_card,
            text=self.tr("保存 AI 设置"),
            command=self.save_ai_settings,
            style="Accent.TButton",
        ).pack(anchor="w", pady=(T.px(T.SPACE_1), 0))
        if self.display_warning:
            self.label(self.display_warning)
        self.button(self.tr("返回"), self.home if self.signed_in else self.login_page)

    def apply_window_size(self):
        width, height = window_size(
            self.display["size"], self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        )
        self.root.minsize(min(720, width), min(480, height))
        self.root.geometry(f"{width}x{height}")

    def save_display(self):
        size = (
            "auto"
            if self.window_choice.get() == self.window_choices[0]
            else self.window_choice.get()
        )
        try:
            self.display_store.save(size, self.compact_choice.get(), self.wheel_choice.get())
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

    def save_ai_settings(self):
        try:
            self.ai_settings.save(self.ai_endpoint.get(), self.ai_model.get(), self.ai_key.get())
        except (ValueError, DataError, OSError) as exc:
            messagebox.showerror(self.tr("保存失败"), self.tr(str(exc)), parent=self.root)
            return
        messagebox.showinfo(self.tr("保存成功"), self.tr("AI 设置已保存。"), parent=self.root)
        self.settings()

    def _control_wheel(self, event):
        if not self.display.get("wheel_controls", False):
            return "break"
        widget = event.widget
        direction = -1 if getattr(event, "delta", 0) > 0 or getattr(event, "num", None) == 4 else 1
        if isinstance(widget, (ttk.Combobox, modern.Dropdown)):
            values = widget["values"]
            if values:
                widget.current(max(0, min(len(values) - 1, widget.current() + direction)))
                widget.event_generate("<<ComboboxSelected>>")
        elif isinstance(widget, modern.Stepper):
            try:
                widget.set(str(max(widget._min, int(widget.get()) - direction)))
            except ValueError:
                pass
        elif isinstance(widget, ttk.Spinbox):
            try:
                value = max(
                    float(widget.cget("from")),
                    min(float(widget.cget("to")), float(widget.get()) - direction),
                )
                widget.set(str(int(value)))
            except ValueError:
                pass
        return "break"

    def _page_wheel(self, event):
        if isinstance(
            event.widget,
            (ttk.Combobox, ttk.Spinbox, tk.Text, ttk.Treeview,
             modern.Dropdown, modern.Stepper),
        ):
            return
        self.canvas.yview_scroll(-int(event.delta / 120), "units")

    def _action_dock(self):
        self.action_dock = ttk.Frame(
            self.outer, style="App.TFrame", padding=(T.px(T.SPACE_4), T.px(T.SPACE_3))
        )
        self.action_dock.pack(side="bottom", fill="x", before=self.canvas)
        return self.action_dock

    def clear(self, title, heading=True, show_heading=True, back=None):
        if self._login_after:
            self.root.after_cancel(self._login_after)
            self._login_after = None
        self.motion.cancel()
        if getattr(self, "action_dock", None) is not None:
            self.action_dock.destroy()
            self.action_dock = None
        if getattr(self, "quiz_progress_header", None) is not None:
            self.quiz_progress_header.destroy()
            self.quiz_progress_header = None
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
            self.body.configure(padding=(T.px(T.PAGE_PAD), T.px(T.SPACE_4)))
        self.chrome_title.configure(text=title)
        back_action = (
            back if back is not None else (None if title == self.tr("首页") else self.home)
        )
        if heading and back_action:
            self.chrome_back.configure(command=back_action)
            self.chrome_back.pack(side="left", before=self.chrome_title, padx=(0, 10))
        else:
            self.chrome_back.pack_forget()
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

    def _fit_wrap(self, widget):
        """Wrap a fill="x" label at its real width.

        A fixed wraplength either clips text when the card is narrower than the
        constant, or leaves it in a narrow column on a maximized 2K/4K window.
        Only use on labels packed with fill="x" (their width is stable).
        """
        def on_resize(event):
            target = max(event.width - T.px(T.SPACE_1), 1)
            try:
                if widget.cget("wraplength") != target:
                    widget.configure(wraplength=target)
            except tk.TclError:
                pass

        widget.bind("<Configure>", on_resize, add="+")
        return widget

    def label(self, text, style="TLabel"):
        widget = ttk.Label(
            self.body,
            text=text,
            justify="left",
            anchor="w",
            style=style,
        )
        self._fit_wrap(widget)
        widget.pack(fill="x", pady=T.px(T.SPACE_1))
        return widget

    def button(self, text, command, style="TButton"):
        variant = (
            "primary" if "Accent" in style
            else "ghost" if ("Ghost" in style or "Link" in style)
            else "secondary"
        )
        widget = modern.SoftButton(
            self.body,
            text=text,
            command=command,
            variant=variant,
            width=max(T.px(160), len(text) * T.px(10) + T.px(40)),
        )
        widget.pack(anchor="w", pady=T.px(T.SPACE_1))
        return widget

    def _mock_action(self, parent, text, command, primary=True, padx=18, pady=11):
        """Canvas-friendly action used by the approved dark mock-up."""
        idle = T.PRIMARY if primary else T.HOVER
        hover = T.PRIMARY_HOVER if primary else T.HOVER
        label = tk.Label(
            parent,
            text=text,
            bg=idle,
            fg=T.ON_PRIMARY if primary else T.TEXT,
            font=(FONT, 11, "bold"),
            padx=padx,
            pady=pady,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground=T.PRIMARY if primary else T.BORDER,
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
            question.id: question for question in [*self.public_questions, *self.personal_questions]
        }

    def _plan_ring(self, parent, plan):
        """Render the concept mock-up's circular daily-goal indicator."""
        size = 152
        canvas = tk.Canvas(parent, width=size, height=size, bg=T.SURFACE, highlightthickness=0, bd=0)
        canvas.create_oval(15, 15, size - 15, size - 15, outline=T.TRACK, width=12)
        if plan["percent"]:
            canvas.create_arc(
                15,
                15,
                size - 15,
                size - 15,
                start=90,
                extent=-min(100, plan["percent"]) * 3.6,
                style="arc",
                outline=T.PRIMARY,
                width=12,
            )
        canvas.create_text(
            size / 2,
            62,
            text=f"{plan['today']} / {plan['daily_goal']}",
            fill=T.TEXT,
            font=(FONT, 18, "bold"),
        )
        canvas.create_text(size / 2, 91, text=self.tr("今日进度"), fill=T.MUTED, font=TYPE_HINT)
        canvas.create_text(
            size / 2,
            112,
            text=f"{plan['percent']:.0f}%",
            fill=T.PRIMARY,
            font=(FONT, 11, "bold"),
        )
        return canvas

    def _weekly_chart(self, parent, weekly):
        """Render a compact seven-day activity chart."""
        width, height = 330, 142
        canvas = tk.Canvas(
            parent, width=width, height=height, bg=T.SURFACE, highlightthickness=0, bd=0
        )
        top, baseline = 18, 105
        maximum = max([item["count"] for item in weekly] + [1])
        canvas.create_line(8, baseline, width - 8, baseline, fill=T.BORDER, width=1)
        gap = (width - 24) / max(1, len(weekly))
        for index, item in enumerate(weekly):
            center = 12 + gap * index + gap / 2
            bar_height = (
                0 if not item["count"] else max(7, item["count"] / maximum * (baseline - top))
            )
            canvas.create_rectangle(
                center - 10,
                baseline - bar_height,
                center + 10,
                baseline,
                fill=T.PRIMARY,
                outline="",
            )
            canvas.create_text(
                center,
                baseline - bar_height - 9,
                text=str(item["count"]),
                fill=T.TEXT if item["count"] else T.MUTED,
                font=(FONT, 8),
            )
            canvas.create_text(
                center,
                125,
                text=item["date"][5:],
                fill=T.MUTED,
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
        rail = tk.Frame(shell, bg=T.BG, width=280)
        self.home_rail = rail
        if self.root.winfo_width() >= 1020:
            rail.pack(side="right", fill="y")
        rail.pack_propagate(False)
        composer = card_frame(feed, pad=16)
        composer.pack(fill="x", pady=(0, 16))
        tk.Label(composer, text=name, bg=T.SURFACE, fg=T.MUTED, font=TYPE_HINT).pack(anchor="w")
        tk.Label(
            composer,
            text=self.tr("有什么想练习的？"),
            bg=T.SURFACE,
            fg=T.TEXT,
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
            plan_head = tk.Frame(plan_card, bg=T.SURFACE)
            plan_head.pack(fill="x")
            tk.Label(
                plan_head,
                text=self.tr("每日学习计划"),
                bg=T.SURFACE,
                fg=T.TEXT,
                font=(FONT, 14, "bold"),
            ).pack(side="left")
            ttk.Button(
                plan_head,
                text=self.tr("调整每日目标"),
                command=self.set_daily_goal,
                style="Tool.TButton",
            ).pack(side="right")
            dashboard = tk.Frame(plan_card, bg=T.SURFACE)
            dashboard.pack(fill="x", pady=(12, 0))
            self._plan_ring(dashboard, plan).pack(side="left", padx=(0, 18))
            goal_stats = tk.Frame(dashboard, bg=T.SURFACE)
            goal_stats.pack(side="left", fill="y", padx=(0, 18))
            for value, title in (
                (plan["daily_goal"], self.tr("每日目标")),
                (plan["remaining"], self.tr("还差题数")),
                (plan["streak"], self.tr("连续学习天数")),
            ):
                stat = tk.Frame(goal_stats, bg=T.HOVER, padx=14, pady=8)
                stat.pack(fill="x", pady=(0, 7))
                tk.Label(
                    stat,
                    text=str(value),
                    bg=T.HOVER,
                    fg=T.TEXT,
                    font=(FONT, 15, "bold"),
                ).pack(side="left")
                tk.Label(stat, text=title, bg=T.HOVER, fg=T.MUTED, font=TYPE_HINT).pack(
                    side="left", padx=(9, 0)
                )
            chart = tk.Frame(dashboard, bg=T.SURFACE)
            chart.pack(side="left", fill="both", expand=True)
            tk.Label(
                chart,
                text=self.tr("最近 7 天"),
                bg=T.SURFACE,
                fg=T.TEXT,
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
            bg=T.BG,
            fg=T.MUTED,
            font=TYPE_HINT,
        ).pack(anchor="w", pady=(0, 12))
        tk.Label(feed, text=self.tr("你的学习动态"), bg=T.BG, fg=T.TEXT, font=(FONT, 15, "bold")).pack(
            anchor="w", pady=(4, 8)
        )
        if bank_error:
            empty = card_frame(feed, pad=16)
            empty.pack(fill="x")
            tk.Label(
                empty,
                text=self.tr("学习数据加载失败"),
                bg=T.SURFACE,
                fg=T.TEXT,
                font=(FONT, 13, "bold"),
            ).pack(anchor="w")
            tk.Label(
                empty,
                text=self.tr(bank_error),
                bg=T.SURFACE,
                fg=T.MUTED,
                wraplength=T.px(520),
                justify="left",
            ).pack(anchor="w", pady=8)
            ttk.Button(
                empty, text=self.tr("重新加载题库"), command=self.home, style="Accent.TButton"
            ).pack(anchor="w")
        elif not history:
            empty = card_frame(feed, pad=16)
            empty.pack(fill="x")
            tk.Label(
                empty, text=self.tr("还没有学习记录"), bg=T.SURFACE, fg=T.TEXT, font=(FONT, 13, "bold")
            ).pack(anchor="w")
            tk.Label(
                empty,
                text=self.tr("完成第一次练习后，学习动态会显示在这里。"),
                bg=T.SURFACE,
                fg=T.MUTED,
                wraplength=T.px(520),
                justify="left",
            ).pack(anchor="w", pady=8)
            ttk.Button(
                empty,
                text=self.tr("开始第一次练习"),
                command=self.configure,
                style="Accent.TButton",
            ).pack(anchor="w")
        for record in list(reversed(history))[:6]:
            post = card_frame(feed, pad=14)
            post.pack(fill="x", pady=(0, 10))
            tk.Label(
                post,
                text=f"{name}  ·  {self._relative_time(record['date'])}",
                bg=T.SURFACE,
                fg=T.MUTED,
                font=TYPE_HINT,
            ).pack(anchor="w")
            tk.Label(
                post,
                text=self.tr(
                    "完成了 {0} · 正确率 {1}%", record["subject"], f"{record['accuracy']:.0f}"
                ),
                bg=T.SURFACE,
                fg=T.TEXT,
                font=TYPE_BODY,
                wraplength=T.px(520),
                justify="left",
            ).pack(anchor="w", pady=(6, 4))
            tk.Label(
                post,
                text=self.tr("{0} 道题", record["total"]),
                bg=T.SURFACE,
                fg=T.MUTED,
                font=TYPE_HINT,
            ).pack(anchor="w", pady=(0, 8))
            actions = tk.Frame(post, bg=T.SURFACE)
            actions.pack(anchor="w")
            self._text_button(actions, self.tr("查看详情"), self.history, bg=T.SURFACE).pack(
                side="left", padx=(0, 12)
            )
            subject_name = record["subject"].split(",")[0].strip()
            self._text_button(
                actions,
                self.tr("再练一次"),
                lambda value=subject_name: self.configure(value),
                bg=T.SURFACE,
            ).pack(side="left")
        search_shell = tk.Frame(rail, bg=T.SURFACE, highlightthickness=1, highlightbackground=T.BORDER)
        search_shell.pack(fill="x", pady=(0, 8))
        self.home_search = tk.StringVar()
        search = tk.Entry(
            search_shell,
            textvariable=self.home_search,
            bg=T.SURFACE,
            fg=T.TEXT,
            insertbackground=T.TEXT,
            relief="flat",
            font=TYPE_BODY,
        )
        search.pack(fill="x", padx=10, ipady=9)
        self._search_hint = self.tr("搜索题目、科目或错题")
        search.insert(0, self._search_hint)
        search.configure(fg=T.MUTED)

        def _focus_in(_e):
            if search.get() == self._search_hint:
                search.delete(0, "end")
                search.configure(fg=T.TEXT)

        def _focus_out(_e):
            if not search.get().strip():
                search.insert(0, self._search_hint)
                search.configure(fg=T.MUTED)

        search.bind("<FocusIn>", _focus_in)
        search.bind("<FocusOut>", _focus_out)
        search.bind("<KeyRelease>", self._filter_home_search)
        self.search_hits = tk.Frame(rail, bg=T.BG)
        self.search_hits.pack(fill="x", pady=(0, 12))
        tk.Label(rail, text=self.tr("学习进度"), bg=T.BG, fg=T.TEXT, font=(FONT, 13, "bold")).pack(
            anchor="w", pady=(4, 6)
        )
        tk.Label(
            rail,
            text=self.tr("综合正确率 {0} · 待复习 {1}", accuracy_text, len(wrong)),
            bg=T.BG,
            fg=T.MUTED,
            font=TYPE_HINT,
            wraplength=T.px(250),
            justify="left",
        ).pack(anchor="w")
        bar = ttk.Progressbar(
            rail, maximum=100, value=0 if accuracy_text == "—" else float(accuracy_text.strip("%"))
        )
        bar.pack(fill="x", pady=(8, 16))
        tk.Label(rail, text=self.tr("推荐练习"), bg=T.BG, fg=T.TEXT, font=(FONT, 13, "bold")).pack(
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
            tk.Label(row, text=subject, bg=T.SURFACE, fg=T.TEXT, font=(FONT, 12, "bold")).pack(
                anchor="w"
            )
            tk.Label(
                row,
                text=self.tr("{0} 道题", counts.get(subject, 0)),
                bg=T.SURFACE,
                fg=T.MUTED,
                font=TYPE_HINT,
            ).pack(anchor="w")
            got = subject_accuracy.get(subject)
            rate = f"{got[0] / got[1] * 100:.0f}%" if got and got[1] else "—"
            tk.Label(
                row,
                text=self.tr("最近正确率 {0}", rate),
                bg=T.SURFACE,
                fg=T.MUTED,
                font=TYPE_HINT,
            ).pack(anchor="w", pady=(4, 8))
            self._text_button(
                row, self.tr("开始练习"), lambda value=subject: self.configure(value), bg=T.SURFACE
            ).pack(anchor="w")
            self._subject_rows.append((subject.lower(), row))
            self._search_index.append(
                ("subject", subject, subject, lambda value=subject: self.configure(value))
            )
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
            ttk.Button(
                admin,
                text=self.tr("题库管理 / 上传图片"),
                command=self.manage_questions,
                style="Tool.TButton",
            ).pack(side="left", padx=(0, 8))
            ttk.Button(
                admin, text=self.tr("用户管理"), command=self.manage_users, style="Tool.TButton"
            ).pack(side="left")
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
        self.body.configure(padding=(T.px(T.SPACE_4), T.px(T.SPACE_4)))

        name = self.user["name"] if self.user else self.tr("访客")
        hour = datetime.now().hour
        greeting = (
            self.tr("早上好")
            if hour < 12
            else self.tr("下午好")
            if hour < 18
            else self.tr("晚上好")
        )
        separator = ", " if self.tr.language == "en" else "，"
        tk.Label(
            self.body,
            text=f"{greeting}{separator}{name}",
            bg=T.BG,
            fg=T.TEXT,
            font=(FONT, 24, "bold"),
        ).pack(anchor="w", pady=(0, T.px(T.SPACE_5)))

        history, data_error = [], ""
        try:
            progress = self.progress.load()
            history = progress.get("history") or []
        except DataError as exc:
            data_error = str(exc)
        try:
            plan = self.learning_plan.summary()
        except DataError as exc:
            plan = {
                "daily_goal": 20,
                "bank_kind": "public",
                "subject": None,
                "difficulty": None,
                "today": 0,
                "remaining": 20,
                "percent": 0,
                "streak": 0,
                "weekly": [],
            }
            data_error = data_error or str(exc)

        top = tk.Frame(self.body, bg=T.BG)
        # Fill the whole viewport: the body is now stretched by the Canvas
        # window item, so expand=True has real space to distribute.
        top.pack(fill="both", expand=True)
        top.rowconfigure(0, weight=1)
        left = tk.Frame(top, bg=T.BG)
        top.columnconfigure(0, weight=1, uniform="home_columns")
        top.columnconfigure(1, weight=1, uniform="home_columns")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, T.px(T.SPACE_3)))
        goal = card_frame(left, pad=T.SPACE_5)
        goal.pack(fill="x", anchor="n")
        goal_heading = tk.Frame(goal, bg=T.SURFACE)
        goal_heading.pack(fill="x")
        tk.Label(
            goal_heading,
            text=self.tr("今日目标"),
            bg=T.SURFACE,
            fg=T.TEXT,
            font=(FONT, 15, "bold"),
        ).pack(side="left")
        tk.Button(
            goal_heading,
            text="🔧",
            command=self.open_daily_plan_settings,
            bg=T.SURFACE,
            fg=T.MUTED,
            activebackground=T.HOVER,
            activeforeground=T.PRIMARY,
            relief="flat",
            bd=0,
            font=(FONT, 13),
            cursor="hand2",
            padx=T.px(7),
            pady=T.px(2),
        ).pack(side="right")
        bank_name = self.tr("个人题库") if plan["bank_kind"] == "personal" else self.tr("公共题库")
        subject_name = plan["subject"] or self.tr("随机科目")
        difficulty_name = plan["difficulty"] or self.tr("全部难度")
        tk.Label(
            goal,
            text=f"{bank_name} · {subject_name} · {difficulty_name}",
            bg=T.SURFACE,
            fg=T.MUTED,
            font=TYPE_HINT,
        ).pack(anchor="w", pady=(T.px(4), 0))
        score = tk.Frame(goal, bg=T.SURFACE)
        score.pack(anchor="w", pady=(T.px(16), T.px(2)))
        tk.Label(
            score,
            text=str(plan["today"]),
            bg=T.SURFACE,
            fg=T.PRIMARY,
            font=(FONT, 36, "bold"),
        ).pack(side="left")
        tk.Label(
            score,
            text=f" / {plan['daily_goal']} {self.tr('题')}",
            bg=T.SURFACE,
            fg=T.TEXT,
            font=(FONT, 22, "bold"),
        ).pack(side="left", pady=(T.px(10), 0))
        tk.Label(
            goal,
            text=self.tr("已完成 {0}%", f"{plan['percent']:.0f}"),
            bg=T.SURFACE,
            fg=T.TEXT,
            font=TYPE_BODY,
        ).pack(anchor="w", pady=(0, T.px(8)))
        progress_canvas = tk.Canvas(goal, height=T.px(18), bg=T.SURFACE, highlightthickness=0, bd=0)
        progress_canvas.pack(fill="x", pady=(0, T.px(20)))

        def draw_goal_bar(_event=None):
            progress_canvas.delete("all")
            width = max(progress_canvas.winfo_width(), T.px(20))
            top = T.px(2)
            bottom = max(progress_canvas.winfo_height(), T.px(18)) - T.px(2)
            progress_canvas.create_rectangle(0, top, width, bottom, fill=T.TRACK, outline="")
            progress_canvas.create_rectangle(
                0,
                top,
                width * plan["percent"] / 100,
                bottom,
                fill=T.PRIMARY,
                outline="",
            )

        progress_canvas.bind("<Configure>", draw_goal_bar)
        self._mock_action(
            goal,
            self.tr("继续今日练习"),
            self.start_daily_practice,
            True,
            padx=T.px(24),
            pady=T.px(12),
        ).pack(fill="x")

        side = tk.Frame(top, bg=T.BG)
        side.grid(row=0, column=1, sticky="nsew")
        streak = card_frame(side, pad=T.SPACE_5)
        streak.pack(fill="x", pady=(0, T.px(T.SPACE_3)))
        tk.Label(
            streak,
            text=self.tr("连续学习"),
            bg=T.SURFACE,
            fg=T.TEXT,
            font=(FONT, 14, "bold"),
        ).pack(anchor="w")
        tk.Label(
            streak,
            text=self.tr("{0} 天", plan["streak"]),
            bg=T.SURFACE,
            fg=T.SUCCESS_FG,
            font=(FONT, 30, "bold"),
        ).pack(anchor="w", pady=(T.px(7), T.px(6)))
        days = tk.Frame(streak, bg=T.SURFACE)
        days.pack(fill="x")
        day_names = self.tr("一 二 三 四 五 六 日").split()
        weekly = plan["weekly"][-7:]
        for index, label in enumerate(day_names):
            cell = tk.Frame(days, bg=T.SURFACE)
            cell.pack(side="left", expand=True)
            tk.Label(cell, text=label, bg=T.SURFACE, fg=T.MUTED, font=(FONT, 8)).pack()
            done = index < len(weekly) and weekly[index]["count"] > 0
            tk.Label(
                cell,
                text="●" if done else "○",
                bg=T.SURFACE,
                fg=T.SUCCESS_FG if done else T.PRIMARY if index == len(day_names) - 1 else T.MUTED,
                font=(FONT, 15),
            ).pack()

        ai_card = card_frame(side, pad=T.SPACE_5)
        ai_card.pack(fill="both", expand=True)
        self._build_home_ai(ai_card)

        recent = card_frame(left, pad=T.SPACE_5)
        recent.pack(fill="both", expand=True, pady=(T.px(T.SPACE_3), 0))
        tk.Label(
            recent,
            text=self.tr("最近学习"),
            bg=T.SURFACE,
            fg=T.TEXT,
            font=(FONT, 14, "bold"),
        ).pack(anchor="w", pady=(0, T.px(8)))
        if history:
            for record in list(reversed(history))[:5]:
                row = tk.Frame(recent, bg=T.SURFACE)
                row.pack(fill="x", pady=T.px(3))
                tk.Label(
                    row,
                    text=str(record["subject"]),
                    bg=T.SURFACE,
                    fg=T.TEXT,
                    font=(FONT, 10, "bold"),
                    anchor="w",
                ).pack(side="left", fill="x", expand=True)
                tk.Label(
                    row,
                    text=self.tr("{0} 题", record["total"]),
                    bg=T.SURFACE,
                    fg=T.TEXT,
                    font=TYPE_HINT,
                ).pack(side="left", padx=T.px(8))
                tk.Label(
                    row,
                    text=str(record["date"])[:10],
                    bg=T.SURFACE,
                    fg=T.MUTED,
                    font=TYPE_HINT,
                ).pack(side="right")
                tk.Frame(recent, bg=T.BORDER, height=T.px(1)).pack(fill="x")
        else:
            # The card now grows with the viewport: centre the empty state so
            # the extra height reads as deliberate whitespace, not a bug.
            tk.Frame(recent, bg=T.SURFACE).pack(fill="both", expand=True)
            self._fit_wrap(tk.Label(
                recent,
                text=self.tr("还没有学习记录，完成第一次练习后会显示在这里。"),
                bg=T.SURFACE,
                fg=T.MUTED,
                font=T.TYPE_BODY_LARGE,
                justify="left",
                anchor="w",
            )).pack(fill="x", pady=(0, T.px(T.SPACE_4)))
            self._mock_action(
                recent,
                self.tr("开始第一次练习"),
                lambda: self.configure(bank_kind="public"),
                True,
            ).pack(anchor="w")
            tk.Frame(recent, bg=T.SURFACE).pack(fill="both", expand=True)
        if data_error:
            tk.Label(
                self.body,
                text=data_error,
                bg=T.BG,
                fg=T.ERROR,
                font=TYPE_HINT,
            ).pack(anchor="w", pady=(T.px(8), 0))

    def ask_home_ai(self):
        message = self.home_ai_input.get("1.0", "end-1c").strip()
        if message == self.home_ai_placeholder:
            message = ""
        self._request_ai(message, self.home_ai_button, self.home_ai_reply)
        if message:
            self.home_ai_input.delete("1.0", "end")

    def _build_home_ai(self, card):
        """Ask AI card: header, tinted composer, portrait / answer surface.

        The Q-version character is the idle illustration: it fills the answer
        area while no reply exists (up to 320 design px, scaled to the room the
        card really has) and hands that space to the answer afterwards. Both
        blocks use the primary family instead of the neutral grey of the first
        layout, which read as a foreign colour next to the blue accent.
        """
        head = tk.Frame(card, bg=T.SURFACE)
        head.pack(fill="x")
        dot = tk.Canvas(
            head, width=T.px(8), height=T.px(8), bg=T.SURFACE,
            highlightthickness=0, bd=0, takefocus=0,
        )
        dot.create_oval(0, 0, T.px(8), T.px(8), fill=T.PRIMARY, outline="")
        dot.pack(side="left", padx=(0, T.px(T.SPACE_2)))
        tk.Label(
            head, text=self.tr("问问 AI"), bg=T.SURFACE, fg=T.TEXT,
            font=T.TYPE_HEADING, anchor="w",
        ).pack(side="left")

        composer = modern.SoftPanel(
            card, fill=T.AI_INPUT_BG, edge=T.AI_INPUT_EDGE, padding=T.SPACE_3,
        )
        composer.pack(fill="x", pady=(T.px(T.SPACE_3), 0))
        row = tk.Frame(composer.content, bg=T.AI_INPUT_BG)
        row.pack(fill="x")
        self.home_ai_input = tk.Text(
            row, height=2, width=1, wrap="word",
            bg=T.AI_INPUT_BG, fg=T.TEXT, insertbackground=T.PRIMARY,
            relief="flat", bd=0, highlightthickness=0, padx=0, pady=0,
            font=T.TYPE_BODY,
        )
        self.home_ai_input.pack(side="left", fill="both", expand=True)
        placeholder = self.tr("请输入你的学习问题……")
        self.home_ai_placeholder = placeholder
        self.home_ai_input.insert("1.0", placeholder)
        self.home_ai_input.configure(fg=T.TEXT_MUTED)

        def focus_input(_event):
            # 3px primary glow is approximated by a primary hairline + tinted fill.
            composer.set_edge(T.PRIMARY)
            if self.home_ai_input.get("1.0", "end-1c") == placeholder:
                self.home_ai_input.delete("1.0", "end")
                self.home_ai_input.configure(fg=T.TEXT)

        def restore_input(_event):
            composer.set_edge(T.AI_INPUT_EDGE)
            if not self.home_ai_input.get("1.0", "end-1c").strip():
                self.home_ai_input.insert("1.0", placeholder)
                self.home_ai_input.configure(fg=T.TEXT_MUTED)

        self.home_ai_input.bind("<FocusIn>", focus_input)
        self.home_ai_input.bind("<FocusOut>", restore_input)
        self.home_ai_input.bind("<Return>", self._home_ai_return)

        self.home_ai_button = modern.SoftButton(
            row, text=self.tr("发送"), command=self.ask_home_ai,
            variant="primary", width=T.px(88),
        )
        self.home_ai_button.pack(
            side="right", anchor="s", padx=(T.px(T.SPACE_2), 0)
        )
        tk.Label(
            composer.content, text=self.tr("Enter 发送 · Shift+Enter 换行"),
            bg=T.AI_INPUT_BG, fg=T.TEXT_SECONDARY,
            font=T.TYPE_CAPTION, anchor="w",
        ).pack(fill="x", pady=(T.px(T.SPACE_1), 0))

        reply_panel = modern.SoftPanel(
            card, fill=T.AI_REPLY_BG, edge=T.AI_REPLY_EDGE, padding=T.SPACE_4,
        )
        reply_panel.pack(fill="both", expand=True, pady=(T.px(T.SPACE_3), 0))

        self._home_ai_idle = tk.Frame(reply_panel.content, bg=T.AI_REPLY_BG)
        self._home_ai_idle.pack(fill="both", expand=True)
        # Keep the portrait and its greeting together as one centred block.
        # Packing the canvas with expand pushed the caption to the very bottom
        # of a tall card, far away from the character it belongs to.
        group = tk.Frame(self._home_ai_idle, bg=T.AI_REPLY_BG)
        group.place(relx=0.5, rely=0.5, anchor="center")
        self._home_mascot = tk.Canvas(
            group, width=T.px(120), height=T.px(120), bg=T.AI_REPLY_BG,
            highlightthickness=0, bd=0, takefocus=0,
        )
        self._home_mascot.pack()
        self._home_mascot.bind("<Configure>", self._draw_home_mascot)
        self._home_ai_hint = tk.Label(
            group,
            text=self.tr("问我任何学习问题，我会给出简短提示。"),
            bg=T.AI_REPLY_BG, fg=T.TEXT_SECONDARY,
            font=T.TYPE_CAPTION, justify="center", anchor="center",
        )
        self._home_ai_hint.pack(pady=(T.px(T.SPACE_2), 0))
        self._home_ai_idle.bind("<Configure>", self._resize_home_idle)

        answer = tk.Frame(reply_panel.content, bg=T.AI_REPLY_BG)
        self._home_ai_answer = answer
        tk.Label(
            answer, text=self.tr("AI 提示"), bg=T.AI_REPLY_BG, fg=T.PRIMARY,
            font=T.TYPE_CAPTION, anchor="w",
        ).pack(anchor="w", pady=(0, T.px(T.SPACE_1)))
        self.home_ai_reply = AssistantReply(
            answer, text="", height=4, bg=T.AI_REPLY_BG, fg=T.TEXT, font=T.TYPE_BODY,
            wrap="word", width=1, relief="flat", bd=0, highlightthickness=0,
            padx=0, pady=0,
        )
        self.home_ai_reply.pack(fill="both", expand=True)
        self.home_ai_reply._on_text = self._on_home_ai_text

    def _home_ai_return(self, event):
        """Enter sends, Shift+Enter keeps the default newline behaviour."""
        if event.state & 0x0001:
            return None
        self.ask_home_ai()
        return "break"

    def _resize_home_idle(self, event):
        """Fit portrait + caption into the reply area, dropping the caption if tight."""
        canvas = getattr(self, "_home_mascot", None)
        hint = getattr(self, "_home_ai_hint", None)
        if canvas is None or hint is None or not canvas.winfo_exists():
            return
        pad = T.px(T.SPACE_2)
        available = max(event.height - pad, T.px(64))
        limit = max(event.width - pad, T.px(140))
        hint.configure(wraplength=min(limit, T.px(320)))
        hint_height = hint.winfo_reqheight() + T.px(T.SPACE_2)
        # Keep the caption only when the portrait can stay reasonably large;
        # a one-line greeting under a speck of a character looks worse than none.
        keep_hint = available - hint_height >= T.px(120)
        if keep_hint and not hint.winfo_manager():
            hint.pack(pady=(T.px(T.SPACE_2), 0))
        elif not keep_hint and hint.winfo_manager():
            hint.pack_forget()
        room = available - (hint_height if keep_hint else 0)
        size = max(min(limit, room, T.px(320)), T.px(64))
        if abs(int(canvas.cget("width")) - size) > 1:
            canvas.configure(width=size, height=size)
        self._draw_home_mascot()

    def _home_mascot_base(self):
        base = self.__dict__.get("_mascot_base")
        if base is None:
            try:
                base = tk.PhotoImage(
                    master=self.root,
                    file=str(self.project_root / "AI-assistant-icon.png"),
                )
            except (tk.TclError, OSError):
                base = False
            self._mascot_base = base
        return base or None

    def _draw_home_mascot(self, _event=None):
        """Scale the Q-version portrait to the room the card actually has."""
        canvas = getattr(self, "_home_mascot", None)
        if canvas is None or not canvas.winfo_exists():
            return
        width, height = canvas.winfo_width(), canvas.winfo_height()
        canvas.delete("all")
        if width <= 4 or height <= 4:
            return
        base = self._home_mascot_base()
        target = min(width - T.px(T.SPACE_2), height, T.px(320))
        if base is None or target < T.px(40):
            canvas.create_text(
                width / 2, height / 2, text="✦", fill=T.PRIMARY,
                font=(FONT, max(12, int(target / 4)), "bold"),
            )
            return
        factor = max(1, int(round(max(base.width(), base.height()) / target)))
        cache = self.__dict__.setdefault("_mascot_cache", {})
        photo = cache.get(factor)
        if photo is None:
            photo = base.subsample(factor)
            cache[factor] = photo
        canvas.create_image(width / 2, height / 2, image=photo)

    def _on_home_ai_text(self, text):
        """Swap the idle portrait for the answer once a reply exists."""
        idle = getattr(self, "_home_ai_idle", None)
        answer = getattr(self, "_home_ai_answer", None)
        if idle is None or answer is None:
            return
        if not idle.winfo_exists() or not answer.winfo_exists():
            return
        wants_answer = bool(text.strip())
        showing_answer = bool(answer.winfo_manager())
        if wants_answer and not showing_answer:
            idle.pack_forget()
            answer.pack(fill="both", expand=True)
        elif not wants_answer and showing_answer:
            answer.pack_forget()
            idle.pack(fill="both", expand=True)
            self._draw_home_mascot()

    def _request_ai(self, message, button, output, once_key=None):
        if once_key is not None and (once_key in self._ai_asked or once_key in self._ai_pending):
            return
        if not message.strip():
            output.configure(text=self.tr("请输入想问的问题。"), fg=T.ERROR)
            return
        if once_key is not None:
            self._ai_pending.add(once_key)
        button.state(["disabled"])
        button.configure(text=self.tr("AI 思考中…"))
        output.configure(text=self.tr("正在连接 AI 服务…"), fg=T.MUTED)

        def worker():
            try:
                answer = self.ai_assistant.ask(message, self.tr.language)
                error = None
            except (ValueError, OSError) as exc:
                answer, error = "", str(exc)

            def finish():
                if once_key is not None:
                    self._ai_pending.discard(once_key)
                if not button.winfo_exists() or not output.winfo_exists():
                    return
                if error:
                    output.configure(text=self.tr(error), fg=T.ERROR)
                    button.state(["!disabled"])
                    button.configure(text=self.tr("问问 AI") if once_key else self.tr("发送"))
                    return
                output.configure(text=answer, fg=T.TEXT)
                if once_key is not None:
                    self._ai_asked.add(once_key)
                    button.configure(text=self.tr("本题已询问"))
                    button.state(["disabled"])
                else:
                    button.configure(text=self.tr("发送"))
                    button.state(["!disabled"])

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def set_daily_goal(self):
        self.open_daily_plan_settings()

    def open_daily_plan_settings(self):
        try:
            plan = self.learning_plan.load()
            self.load_bank()
        except (DataError, ValueError) as exc:
            messagebox.showerror(self.tr("无法打开设置"), self.tr(str(exc)), parent=self.root)
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(self.tr("调整每日目标"))
        dialog.configure(bg=T.BG)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        host = card_frame(dialog, pad=22)
        host.pack(fill="both", expand=True, padx=18, pady=18)
        tk.Label(
            host,
            text=self.tr("调整每日目标"),
            bg=T.SURFACE,
            fg=T.TEXT,
            font=(FONT, 17, "bold"),
        ).pack(anchor="w", pady=(0, 14))

        public_label = self.tr("公共题库")
        personal_label = self.tr("个人题库")
        available_banks = [public_label] + ([personal_label] if self.user else [])
        bank_var = tk.StringVar(
            value=(
                personal_label if self.user and plan["bank_kind"] == "personal" else public_label
            )
        )
        subject_var = tk.StringVar()
        difficulty_var = tk.StringVar()
        goal_var = tk.StringVar(value=str(plan["daily_goal"]))

        def field(label, variable, values):
            tk.Label(host, text=label, bg=T.SURFACE, fg=T.TEXT, font=T.TYPE_BODY).pack(
                anchor="w", pady=(T.px(T.SPACE_2), 0)
            )
            box = modern.Dropdown(host, textvariable=variable, values=values)
            box.pack(fill="x", pady=(T.px(T.FIELD_GAP), 0))
            return box

        bank_box = field(self.tr("题库"), bank_var, available_banks)
        subject_box = field(self.tr("科目"), subject_var, [])
        difficulty_box = field(self.tr("难度"), difficulty_var, [])
        tk.Label(host, text=self.tr("每日题量"), bg=T.SURFACE, fg=T.TEXT, font=T.TYPE_BODY).pack(
            anchor="w", pady=(T.px(T.GROUP_GAP), 0)
        )
        modern.Stepper(host, textvariable=goal_var, maximum=500, minimum=1).pack(
            fill="x", pady=(T.px(T.FIELD_GAP), 0)
        )

        random_subject = self.tr("随机科目")
        all_difficulties = self.tr("全部难度")

        def selected_questions():
            return (
                self.personal_questions
                if bank_var.get() == personal_label
                else self.public_questions
            )

        def refresh_difficulties(_event=None, preferred=None):
            questions = selected_questions()
            subject = None if subject_var.get() == random_subject else subject_var.get()
            values = [all_difficulties] + sorted(
                {q.difficulty for q in questions if subject is None or q.subject == subject}
            )
            difficulty_box["values"] = values
            wanted = preferred if preferred in values else all_difficulties
            difficulty_var.set(wanted)

        def refresh_subjects(_event=None, preferred_subject=None, preferred_difficulty=None):
            values = [random_subject] + sorted({q.subject for q in selected_questions()})
            subject_box["values"] = values
            wanted = preferred_subject if preferred_subject in values else random_subject
            subject_var.set(wanted)
            refresh_difficulties(preferred=preferred_difficulty)

        bank_box.bind("<<ComboboxSelected>>", refresh_subjects)
        subject_box.bind("<<ComboboxSelected>>", refresh_difficulties)
        refresh_subjects(
            preferred_subject=plan["subject"] or random_subject,
            preferred_difficulty=plan["difficulty"] or all_difficulties,
        )

        actions = tk.Frame(host, bg=T.SURFACE)
        actions.pack(fill="x", pady=(20, 0))

        def save():
            try:
                goal = int(goal_var.get())
                self.learning_plan.set_settings(
                    "personal" if bank_var.get() == personal_label else "public",
                    None if subject_var.get() == random_subject else subject_var.get(),
                    None if difficulty_var.get() == all_difficulties else difficulty_var.get(),
                    goal,
                )
            except (DataError, ValueError) as exc:
                messagebox.showerror(self.tr("保存失败"), self.tr(str(exc)), parent=dialog)
                return
            dialog.destroy()
            self.home()

        ttk.Button(actions, text=self.tr("保存设置"), command=save, style="Accent.TButton").pack(
            side="left"
        )
        ttk.Button(
            actions, text=self.tr("取消"), command=dialog.destroy, style="Tool.TButton"
        ).pack(side="right")
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + max((self.root.winfo_width() - dialog.winfo_width()) // 2, 0)
        y = self.root.winfo_rooty() + max(
            (self.root.winfo_height() - dialog.winfo_height()) // 2, 0
        )
        dialog.geometry(f"+{x}+{y}")

    def start_daily_practice(self):
        try:
            plan = self.learning_plan.summary()
            if plan["bank_kind"] == "personal" and not self.user:
                raise ValueError(self.tr("请先登录账户，再导入或使用个人题库。"))
            if plan["remaining"] <= 0:
                messagebox.showinfo(
                    self.tr("今日目标"),
                    self.tr("今天的目标已经完成，明天继续保持！"),
                    parent=self.root,
                )
                return
            self.load_bank()
            questions = (
                self.personal_questions
                if plan["bank_kind"] == "personal"
                else self.public_questions
            )
            selected = select_questions(
                questions,
                subject=plan["subject"],
                difficulty=plan["difficulty"],
                count=plan["remaining"],
            )
        except (DataError, ValueError) as exc:
            messagebox.showerror(
                self.tr("无法开始练习"),
                self.tr("每日目标没有匹配题目，请点击扳手调整设置。\n{0}", exc),
                parent=self.root,
            )
            return
        self.questions = questions
        self._practice_bank_kind = plan["bank_kind"]
        self._last_filters = {
            "subject": plan["subject"],
            "topic": None,
            "difficulty": plan["difficulty"],
            "count": plan["remaining"],
            "bank_kind": plan["bank_kind"],
        }
        self.start_quiz(selected)

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
            bg=T.SURFACE,
            fg=T.TEXT,
            font=(FONT, 16, "bold"),
        ).pack(anchor="w")
        tk.Label(
            intro,
            text=self.tr(
                "个人题库仅属于当前账户，不会修改管理员维护的公共题库。支持 JSON 和 CSV；先校验预览，确认后才会保存。"
            ),
            bg=T.SURFACE,
            fg=T.MUTED,
            font=TYPE_BODY,
            wraplength=T.px(760),
            justify="left",
        ).pack(anchor="w", pady=(6, 14))
        workflow = tk.Frame(intro, bg=T.SURFACE)
        workflow.pack(fill="x")
        self.import_steps = []
        for number, title, hint in (
            ("1", self.tr("上传文件"), self.tr("选择 JSON 或 CSV")),
            ("2", self.tr("自动校验"), self.tr("检查格式与重复题")),
            ("3", self.tr("预览题目"), self.tr("查看有效与错误项目")),
            ("4", self.tr("确认合并"), self.tr("写入当前个人题库")),
        ):
            step = tk.Frame(workflow, bg=T.HOVER, padx=12, pady=10)
            step.pack(side="left", fill="x", expand=True, padx=(0, 8))
            badge = tk.Label(
                step,
                text=number,
                width=2,
                bg=T.PRIMARY if number == "1" else T.TRACK,
                fg=T.ON_PRIMARY if number == "1" else T.MUTED,
                font=(FONT, 10, "bold"),
            )
            badge.pack(anchor="w")
            title_label = tk.Label(
                step,
                text=title,
                bg=T.HOVER,
                fg=T.TEXT,
                font=(FONT, 10, "bold"),
            )
            title_label.pack(anchor="w", pady=(5, 1))
            tk.Label(step, text=hint, bg=T.HOVER, fg=T.MUTED, font=(FONT, 8)).pack(anchor="w")
            self.import_steps.append((badge, title_label))

        upload_zone = tk.Frame(
            self.body,
            bg=T.SURFACE,
            highlightthickness=2,
            highlightbackground=T.PRIMARY,
            padx=18,
            pady=16,
        )
        upload_zone.pack(fill="x", pady=(0, 14))
        upload_copy = tk.Frame(upload_zone, bg=T.SURFACE)
        upload_copy.pack(side="left", fill="x", expand=True)
        tk.Label(
            upload_copy,
            text=self.tr("选择题库文件开始导入"),
            bg=T.SURFACE,
            fg=T.TEXT,
            font=(FONT, 12, "bold"),
        ).pack(anchor="w")
        tk.Label(
            upload_copy,
            text=self.tr("支持 .json 与 .csv；文件会先校验，不会直接覆盖现有题库。"),
            bg=T.SURFACE,
            fg=T.MUTED,
            font=TYPE_HINT,
        ).pack(anchor="w", pady=(4, 0))
        actions = tk.Frame(upload_zone, bg=T.SURFACE)
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
        self.import_table = ttk.Treeview(self.body, columns=columns, show="headings", height=12)
        for key, title, width in (
            ("row", "#", 55),
            ("id", self.tr("题目 ID"), 130),
            ("status", self.tr("状态"), 100),
            ("message", self.tr("结果 / 错误原因"), 520),
        ):
            self.import_table.heading(key, text=title)
            self.import_table.column(
                key, width=T.px(width), anchor="w", stretch=key == "message"
            )
        self.import_table.pack(fill="both", expand=True)
        self.import_confirm = ttk.Button(
            self.body,
            text=self.tr("确认导入有效题目"),
            command=self.confirm_personal_import,
            style="Accent.TButton",
        )
        self.import_confirm.pack(anchor="w", pady=(12, 4))
        self.import_confirm.state(["disabled"])

    def personal_bank_page(self, bank_kind="personal"):
        """Import workflow matching the approved right-hand mock-up."""
        if not self.user:
            messagebox.showinfo(
                self.tr("权限提示"),
                self.tr("请先登录账户，再导入或使用个人题库。"),
                parent=self.root,
            )
            return
        if bank_kind == "public" and not self.check_admin():
            return
        if bank_kind != "public" and not self.check_session():
            return
        self.import_bank_kind = bank_kind
        self._nav_key = "questions"

        def return_to_bank():
            self._show_question_bank(bank_kind)

        self.clear(self.tr("题库管理"), show_heading=False, back=return_to_bank)
        self.chrome.pack_forget()
        self.rule.pack_forget()
        self.body.configure(padding=(T.px(T.SPACE_4), T.px(T.SPACE_4)))
        self.load_bank()
        self.import_preview = None

        tk.Label(
            self.body,
            text=self.tr("公共题库 · 批量导入" if bank_kind == "public" else "个人题库 · 批量导入"),
            bg=T.BG,
            fg=T.TEXT,
            font=(FONT, 24, "bold"),
        ).pack(anchor="w", pady=(0, T.px(T.SPACE_5)))

        workflow = tk.Frame(self.body, bg=T.BG)
        workflow.pack(fill="x", pady=(0, 16))
        self.import_steps = []
        step_data = (
            ("1", self.tr("选择文件")),
            ("2", self.tr("数据校验")),
            ("3", self.tr("预览确认")),
            ("4", self.tr("合并完成")),
        )
        for index, (number, title) in enumerate(step_data):
            cell = tk.Frame(workflow, bg=T.BG)
            cell.pack(side="left", fill="x", expand=True)
            badge = tk.Label(
                cell,
                text=number,
                width=2,
                height=1,
                bg=T.SELECTED_BG if index < 2 else T.PRIMARY if index == 2 else T.HOVER,
                fg="#FFFFFF" if index <= 2 else T.MUTED,
                font=(FONT, 13, "bold"),
                padx=5,
                pady=5,
                highlightthickness=1,
                highlightbackground=T.PRIMARY if index <= 2 else T.MUTED,
            )
            badge.pack()
            title_label = tk.Label(
                cell,
                text=title,
                bg=T.BG,
                fg=T.TEXT if index <= 2 else T.MUTED,
                font=(FONT, 10),
            )
            title_label.pack(pady=(6, 0))
            self.import_steps.append((badge, title_label))

        file_card = tk.Frame(
            self.body,
            bg=T.SURFACE,
            padx=16,
            pady=15,
            highlightthickness=1,
            highlightbackground=T.BORDER,
            cursor="hand2",
        )
        file_card.pack(fill="x", pady=(0, 14))
        self.import_file_name = tk.Label(
            file_card,
            text=self.tr("▤  选择 JSON / CSV 文件"),
            bg=T.SURFACE,
            fg=T.TEXT,
            font=(FONT, 12),
            cursor="hand2",
        )
        self.import_file_name.pack(side="left")
        self.import_file_total = tk.Label(
            file_card,
            text=self.tr("点击选择文件"),
            bg=T.SURFACE,
            fg=T.MUTED,
            font=TYPE_HINT,
            cursor="hand2",
        )
        self.import_file_total.pack(side="right")
        bind_whole(file_card, self.choose_import_file)

        stats = tk.Frame(self.body, bg=T.BG)
        stats.pack(fill="x", pady=(0, 14))
        self.import_stat_labels = {}
        for key, title, color in (
            ("valid", self.tr("有效"), T.SUCCESS_FG),
            ("warning", self.tr("警告"), T.WARNING),
            ("error", self.tr("错误"), T.ERROR),
            ("duplicate", self.tr("重复"), T.MUTED),
        ):
            card = card_frame(stats, pad=14)
            card.pack(side="left", fill="x", expand=True, padx=(0, 10))
            tk.Label(card, text=title, bg=T.SURFACE, fg=color, font=TYPE_HINT).pack(anchor="w")
            value = tk.Label(card, text="0", bg=T.SURFACE, fg=color, font=(FONT, 22, "bold"))
            value.pack(anchor="w", pady=(4, 0))
            self.import_stat_labels[key] = value

        columns = ("status", "id", "subject", "topic", "difficulty", "question")
        self.import_table = ttk.Treeview(self.body, columns=columns, show="headings", height=9)
        for key, title, width in (
            ("status", self.tr("状态"), 95),
            ("id", "ID", 90),
            ("subject", self.tr("学科"), 105),
            ("topic", self.tr("主题"), 120),
            ("difficulty", self.tr("难度"), 90),
            ("question", self.tr("题目"), 390),
        ):
            self.import_table.heading(key, text=title)
            self.import_table.column(
                key, width=T.px(width), anchor="w", stretch=key == "question"
            )
        self.import_table.pack(fill="both", expand=True, pady=(0, 14))
        self.import_table.tag_configure("valid", foreground=T.SUCCESS_FG)
        self.import_table.tag_configure("duplicate", foreground=T.MUTED)
        self.import_table.tag_configure("error", foreground=T.ERROR)

        permissions = tk.Frame(self.body, bg=T.BG)
        permissions.pack(fill="x")
        tk.Label(
            permissions,
            text=self.tr("导入到公共题库，仅管理员可执行。")
            if bank_kind == "public"
            else self.tr("导入到个人题库，仅当前账户可见。"),
            bg=T.BG,
            fg=T.MUTED,
            font=TYPE_BODY,
        ).pack(anchor="w")

        footer = tk.Frame(self.body, bg=T.BG)
        footer.pack(fill="x", pady=(18, 0))
        self.import_summary = tk.Label(
            footer,
            text=self.tr("ⓘ 错误记录不会导入题库"),
            bg=T.BG,
            fg=T.MUTED,
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
            self.tr("返回题库中心"),
            return_to_bank,
            False,
            padx=14,
            pady=10,
        ).pack(side="right", padx=(0, 10))

    def _set_import_step(self, active):
        for index, (badge, title) in enumerate(getattr(self, "import_steps", []), 1):
            selected = index <= active
            badge.configure(
                bg=T.PRIMARY if selected else T.TRACK,
                fg=T.ON_PRIMARY if selected else T.MUTED,
            )
            title.configure(fg=T.TEXT if selected else T.MUTED)

    def choose_import_file(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title=self.tr("选择题库文件"),
            filetypes=(("JSON / CSV", "*.json *.csv"), ("JSON", "*.json"), ("CSV", "*.csv")),
        )
        if not path:
            return
        try:
            preview = self._question_import_service().preview(path)
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
        self.import_summary.configure(text=self.tr("ⓘ 错误记录不会导入题库，可下载校验报告"))
        self.import_confirm.configure(
            text=self.tr("合并 {0} 道有效题目", len(preview.valid)),
            bg=T.PRIMARY if preview.valid else T.PRIMARY_DISABLED,
        )

    def confirm_personal_import(self):
        preview = getattr(self, "import_preview", None)
        if not preview or not preview.valid:
            return
        if not messagebox.askyesno(
            self.tr("确认导入"),
            self.tr(
                "将 {0} 道有效题目加入公共题库？"
                if self.import_bank_kind == "public"
                else "将 {0} 道有效题目加入当前账户的个人题库？",
                len(preview.valid),
            ),
            parent=self.root,
        ):
            return
        try:
            added = self._question_import_service().confirm(preview)
        except (DataError, ValueError) as exc:
            messagebox.showerror(self.tr("导入失败"), self.tr(str(exc)), parent=self.root)
            return
        messagebox.showinfo(
            self.tr("导入完成"),
            self.tr("已导入 {0} 道题；重复题目保持跳过。", len(added)),
            parent=self.root,
        )
        self.personal_bank_page(self.import_bank_kind)

    def _show_question_bank(self, bank_kind):
        self.editor = EditorPage(self, mode=bank_kind)
        self.editor.show_list()

    def _question_import_service(self):
        if getattr(self, "import_bank_kind", "personal") == "public":
            repository = QuestionEditor(
                self.bank.folder, lambda: self.auth.require_admin(self.user)
            )
            return QuestionImportService(repository, [])
        return QuestionImportService(self.personal_bank, self.public_questions)

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
            tk.Label(host, text=self.tr("没有匹配结果"), bg=T.BG, fg=T.MUTED, font=TYPE_HINT).pack(
                anchor="w"
            )
            return
        for kind, _hay, label, action in hits:
            tag = {
                "subject": self.tr("科目"),
                "question": self.tr("题目"),
                "wrong": self.tr("错题"),
            }.get(kind, kind)
            line = tk.Button(
                host,
                text=f"{tag} · {label[:48]}",
                command=action,
                bg=T.SURFACE,
                fg=self._native_button_ink(T.TEXT),
                activebackground=T.HOVER,
                activeforeground=self._native_button_ink(T.TEXT),
                relief="flat",
                bd=0,
                anchor="w",
                padx=10,
                pady=8,
                wraplength=T.px(240),
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
                card.configure(highlightbackground=T.PRIMARY, highlightthickness=2, bg=T.SELECTED_BG)
            else:
                detail.pack_forget()
                card.configure(highlightbackground=T.BORDER, highlightthickness=1, bg=T.SURFACE)
        self._expanded_subject = None if current == name else name

    def configure(self, subject=None, bank_kind="public"):
        if not self.check_session():
            return
        self._nav_key = "practice"
        if bank_kind == "personal" and not self.user:
            self.personal_bank_page()
            return
        self.load_bank()
        self.questions = (
            self.personal_questions if bank_kind == "personal" else self.public_questions
        )
        self._practice_bank_kind = bank_kind
        self.clear(self.tr("配置练习"), show_heading=False)
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

        card = modern.SoftCard(self.body)
        # Fill the viewport instead of leaving a large dead band below a short
        # form; a flexible spacer pushes the footer to the bottom of the card.
        card.pack(fill="both", expand=True, pady=(T.px(T.SPACE_2), T.px(T.SPACE_5)))
        host = card.content

        header = tk.Frame(host, bg=T.SURFACE)
        header.pack(fill="x", pady=(0, T.px(T.SPACE_5)))
        tk.Label(
            header, text=self.tr("练习设置"), bg=T.SURFACE, fg=T.TEXT,
            font=T.TYPE_HEADING, anchor="w",
        ).pack(side="left")
        self.config_summary = tk.Label(
            header, text="", bg=T.SURFACE, fg=T.TEXT_MUTED,
            font=T.TYPE_CAPTION, anchor="e",
        )
        self.config_summary.pack(side="right")

        tk.Label(host, text=self.tr("学科"), bg=T.SURFACE, fg=T.TEXT,
                 font=T.TYPE_HEADING, anchor="w").pack(fill="x")
        picker = tk.Frame(host, bg=T.SURFACE)
        picker.pack(fill="x", pady=(T.px(T.FIELD_GAP), 0))
        counts = {name: sum(q.subject == name for q in self.questions) for name in subjects}
        self._subject_cards = []
        for index, name in enumerate(subjects):
            item = modern.SubjectCard(
                picker,
                name,
                self.tr("{0} 道题", counts[name]),
                command=lambda value=name: self._select_subject(value),
            )
            item.grid(
                row=index // 3, column=index % 3, sticky="nsew",
                padx=(0, T.px(T.SPACE_2)), pady=T.px(T.SPACE_1),
            )
            picker.columnconfigure(index % 3, weight=1, uniform="subjects")
            self._subject_cards.append((item, name))

        # Two-column field grid: topic + difficulty, time limit + question count.
        grid = tk.Frame(host, bg=T.SURFACE)
        grid.pack(fill="x", pady=(T.px(T.GROUP_GAP), 0))
        grid.columnconfigure(0, weight=1, uniform="columns")
        grid.columnconfigure(1, weight=1, uniform="columns")

        def column(row, col, title, caption=None):
            box = tk.Frame(grid, bg=T.SURFACE)
            box.grid(
                row=row, column=col, sticky="nsew",
                padx=(0 if col == 0 else T.px(T.SPACE_2),
                      T.px(T.SPACE_2) if col == 0 else 0),
                pady=(T.px(T.GROUP_GAP), 0) if row else 0,
            )
            def fit(event):
                widget = event.widget
                target = max(event.width - T.px(T.SPACE_1), 1)
                try:
                    if widget.cget("wraplength") != target:
                        widget.configure(wraplength=target)
                except tk.TclError:
                    pass

            title_label = tk.Label(
                box, text=title, bg=T.SURFACE, fg=T.TEXT,
                font=T.TYPE_HEADING, anchor="w", justify="left",
                wraplength=T.px(280),
            )
            title_label.pack(fill="x")
            title_label.bind("<Configure>", fit)
            if caption:
                caption_label = tk.Label(
                    box, text=caption, bg=T.SURFACE, fg=T.TEXT_MUTED,
                    font=T.TYPE_CAPTION, anchor="w", justify="left",
                    wraplength=T.px(280),
                )
                caption_label.pack(fill="x", pady=(T.px(T.SPACE_1), 0))
                caption_label.bind("<Configure>", fit)
            return box

        topic_col = column(0, 0, self.tr("主题"))
        self.topic_box = modern.Dropdown(topic_col, textvariable=self.topic, values=[])
        self.topic_box.pack(fill="x", pady=(T.px(T.FIELD_GAP), 0))
        self.topic_box.bind("<<ComboboxSelected>>", self.refresh_difficulties)

        difficulty_col = column(0, 1, self.tr("难度"))
        self.difficulty_chips = modern.Segmented(
            difficulty_col,
            variable=self.difficulty,
            on_change=lambda _value: self.show_count(),
        )
        self.difficulty_chips.pack(fill="x", pady=(T.px(T.FIELD_GAP), 0))
        # Plain data holder: the visible control is the Segmented widget, so no
        # native Combobox is instantiated anywhere in the redesigned pages.
        self.difficulty_box = {"values": ()}

        limit_col = column(1, 0, self.tr("每轮限时（秒，0 表示不限时）"))
        self.timer_box = modern.Stepper(
            limit_col, textvariable=self.timer_seconds, maximum=86400, minimum=0
        )
        self.timer_box.pack(fill="x", pady=(T.px(T.FIELD_GAP), 0))
        self.timer_box.wheel_guard = lambda: self.display.get("wheel_controls", False)

        count_col = column(
            1, 1, self.tr("题目数量（不足时使用所有匹配题目；顺序随机）")
        )
        self.count_box = modern.Stepper(count_col, textvariable=self.count, maximum=20)
        self.count_box.pack(fill="x", pady=(T.px(T.FIELD_GAP), 0))
        self.count_box.bind("<KeyRelease>", self.show_count)
        self.count_box.wheel_guard = lambda: self.display.get("wheel_controls", False)
        self.count.trace_add("write", lambda *_: self._sync_start_button())

        self._match_count = 0
        self.available = tk.Label(
            host, text="", bg=T.SURFACE, fg=T.TEXT_SECONDARY,
            font=T.TYPE_CAPTION, anchor="w",
        )
        self.available.pack(fill="x", pady=(T.px(T.GROUP_GAP), 0))
        tk.Frame(host, bg=T.SURFACE).pack(fill="both", expand=True)

        footer = tk.Frame(host, bg=T.SURFACE)
        footer.pack(fill="x", pady=(T.px(T.SPACE_4), 0))
        modern.hairline(footer).pack(fill="x", pady=(0, T.px(T.SPACE_4)))
        actions = tk.Frame(footer, bg=T.SURFACE)
        actions.pack(fill="x")
        self.start_button = modern.SoftButton(
            actions, text=self.tr("开始练习"), command=self.start_configured,
            variant="primary", width=T.px(180),
        )
        self.start_button.pack(side="left")
        modern.SoftButton(
            actions, text=self.tr("返回首页"), command=self.home,
            variant="secondary", width=T.px(120),
        ).pack(side="right")

        self.refresh_filters()
        self._paint_subject_cards()
        self._sync_start_button()

    def _select_subject(self, name):
        self.subject.set(name)
        self.refresh_filters()
        self._paint_subject_cards()

    def _paint_subject_cards(self):
        chosen = self.subject.get()
        for item, name in getattr(self, "_subject_cards", []):
            if item.winfo_exists():
                item.set_selected(name == chosen)

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

    def _difficulty_label(self, value):
        """Translate a difficulty data value for display without changing data."""
        if value == self.tr("全部"):
            return self.tr("全部")
        return self.tr(DIFFICULTY_LABELS.get(value, value))

    def refresh_difficulties(self, event=None):
        subset = [
            q
            for q in self.questions
            if q.subject == self.subject.get()
            and (self.topic.get() == self.tr("全部") or q.topic == self.topic.get())
        ]
        order = {"easy": 0, "medium": 1, "hard": 2}
        values = [self.tr("全部")] + sorted(
            {q.difficulty for q in subset},
            key=lambda name: (order.get(name, 99), name),
        )
        self.difficulty_box["values"] = values
        self.difficulty.set(self.tr("全部"))
        self._rebuild_difficulty_chips(values)
        self.show_count()

    def _rebuild_difficulty_chips(self, values):
        host = getattr(self, "difficulty_chips", None)
        if host is None or not host.winfo_exists():
            return
        labels = [self._difficulty_label(value) for value in values]
        host.set_values(values, labels)
        host.set(self.difficulty.get())
        self._difficulty_chip_widgets = []

    def _select_difficulty(self, value):
        self.difficulty.set(value)
        self._paint_difficulty_chips()
        self.show_count()

    def _paint_difficulty_chips(self):
        host = getattr(self, "difficulty_chips", None)
        if host is not None and host.winfo_exists():
            host.set(self.difficulty.get())

    def show_count(self, event=None):
        count = sum(
            q.subject == self.subject.get()
            and (self.topic.get() == self.tr("全部") or q.topic == self.topic.get())
            and (self.difficulty.get() == self.tr("全部") or q.difficulty == self.difficulty.get())
            for q in self.questions
        )
        previous = getattr(self, "_match_count", count)
        self._match_count = count

        def formatter(value):
            return self.tr("当前匹配：{0} 道题", value)

        if getattr(self, "available", None) and self.available.winfo_exists():
            self.motion.roll_count(self.available, formatter, previous, count)
        box = getattr(self, "count_box", None)
        if box is not None and box.winfo_exists():
            box.configure(to=max(count, 1))
            if count and self._wanted_count() > count:
                self.count.set(str(count))
        wanted = self._wanted_count()
        extra = ""
        if count and wanted > count:
            extra = self.tr("将使用全部 {0} 道匹配题。", count)
        topics = len(self.topic_box["values"]) - 1 if getattr(self, "topic_box", None) else 0
        summary = getattr(self, "config_summary", None)
        if summary is not None and summary.winfo_exists():
            shown_difficulty = self._difficulty_label(self.difficulty.get())
            summary.configure(
                text=self.tr(
                    "{0} · {1} · {2} · {3} 个主题",
                    self.subject.get(),
                    self.topic.get(),
                    shown_difficulty,
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
            difficulty = None if self.difficulty.get() == self.tr("全部") else self.difficulty.get()
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
        path = filedialog.asksaveasfilename(
            parent=self.root,
            defaultextension="." + format,
            filetypes=[(format.upper(), "*." + format)],
            initialfile=kind + "." + format,
        )
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
            ttk.Button(
                bar,
                text=self.tr("导出 {0}", format.upper()),
                command=lambda f=format: self.export_progress(kind, f),
            ).pack(side="left", padx=4)

    def _image_box(self, host, max_width=None):
        """Space the illustration may take, in device pixels (DPI aware).

        On the quiz page the question column has no width yet while it is being
        built, so the fallback estimates half the window; the first <Configure>
        of the column corrects it a moment later.
        """
        width = host.winfo_width() if host is not None and host.winfo_exists() else 0
        if width <= T.px(200):
            width = max(T.px(400), self.root.winfo_width() // 2)
        cap = T.px(max_width or ART_MAX_W)
        return (max(T.px(280), min(width - T.px(16), cap)), T.px(ART_MAX_H))

    def _blend_color(self, host):
        """Background the illustration should sit on, so its transparency works."""
        try:
            return host.cget("background")
        except tk.TclError:
            pass
        try:
            style = host.cget("style") or "App.TFrame"
            return ttk.Style(self.root).lookup(style, "background") or T.BG
        except tk.TclError:
            return T.BG

    def show_image(self, value, parent=None, fallback_subject=None, max_width=None):
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
            base = tk.PhotoImage(master=self.root, file=str(path))
            surface = self._blend_color(host)
            frame = tk.Frame(host, bg=surface, bd=0, highlightthickness=0)
            frame.pack(anchor="w", pady=5)
            label = tk.Label(frame, image=base, bg=surface, bd=0, highlightthickness=0)
            label.pack(anchor="w")
            self._fit_image(label, base, host, max_width)
            # Keep the copy that is actually on screen: the 3x source only has
            # to survive as long as its label does.
            self.images.append(label._fit_photo)
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
                wraplength=T.px(640),
            ).pack(anchor="w", pady=6)

    def _fit_image(self, label, base, host, max_width=None):
        """Show ``base`` as large as the column allows, and keep it in sync.

        Tk can only subsample, so the step is chosen from the 3x source bitmap
        instead of stretching a small one. The chosen copy is cached on the
        label because a PhotoImage must outlive the widget that displays it.
        """
        state = {"factor": 0}

        def apply():
            limit_w, limit_h = self._image_box(host, max_width)
            factor = art_factor(base.width(), base.height(), limit_w, limit_h)
            if factor == state["factor"] or not label.winfo_exists():
                return
            state["factor"] = factor
            label._fit_photo = base.subsample(factor) if factor > 1 else base
            label.configure(image=label._fit_photo)

        apply()
        host.bind("<Configure>", lambda _event: apply(), add="+")

    def question_content(self, q, selectable=False, parent=None, art_width=None):
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
            wraplength=T.px(CONTENT_MAX - 48),
            justify="left",
            style="Question.TLabel" if on_body else "Card.TLabel",
        ).pack(fill="x", pady=(4, 10))
        self.show_image(
            q.question_image,
            host,
            fallback_subject=q.subject if selectable else None,
            max_width=art_width,
        )
        self.option_buttons = []
        self.option_cards = []
        self.option_status = {}
        box = ttk.LabelFrame(host, text=self.tr("选项"), padding=6)
        box.pack(fill="x", pady=4)
        for index, option in enumerate(q.options):
            text = f"{option_label(index)}: {option}"
            if selectable:
                card = tk.Frame(
                    box,
                    bg=T.SURFACE,
                    highlightthickness=T.px(1),
                    highlightbackground=T.BORDER_LIGHT,
                    highlightcolor=T.PRIMARY,
                )
                card.pack(anchor="w", pady=3, fill="x")
                inner = tk.Frame(card, bg=T.SURFACE)
                inner.pack(fill="x", padx=6, pady=4)
                mark = tk.Label(
                    inner,
                    text=option_label(index),
                    bg=T.SURFACE,
                    fg=T.PRIMARY,
                    font=(FONT, 12, "bold"),
                    width=3,
                )
                mark.pack(side="left")
                widget = ttk.Radiobutton(
                    inner,
                    text=option,
                    variable=self.answer,
                    value=option,
                    style="CardOption.TRadiobutton",
                )
                widget.pack(side="left", fill="x", expand=True, padx=8)
                status = tk.Label(inner, text="", bg=T.SURFACE, fg=T.MUTED, font=TYPE_HINT, width=6)
                status.pack(side="right")
                self.option_status[option] = status
                self.option_buttons.append(widget)
                self.option_cards.append((card, option))

                def pick(value=option):
                    self._pick_option(value)

                bind_whole(card, pick)
                card.bind("<Enter>", lambda _e, frame=card: self._hover_option(frame, True))
                card.bind("<Leave>", lambda _e, frame=card: self._hover_option(frame, False))
                widget.bind("<Enter>", lambda _e, frame=card: self._hover_option(frame, True))
                widget.bind("<Leave>", lambda _e, frame=card: self._hover_option(frame, False))
            else:
                ttk.Label(box, text=text, wraplength=T.px(600), style="Card.TLabel").pack(
                    anchor="w", pady=2
                )
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
            self._fill_option(frame, T.SELECTED_BG, T.PRIMARY)
            return
        self._fill_option(frame, T.HOVER if entering else T.SURFACE, T.PRIMARY if entering else T.BORDER)

    def _paint_options(self, submitted=False, correct=False):
        chosen = self.answer.get()
        answer = self.engine.current.answer if self.engine else ""
        for frame, option in getattr(self, "option_cards", []):
            if not frame.winfo_exists():
                continue
            status = getattr(self, "option_status", {}).get(option)
            note = ""
            if submitted and option == answer:
                color = T.SUCCESS_BG
                border = T.SUCCESS_FG
                note = self.tr("正确")
            elif submitted and option == chosen and option != answer:
                color = T.ERROR_BG
                border = T.ERROR
                note = self.tr("你的选择")
            elif option == chosen:
                color = T.SELECTED_BG
                border = T.PRIMARY
                note = self.tr("已选")
            else:
                color = T.SURFACE
                border = T.BORDER
            self._fill_option(frame, color, border)
            if status is not None and status.winfo_exists():
                status.configure(
                    text=note, bg=color, fg=T.SUCCESS_FG if note == self.tr("正确") else T.TEXT
                )

    def show_question(self):
        engine = self.engine
        mode = self.tr("错题复习") if engine.review else self.tr("练习")
        total = len(engine.questions)
        self._choices_locked = False
        self._submit_busy = False
        self.clear(
            self.tr("{0} · 第 {1} / {2} 题", mode, engine.index + 1, total), show_heading=False
        )
        self.quiz_progress_header = ttk.Frame(self.outer, style="App.TFrame", padding=(24, 4))
        self.quiz_progress_header.pack(side="top", fill="x", before=self.canvas)
        path = tk.Canvas(self.quiz_progress_header, height=28, bg=T.BG, highlightthickness=0, bd=0)
        path.pack(fill="x", pady=(2, 4))
        path.bind(
            "<Configure>",
            lambda _e, canvas=path, n=total, i=engine.index + 1: self.motion.paint_path(
                canvas, n, i
            ),
        )
        self.answer = tk.StringVar(value="")
        split = ttk.Frame(self.body, style="App.TFrame")
        split.pack(fill="both", expand=True)
        # Half / half: the assistant used to be a narrow 40% strip with a short
        # box at the top, leaving a large dead area under it. Both columns now
        # grow with the viewport and the assistant is a full-height stack.
        split.columnconfigure(0, weight=1, uniform="quiz_split")
        split.columnconfigure(1, weight=1, uniform="quiz_split")
        split.rowconfigure(0, weight=1)
        self.question_shell = ttk.Frame(split, style="App.TFrame")
        self.question_shell.grid(
            row=0, column=0, sticky="nsew", padx=(0, T.px(T.SPACE_3))
        )
        self.question_content(engine.current, selectable=True, parent=self.question_shell)
        self._quiz_ai_panel(split)
        self.answer.trace_add("write", lambda *_: self._on_answer_changed())
        self.feedback = self.label("")
        dock = self._action_dock()
        self.submit_button = ttk.Button(
            dock, text=self.tr("检查答案"), command=self.submit, style="Accent.TButton"
        )
        self.submit_button.pack(side="left", padx=T.px(T.SPACE_2))
        self.submit_button.state(["disabled"])
        next_label = self.tr("查看结果") if engine.index == total - 1 else self.tr("继续")
        self.next_button = ttk.Button(
            dock, text=next_label, command=self.advance, style="Accent.TButton"
        )
        self.next_button.state(["disabled"])
        ai_key = (engine.id, engine.index)
        if ai_key in self._ai_asked:
            self.quiz_ai_button.configure(text=self.tr("本题已询问"))
            self.quiz_ai_button.state(["disabled"])
        ttk.Button(
            dock, text=self.tr("结束练习并返回"), command=self.leave_quiz, style="Tool.TButton"
        ).pack(side="right")
        self._bind_quiz_keys()
        self.motion.fade_in(self.question_shell, duration=160)

    def _circle_avatar(self, parent, size, bg=None):
        """Round assistant avatar instead of a square image tile."""
        canvas = tk.Canvas(
            parent, width=size, height=size, bg=bg or T.SURFACE,
            highlightthickness=0, bd=0, takefocus=0,
        )
        try:
            photo = tk.PhotoImage(
                master=self.root, file=str(self.project_root / "AI-assistant-icon.png")
            )
            target = max(24, size - T.px(T.SPACE_2))
            factor = max(1, (max(photo.width(), photo.height()) + target - 1) // target)
            canvas._photo = photo.subsample(factor)
        except (tk.TclError, OSError):
            canvas._photo = None

        def draw(_event=None):
            side = min(canvas.winfo_width(), canvas.winfo_height())
            canvas.delete("all")
            if side <= 2:
                return
            gap = T.px(2)
            canvas.create_oval(
                gap, gap, side - gap, side - gap,
                fill=T.PRIMARY_SOFT, outline=T.PRIMARY, width=T.px(T.HAIRLINE),
            )
            if canvas._photo is not None:
                canvas.create_image(side // 2, side // 2, image=canvas._photo)
            else:
                canvas.create_text(
                    side // 2, side // 2, text="✦", fill=T.PRIMARY,
                    font=(FONT, max(12, side // 3), "bold"),
                )

        canvas.bind("<Configure>", draw, add="+")
        return canvas

    def _quiz_ai_panel(self, split):
        """Vertical Ask AI card: title -> reply area -> avatar + action row.

        The old layout put the reply and the avatar side by side inside a short
        card. Stacking them lets the reply use the whole column and grow with the
        window, while the action row stays pinned at the bottom.
        """
        panel = card_frame(split, pad=T.SPACE_5)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        self.quiz_ai_panel = panel

        head = tk.Frame(panel, bg=T.SURFACE)
        head.grid(row=0, column=0, sticky="ew", pady=(0, T.px(T.SPACE_3)))
        tk.Label(
            head, text=self.tr("问问 AI"), bg=T.SURFACE, fg=T.PRIMARY,
            font=T.TYPE_HEADING, anchor="w",
        ).pack(side="left")
        tk.Label(
            head, text=self.tr("每题可询问一次"), bg=T.SURFACE, fg=T.TEXT_MUTED,
            font=T.TYPE_CAPTION, anchor="e",
        ).pack(side="right")

        bubble = modern.SoftPanel(
            panel, fill=T.AI_REPLY_BG, edge=T.AI_REPLY_EDGE, padding=T.SPACE_4,
        )
        bubble.grid(row=1, column=0, sticky="nsew")
        bubble.content.columnconfigure(0, weight=1)
        bubble.content.rowconfigure(0, weight=1)
        self.quiz_ai_reply = AssistantReply(
            bubble.content,
            text=self.tr("点击下方向 AI 请求本题提示。"),
            bg=T.AI_REPLY_BG, fg=T.TEXT_SECONDARY, font=T.TYPE_BODY,
            wrap="word", width=1, relief="flat", height=9,
            highlightthickness=0, bd=0, padx=0, pady=0,
        )
        reply_scroll = ttk.Scrollbar(
            bubble.content, orient="vertical", command=self.quiz_ai_reply.yview
        )
        reply_scroll.grid(row=0, column=1, sticky="ns", padx=(T.px(T.SPACE_2), 0))
        self.quiz_ai_reply.configure(yscrollcommand=reply_scroll.set)
        self.quiz_ai_reply.grid(row=0, column=0, sticky="nsew")

        footer = tk.Frame(panel, bg=T.SURFACE)
        footer.grid(row=2, column=0, sticky="ew", pady=(T.px(T.SPACE_3), 0))
        footer.columnconfigure(1, weight=1)
        avatar_size = T.px(56)
        self._circle_avatar(footer, avatar_size).grid(
            row=0, column=0, sticky="w", padx=(0, T.px(T.SPACE_3))
        )
        self.quiz_ai_button = modern.SoftButton(
            footer,
            text=self.tr("问问 AI"),
            command=self.ask_current_question_ai,
            variant="primary",
            width=T.px(220),
        )
        self.quiz_ai_button.grid(row=0, column=1, sticky="ew", ipady=0)
        return panel

    def ask_current_question_ai(self):
        if not self.engine:
            return
        key = (self.engine.id, self.engine.index)
        self._request_ai(
            question_message(self.engine.current, self.tr.language),
            self.quiz_ai_button,
            self.quiz_ai_reply,
            once_key=key,
        )

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
        detail = self.tr("回答正确，继续保持。") if correct else self.tr("回答错误，已记入错题本。")
        self.feedback.configure(
            style="Success.TLabel" if correct else "Error.TLabel",
            text=self.tr(
                "{0}\n正确答案：{1}\n解析：{2}", f"{headline}\n{detail}", q.answer, q.explanation
            ),
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
            self.submit_button.pack_forget()
            self.next_button.configure(text=next_label)
            self.next_button.pack(side="left", padx=8)
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
        self.clear(self.tr("练习完成"), show_heading=False)
        if getattr(self.engine, "timed_out", False):
            self.label(
                self.tr(
                    "本轮已超时，未答 {0} 题计为未得分；未答题不会加入错题本。",
                    self.engine.unanswered,
                )
            )
        stats = ttk.Frame(self.body, style="App.TFrame")
        stats.pack(fill="x", pady=(4, 12))
        for title, value in (
            (self.tr("正确率"), f"{result['accuracy']:.0f}%"),
            (self.tr("答对题数"), f"{result['correct']} / {result['total']}"),
            (self.tr("总分"), f"{result['score']} / {result['max_score']}"),
        ):
            cell = card_frame(stats, pad=14)
            cell.pack(side="left", fill="x", expand=True, padx=(0, 10))
            tk.Label(cell, text=title, bg=T.SURFACE, fg=T.MUTED, font=TYPE_HINT).pack(anchor="w")
            tk.Label(cell, text=value, bg=T.SURFACE, fg=T.TEXT, font=(FONT, 20, "bold")).pack(
                anchor="w", pady=(4, 0)
            )
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
        ttk.Button(
            actions, text=self.tr("再练一次"), command=self.retry_quiz, style="Accent.TButton"
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            actions, text=self.tr("查看错题本"), command=self.notebook, style="Accent.TButton"
        ).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text=self.tr("返回首页"), command=self.home, style="Tool.TButton").pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(
            actions, text=self.tr("查看学习历史"), command=self.history, style="Tool.TButton"
        ).pack(side="left")

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
                self.tr(
                    "本次练习尚未完成，退出后不会计入成绩历史。已经提交且答错的题目会保留在错题本，供以后复习。确定退出吗？"
                ),
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
        self.clear(self.tr("错题本"), show_heading=False)
        self.export_buttons("wrong")
        try:
            wrong = self.progress.load()["wrong"]
        except DataError as exc:
            empty = card_frame(self.body, pad=16)
            empty.pack(fill="both", expand=True)
            tk.Label(
                empty,
                text=self.tr("学习数据加载失败"),
                bg=T.SURFACE,
                fg=T.TEXT,
                font=(FONT, 13, "bold"),
            ).pack(anchor="w")
            tk.Label(
                empty, text=self.tr(str(exc)), bg=T.SURFACE, fg=T.MUTED, wraplength=T.px(560), justify="left"
            ).pack(anchor="w", pady=8)
            ttk.Button(
                empty, text=self.tr("重新加载题库"), command=self.notebook, style="Accent.TButton"
            ).pack(anchor="w")
            return
        if not wrong:
            empty = card_frame(self.body, pad=16)
            empty.pack(fill="both", expand=True)
            tk.Label(
                empty,
                text=self.tr("还没有错题。开始一次练习吧！"),
                bg=T.SURFACE,
                fg=T.TEXT,
                font=(FONT, 13, "bold"),
            ).pack(anchor="w")
            tk.Label(
                empty,
                text=self.tr("完成第一次练习后，学习动态会显示在这里。"),
                bg=T.SURFACE,
                fg=T.MUTED,
                wraplength=T.px(560),
                justify="left",
            ).pack(anchor="w", pady=8)
            ttk.Button(
                empty,
                text=self.tr("开始第一次练习"),
                command=self.configure,
                style="Accent.TButton",
            ).pack(anchor="w")
            return
        available = [self.by_id[key] for key in wrong if key in self.by_id]
        self.label(
            self.tr("复习规则：复习答对后移除；普通练习答对不会移除。重复答错累计次数。"),
            "Muted.TLabel",
        )
        actions = ttk.Frame(self.body, style="App.TFrame")
        actions.pack(fill="x", pady=(0, 8))
        if available:
            ttk.Button(
                actions,
                text=self.tr("复习全部可用错题（{0} 道）", len(available)),
                command=lambda: self.start_quiz(available, True),
                style="Accent.TButton",
            ).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text=self.tr("返回首页"), command=self.home, style="Tool.TButton").pack(
            side="left"
        )
        for key, record in wrong.items():
            panel = card_frame(self.body, pad=14)
            panel.pack(fill="x", pady=(0, 10))
            if key not in self.by_id:
                tk.Label(
                    panel,
                    text=self.tr(
                        "{0}：题目已删除或无效，暂不能复习；记录保留，恢复题目后可继续。", key
                    ),
                    bg=T.SURFACE,
                    fg=T.MUTED,
                    wraplength=T.px(560),
                    justify="left",
                ).pack(anchor="w")
                continue
            q = self.by_id[key]
            tk.Label(panel, text=q.subject, bg=T.SURFACE, fg=T.PRIMARY, font=TYPE_HINT).pack(anchor="w")
            self.question_content(q, parent=panel, art_width=360)
            tk.Label(
                panel,
                text=self.tr("你选择：{0}", record["last_answer"]),
                bg=T.SURFACE,
                fg=T.MUTED,
                font=TYPE_HINT,
            ).pack(anchor="w", pady=(6, 0))
            tk.Label(
                panel,
                text=self.tr("正确答案：{0}", q.answer),
                bg=T.SURFACE,
                fg=T.TEXT,
                font=TYPE_HINT,
            ).pack(anchor="w")
            tk.Label(
                panel,
                text=self.tr("错误次数：{0}", record["count"]),
                bg=T.SURFACE,
                fg=T.MUTED,
                font=TYPE_HINT,
            ).pack(anchor="w", pady=(0, 8))
            explain = tk.Label(
                panel,
                text=self.tr("解析：{0}", q.explanation),
                bg=T.SURFACE,
                fg=T.MUTED,
                font=TYPE_HINT,
                wraplength=T.px(560),
                justify="left",
            )

            def toggle_explain(label=explain):
                if label.winfo_ismapped():
                    label.pack_forget()
                else:
                    label.pack(anchor="w", pady=(0, 8))

            row = tk.Frame(panel, bg=T.SURFACE)
            row.pack(anchor="w")
            self._text_button(row, self.tr("查看解析"), toggle_explain, bg=T.SURFACE).pack(
                side="left", padx=(0, 12)
            )
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
        self.clear(self.tr("学习统计与历史"), show_heading=False)
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
            wraplength=T.px(640),
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
            empty.pack(fill="both", expand=True, pady=(0, T.px(T.SPACE_2)))
            tk.Label(
                empty, text=self.tr("还没有学习记录"), bg=T.SURFACE, fg=T.TEXT, font=(FONT, 13, "bold")
            ).pack(anchor="w")
            tk.Label(
                empty,
                text=self.tr("完成第一次练习后，学习动态会显示在这里。"),
                bg=T.SURFACE,
                fg=T.MUTED,
                wraplength=T.px(560),
                justify="left",
            ).pack(anchor="w", pady=8)
            ttk.Button(
                empty,
                text=self.tr("开始第一次练习"),
                command=self.configure,
                style="Accent.TButton",
            ).pack(anchor="w")
        for record in reversed(history):
            card = ttk.LabelFrame(self.body, text=record["date"], padding=12)
            card.pack(fill="x", pady=8)
            ttk.Label(
                card,
                style="Card.TLabel",
                wraplength=T.px(640),
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


def maximize_startup(root):
    """Open maximized by default instead of a small 1040x720 box on 2K/4K screens."""
    try:
        root.state("zoomed")  # Windows
        return
    except tk.TclError:
        pass
    try:
        root.attributes("-zoomed", True)  # some X11 window managers
        return
    except tk.TclError:
        pass
    root.geometry(
        f"{max(960, root.winfo_screenwidth() - 80)}x"
        f"{max(640, root.winfo_screenheight() - 120)}+40+40"
    )


def main():
    from .dpi import apply_to, enable

    enable()  # must precede the first Tk window (high-dpi text clarity)
    root = tk.Tk()
    apply_to(root)
    Application(root)
    maximize_startup(root)
    root.mainloop()
