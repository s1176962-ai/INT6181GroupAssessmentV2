---
version: 2.7
name: Modern Light / Quiz-Studio
description: >
  Offline Tkinter/ttk quiz shell with two switchable palettes ("Daylight" light
  and "Lights Out" dark). learning_platform/tokens.py is the single source of
  truth for colour, spacing, radius, type, geometry and DPI scale;
  learning_platform/ui_tokens.py is a thin compatibility shim that rebinds its
  module globals on set_theme(). Colours must be read at render time as
  T.<TOKEN>. learning_platform/modern.py holds the Canvas-drawn controls
  (rounded cards, soft shadows, four interaction states) that replace the
  native widget look on the app shell and the Configure-quiz form.
---

token_source:
  file: learning_platform/tokens.py
  compat: learning_platform/ui_tokens.py
  rule: "No colour literal outside tokens.py; every style reads T.<TOKEN> at render time."
  dpi: learning_platform/dpi.py (SetProcessDpiAwareness(1) before the first Tk window)
  scaling: "All geometry goes through T.px(); fonts are converted by T.font_at()."

palettes:
  light:
    page: "#F7F8FA"
    surface: "#FFFFFF"
    nav: "#F8F9FC"
    border-light: "#E9ECF1"
    border-control: "#DFE4EC"
    primary: "#2F6BFF"
    primary-soft: "#EEF3FF"
    text: "#1B2430"
    text-secondary: "#6B7688"
    text-muted: "#9AA5B5"
  dark:
    page: "#14171C"
    surface: "#1C2027"
    nav: "#191D23"
    border: "#2C323C"
    text: "#E8ECF2"
    text-secondary: "#9AA5B5"
    primary: "#5B83FF"
    primary-soft: "#1E2A45"

geometry:
  radius-card: 12
  radius-control: 9
  radius-chip: 8
  radius-avatar: "50%"
  spacing-grid: [4, 8, 12, 16, 24, 32]
  card-padding: 24
  label-to-control: 8
  group-gap: 24
  control-height: 36
  icon-size: 16
  topbar-height: 54
  nav-indicator: 3
  focus-ring: 3

typography:
  family: "Microsoft YaHei UI / Segoe UI"
  title: "15px / 500 (Tk has no 500; bold is the closest approximation)"
  body: "13-14px / 400"
  caption: "12px / 400"
  line-height: 1.5

elevation:
  shadow: "0 1px 2px rgba(16,24,40,.04) + 0 8px 24px rgba(16,24,40,.06)"
  implementation: >
    Tk has no alpha compositing, so SHADOW_NEAR / SHADOW_FAR are pre-mixed
    opaque colours and drawn as two offset rounded rectangles behind the card.
    Depth comes from shadows, never from a 1px dark grey border.

components:
  SoftCard: "12px radius, two soft shadow bands, 24px inner padding"
  SoftPanel: "12px radius tinted surface without shadow (chat composer / reply area); optional hairline edge that can be swapped for the focus colour"
  SoftButton / CircleIconButton: "9px radius / 36px circle; hover, pressed, focus, disabled"
  Dropdown: "36px rounded frame + self-drawn chevron; no native Combobox arrow"
  Stepper: "unified [-] value [+] control; no native Spinbox"
  Segmented: "grey track with a raised capsule for the selected value"
  Toggle: "44x24 switch for dark mode"
  NavItem: "PRIMARY_SOFT rounded background + 3px primary indicator + 16px line icon"
  SubjectCard: "selected = PRIMARY_SOFT + primary outline + top-right check dot"
  hairline: "1px BORDER_LIGHT separator (top bar)"

rules:
  - "All clickable elements expose hover / pressed / focus / disabled states, all valued from tokens."
  - "Focus: strip the ttk .focus layout; self-drawn controls paint a 3px FOCUS_GLOW ring."
  - "Theme switching rebinds tokens, restyles ttk, then rebuilds the current screen; in-flight quiz engines survive."
  - "No native Combobox / Spinbox is instantiated on the redesigned pages."
  - "Legacy pages still use ttk Button / LabelFrame / Radiobutton / Checkbutton: they are token-styled with four states and flat relief, but ttk cannot draw rounded corners, so those surfaces stay square. Converting them to modern.SoftButton is a follow-up pass."
  - "widgets.card_frame() draws a rounded soft card behind its children and snaps legacy padding (14/18/22) to the 4pt grid."
  - "Business logic, data structures, question algorithms and i18n behaviour are unchanged."
  - "The home dashboard keeps its original V2 four-card layout; only global tokens, card rendering and vertical growth changed."

v2_4_layout_fixes:
  startup: >
    launcher.py and gui.main() call maximize_startup(root) after deiconify; Windows
    uses root.state("zoomed"), X11 falls back to -zoomed / a screen-filling geometry.
    All three entry points (start.bat, main.py, python -m learning_platform) inherit it.
  viewport_growth: >
    The scroll-canvas body window is stretched to the full canvas height, so the
    home dashboard's two grid rows expand with the viewport instead of leaving a
    large empty band under four short cards. Home card padding is unified to
    T.SPACE_5 (24) and all paddings pass through T.px().
  login: >
    The login form is widened (CARD_WIDTH 420 -> 520 design px), the hero headline
    is TYPE_HERO, and the right-hand form column is centred and padded so the
    toolbar (theme / Settings / language / Exit) never clips at high DPI.
  wrapping: >
    Fixed wraplength literals were removed. label(), settings() fit() and the
    configure() column helper track the widget's real <Configure> width, so
    descriptions use the full card width at 100/125/150% DPI without narrow
    columns or clipped tails.
  focus_regression: >
    _strip_focus() must HOIST the children of a removed .focus element, not drop
    the whole node: the clam theme nests Radiobutton.label / Checkbutton.label
    inside .focus. Dropping it made every radio/check button show only its dot.
  default_language: >
    A fresh profile starts in English (Translator default {"language": "en"} and
    data/settings.json). Locked by LanguageTests.test_new_profile_starts_in_english.

v2_5_quiz_and_i18n:
  ask_ai_vertical: >
    show_question() splits the body 50/50 with a weighted grid row, so both
    columns grow with the viewport. _quiz_ai_panel() replaces the old short
    left/right speech bubble with a vertical stack: "Ask AI" header + one-hint
    caption, a full-width weighted reply bubble, then a circular avatar and a
    wide SoftButton pinned to the bottom. The button label doubles as the
    "Asked for this question" status; one-ask-per-question locking is unchanged.
  english_only: >
    ai_assistant.py now holds SYSTEM_PROMPTS {zh, en} and question_message()
    accepts the UI language. _request_ai() passes self.tr.language, so the
    English system prompt forces English output even when the stem/options are
    in another language. Validation and network errors are bilingual too.
    DIFFICULTY_LABELS are i18n keys resolved through _difficulty_label(), so
    the segmented control and the config summary read All / Easy / Medium /
    Hard in English. The language option "简体中文" is rendered as
    "Simplified Chinese" in English mode.
  table_fill: >
    Question-bank and user-management tables had a pack(expand=True) frame but
    no weighted grid row, so the Treeview stayed 10 rows tall. Both now set
    rowconfigure(0, weight=1), grow to 18 baseline rows and stretch their last
    column. All Treeview column widths go through T.px() so 125/150% DPI does
    not truncate "Difficulty" / "Mathematics" / "Vocabulary".
  short_pages: >
    The Configure-quiz SoftCard now packs with fill="both", expand=True and a
    flexible spacer pins its footer to the bottom of the card, removing the
    large dead band below the form. Empty-state cards on notebook/history also
    expand to the viewport.
  question_content_exception: >
    Question stems and options are data, not UI chrome. ENG001 deliberately
    offers Chinese translations, so an English screen can still show Chinese
    inside a question. This is intentional per the SRS ("question content
    stays in its original language") and is not an i18n leak.

v2_6_home_ai:
  palette: >
    AI surfaces no longer borrow the neutral HOVER grey, which read as a foreign
    colour next to the blue accent. New semantic tokens: AI_INPUT_BG
    (PRIMARY_SOFT), AI_INPUT_EDGE, AI_REPLY_BG and AI_REPLY_EDGE. In light mode
    the reply area is a 72% PRIMARY_SOFT tint on white; in dark mode PRIMARY_SOFT
    is too close to SURFACE, so the reply tint is mixed from the accent instead
    (mix(surface, primary, 0.10)) or the panel would disappear.
  layout: >
    _build_home_ai() replaces the old stacked "grey input + grey reply + floating
    Send + corner avatar" block. Structure: header (primary dot + "Ask AI"),
    composer SoftPanel (2-line field, Send button inside the panel, one caption
    line with the Enter hint), then a reply SoftPanel that owns all remaining
    height. The composer edge turns PRIMARY while the field has focus.
  portrait: >
    The Q-version character is the idle illustration of the reply panel. It is
    sized from the panel's real <Configure> box (up to 320 design px), drawn with
    integer PhotoImage subsampling so no PIL dependency is added, and grouped
    with its greeting in one centred block - packing the canvas with expand
    pushed the caption to the bottom of a tall card, far from the character. The
    caption is dropped when the panel is too short for art >= 120 design px.
  state_swap: >
    AssistantReply takes an on_text hook; _on_home_ai_text() swaps the idle
    portrait for the answer surface ("AI hint" + read-only text) on the first
    status/reply and restores the portrait when the text is cleared.
  composer_keys: >
    Enter sends, Shift+Enter inserts a newline; ask_home_ai() clears the field
    after a successful dispatch and the placeholder is restored on focus-out.
  quiz_panel: >
    _quiz_ai_panel() reuses the same AI_REPLY_BG / AI_REPLY_EDGE tints so the
    in-quiz hint panel and the dashboard card read as one product.

v2_7_question_art:
  problem: >
    The old show_image() capped art at 480x220 device px. Every question asset is
    480x270, so the height cap alone forced subsample(2) and the illustration was
    rendered at 240x135 - half its intended size, and tiny next to DPI-scaled text.
  source: >
    scripts/generate_question_art.py keeps the 480x270 design grid but renders at
    SCALE=3 (1440x810) through a ScaledDraw proxy, and supersamples 2x before a
    LANCZOS downscale, so strokes and captions are rasterised at final resolution
    instead of being a blurred upscale. The canvas is RGBA with a transparent
    margin, so the illustration card floats on any surface.
  sizing: >
    show_image()/_fit_image() pick the crispest integer subsample that fits the
    hosting column (<=72% - 16px of the column, height cap 420 design px) and the
    choice is cached per factor. The <Configure> of the host re-fits on resize,
    which also corrects the first pass, where a freshly built quiz column still
    reports width 1. Compact contexts (wrong-answer notebook, question editor
    preview) pass max_width=360.
  blend: >
    Tk PhotoImage alpha composites against the widget background, so the label and
    its frame take their background from the host (_blend_color: classic bg, then
    ttk style lookup). A white ttk frame would have shown a bright box in dark mode.
  memory: >
    Only the on-screen copy is appended to Application.images; the 1440x810 source
    lives as long as the label that shows it.

known_limits:
  - "Tk cannot express font-weight 500; bold is used for the 15px title."
  - "A 1.5px outline is approximated by T.px(2)."
  - "Native ttk widgets cannot paint a 3px glow; they keep a 1px primary focus border."
  - "Settings sections still use ttk.LabelFrame: token-styled and full-width, but square-cornered in dark theme. Converting them to SoftCard is a follow-up pass."
  - "The app still defaults to English (data/settings.json); Chinese keys remain the i18n source."
