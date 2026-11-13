"""A self-contained timed player-versus-simulated-AI match."""

import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from . import modern
from . import tokens as T
from .battle import (
    PROFILES,
    ROUND_SECONDS,
    ApiOpponent,
    LocalOpponent,
    apply_damage,
    grade,
)
from .image_cache import portrait_image
from .services import select_questions
from .widgets import card_frame


class BattlePage:
    @property
    def player_name(self):
        return self.app.user["name"] if self.app.user else "Player"

    @property
    def opponent_name(self):
        return "Big Whale" if self.app.tr.language == "en" else "大肥鱼"

    def __init__(self, app):
        self.app = app
        self.generation = 0
        self.active = False

    def setup(self):
        app = self.app
        app._nav_key = "battle"
        app.clear(app.tr("答题对战"), show_heading=False)
        app.load_bank()
        app.label(app.tr("双方回答同一道题，每题限时 30 秒；答对后才获得时间分。"))
        self.subject = tk.StringVar(value="All")
        self.level_labels = {app.tr(level): level for level in PROFILES}
        self.level = tk.StringVar(value=app.tr("普通级"))
        self.count = tk.StringVar(value="5")
        self.backend = tk.StringVar(value="API" if app.ai_settings.load()["api_key"] else "Local")
        self.initial_hp = tk.StringVar(value="100")
        for label, variable, values in (
            ("科目", self.subject, ["All"] + sorted({q.subject for q in app.public_questions})),
            ("对手等级", self.level, list(self.level_labels)),
            ("题量", self.count, ["3", "5", "10"]),
            ("初始血量", self.initial_hp, ["100", "200", "300", "500", "1000"]),
            ("AI", self.backend, ["Local", "API"]),
        ):
            app.label(app.tr(label))
            ttk.Combobox(app.body, textvariable=variable, values=values, state="readonly").pack(
                fill="x", pady=6
            )
        app.label(app.tr("正确分 100；≤5/10/15/20/30 秒分别加 50/40/30/20/10 分。额外分暂为 0。"))
        app.label(app.tr("API：模型根据题目选择答案并保存依据；Local：按概率模拟对手。"))
        app.button(app.tr("开始对战"), self.start, "Accent.TButton")

    def start(self):
        try:
            maximum = int(self.initial_hp.get())
            if maximum not in (100, 200, 300, 500, 1000):
                raise ValueError(self.app.tr("请选择有效的初始血量。"))
            self.questions = select_questions(
                self.app.public_questions,
                subject=None if self.subject.get() == "All" else self.subject.get(),
                count=int(self.count.get()),
            )
        except ValueError as exc:
            messagebox.showerror(self.app.tr("无法开始练习"), str(exc), parent=self.app.root)
            return
        self.difficulty = self.level_labels[self.level.get()]
        self.provider = (
            ApiOpponent(self.app.ai_assistant, self.app.tr.language, self.app.project_root)
            if self.backend.get() == "API"
            else LocalOpponent()
        )
        self.index = 0
        self.records = []
        self.max_hp = maximum
        self.player_hp = self.ai_hp = self.max_hp
        self.round()

    def round(self):
        app = self.app
        self.generation += 1
        generation = self.generation
        app.clear(app.tr("答题对战"), show_heading=False, back=self.leave)
        self.active = True
        self.player = self.ai = None
        self.started = time.monotonic()
        q = self.questions[self.index]
        self.planned, self.delay = None, ROUND_SECONDS
        self.decision = None
        self.decision_error = None
        responses = queue.Queue()

        def request_opponent():
            try:
                responses.put((self.provider.answer(q, self.difficulty), None))
            except Exception as exc:
                responses.put((None, str(exc)))

        threading.Thread(target=request_opponent, daemon=True).start()
        self.clock = app.label(f"{self.index + 1} / {len(self.questions)} · 30s")
        self.health = ttk.Frame(app.body)
        self.health.pack(fill="x", pady=4)
        self.hp_labels = []
        for name, hp in ((self.player_name, self.player_hp), (self.opponent_name, self.ai_hp)):
            ttk.Label(self.health, text=name).pack(side="left", padx=(0, 6))
            ttk.Label(self.health, text="♥", foreground="#EF4444").pack(side="left")
            value = ttk.Label(self.health, text=f" {hp}/{self.max_hp}")
            value.pack(side="left", padx=(0, 24))
            self.hp_labels.append(value)
        scores = ttk.Frame(app.body)
        scores.pack(fill="both", expand=True, pady=T.px(T.SPACE_3))
        for column in (0, 1):
            scores.columnconfigure(column, weight=1, uniform="battle")
        scores.rowconfigure(0, weight=1)
        player_card = card_frame(scores, pad=T.SPACE_4)
        player_card.grid(row=0, column=0, sticky="nsew", padx=(0, T.px(T.SPACE_3)))
        ai_card = card_frame(scores, pad=T.SPACE_4)
        ai_card.grid(row=0, column=1, sticky="nsew")
        self.player_status = ttk.Label(player_card, text=f"{self.player_name}: {app.tr('作答中')}")
        self.player_status.pack(anchor="w")
        self.ai_status = ttk.Label(ai_card, text=f"{self.opponent_name}: {app.tr('阅读题目')}")
        self.ai_status.pack(anchor="w")
        self.portrait = tk.Label(ai_card, bg=T.palette()["SURFACE"], bd=0)
        self.portrait.pack(pady=T.px(T.SPACE_2))
        self.show_expression("thinking")
        from .gui import AssistantReply

        analysis = ttk.Frame(ai_card)
        analysis.pack(fill="both", expand=True, pady=T.px(T.SPACE_3))
        self.thinking_status = AssistantReply(
            analysis,
            text=app.tr("阅读题目"),
            height=7,
            width=1,
            wrap="word",
            bg=T.palette()["SURFACE"],
            fg=T.palette()["TEXT"],
            font=T.TYPE_BODY,
            relief="flat",
            bd=0,
            highlightthickness=0,
        )
        scroll = ttk.Scrollbar(analysis, orient="vertical", command=self.thinking_status.yview)
        scroll.pack(side="right", fill="y")
        self.thinking_status.configure(yscrollcommand=scroll.set)
        self.thinking_status.pack(side="left", fill="both", expand=True)
        self.current_stage = -1
        self.show_decision_stage(0)
        ttk.Label(player_card, text=q.question, wraplength=T.px(420), style="Question.TLabel").pack(
            fill="x", pady=T.px(T.SPACE_3)
        )
        app.show_image(q.question_image, parent=player_card, max_width=280)
        self.buttons = []
        for index, option in enumerate(q.options):
            button = modern.SoftButton(
                player_card,
                text=f"{chr(65 + index)}  {option}",
                command=lambda value=option: self.answer(value),
                variant="secondary",
            )
            button.pack(fill="x", pady=T.px(T.SPACE_1))
            if q.option_images and q.option_images[index]:
                app.show_image(q.option_images[index], parent=player_card, max_width=180)
            self.buttons.append(button)
        dock = app._action_dock()
        result_frame = ttk.Frame(dock)
        result_frame.pack(fill="x", pady=(0, T.px(T.SPACE_2)))
        self.result = AssistantReply(
            result_frame,
            text="",
            height=4,
            width=1,
            wrap="word",
            bg=T.palette()["PAGE"],
            fg=T.palette()["TEXT"],
            font=T.TYPE_BODY,
            relief="flat",
            bd=0,
            highlightthickness=0,
        )
        result_scroll = ttk.Scrollbar(result_frame, orient="vertical", command=self.result.yview)

        def sync_scroll(first, last):
            result_scroll.set(first, last)
            if float(first) > 0.001 or float(last) < 0.999:
                if not result_scroll.winfo_manager():
                    result_scroll.pack(side="right", fill="y")
            else:
                result_scroll.pack_forget()

        self.result.configure(yscrollcommand=sync_scroll)
        self.result.pack(side="left", fill="x", expand=True)

        def fit_result(_event=None):
            lines = self.result.count("1.0", "end-1c", "displaylines")
            height = min(7, max(4, (lines[0] if lines else 0) + 1))
            if int(self.result.cget("height")) != height:
                self.result.configure(height=height)

        self.result.bind("<Configure>", fit_result)
        self.fit_result = fit_result
        self.next = ttk.Button(
            dock, text=app.tr("继续"), command=self.advance, style="Accent.TButton"
        )
        self.next.pack(side="left", padx=T.px(T.SPACE_2))
        self.next.state(["disabled"])

        def tick():
            if generation != self.generation or not self.active or not self.clock.winfo_exists():
                return
            elapsed = time.monotonic() - self.started
            try:
                response, error = responses.get_nowait()
                self.receive_decision(response, error, elapsed)
            except queue.Empty:
                pass
            if self.ai is None:
                _, low, high = PROFILES[self.difficulty]
                duration = self.delay if self.decision else (low + high) / 2
                stage = min(2, int(elapsed / max(duration, 1) * 3))
                self.show_decision_stage(stage)
            clock_text = f"{self.index + 1} / {len(self.questions)} · {max(0, ROUND_SECONDS - int(elapsed))}s"
            if self.clock.cget("text") != clock_text:
                self.clock.configure(text=clock_text)
            if self.ai is None and self.planned is not None and elapsed >= self.delay:
                self.ai = grade(self.planned == q.answer, self.delay)
                self.ai_status.configure(text=f"{self.opponent_name}: {app.tr('已锁定答案')}")
                self.thinking_status.configure(text=app.tr("我选好了，等你一起揭晓。"))
            if self.ai is None and elapsed >= ROUND_SECONDS:
                if self.decision is None:
                    self.decision_error = app.tr("等待对手决策超时。")
                self.ai = grade(False, ROUND_SECONDS + 1)
            if self.player is None and elapsed >= ROUND_SECONDS:
                self.answer(None, timed_out=True)
            if self.player is not None and self.ai is not None:
                self.finish_round()
                return
            self.timer_id = app.root.after(100, tick)

        tick()

    def receive_decision(self, response, error, elapsed):
        """Reject late responses before assigning an answer or scoring it."""
        if error or elapsed >= ROUND_SECONDS:
            self.decision = None
            self.planned = None
            self.decision_error = error or self.app.tr("等待对手决策超时。")
            self.ai = grade(False, ROUND_SECONDS + 1)
            self.ai_status.configure(text=self.app.tr("AI 服务不可用，本题未作答"))
            return
        self.decision = response
        self.planned, self.delay = response
        self.delay = max(self.delay, elapsed)

    def answer(self, value, timed_out=False):
        if self.player is not None:
            return
        elapsed = ROUND_SECONDS + 1 if timed_out else time.monotonic() - self.started
        self.player = grade(value == self.questions[self.index].answer, elapsed)
        for button in self.buttons:
            button.state(["disabled"])
        self.player_status.configure(text=f"{self.player_name}: {self.app.tr('已锁定答案')}")

    def finish_round(self):
        if not self.active:
            return
        self.active = False
        if self.decision_error:
            self.ai_status.configure(
                text=self.app.tr("对手作答异常"), foreground=T.palette()["TEXT"]
            )
            self.show_expression("thinking")
            self.thinking_status.configure(
                text=self.app.tr("对手未返回有效答案，本题作废，不计分也不扣血。")
                + "\n\n"
                + self.app.tr("异常原因：")
                + self.decision_error
            )
            self.result.configure(text=self.app.tr("本题未结算，请重试。"))
            self.next.configure(text=self.app.tr("重试本题"), command=self.round)
            self.next.state(["!disabled"])
            self.fit_result()
            return
        q = self.questions[self.index]
        letter = chr(65 + q.options.index(self.planned)) if self.planned in q.options else "—"
        self.ai_status.configure(
            text=f"{self.opponent_name}: {letter}",
            foreground="#22C55E" if self.ai.correct else "#EF4444",
            font=T.TYPE_HEADING,
        )
        self.show_expression("correct" if self.ai.correct else "wrong")
        self.thinking_status.configure(
            text=self.app.tr("回答正确") if self.ai.correct else self.app.tr("再想一想")
        )
        self.records.append((self.player, self.ai))
        q = self.questions[self.index]
        self.player_hp, self.ai_hp = apply_damage(
            self.player_hp, self.ai_hp, self.player.total, self.ai.total
        )
        for label, hp in zip(self.hp_labels, (self.player_hp, self.ai_hp)):
            label.configure(text=f" {hp}/{self.max_hp}")
        chosen = self.planned
        record = self.app.tr(
            "本题 {0} · 我的选择：{1} · 正确答案：{2}", q.id, chosen or "—", q.answer
        )
        stage_titles = ("读题", "分析选项", "选择并检查")
        process = "\n\n".join(
            f"{index + 1}. {self.app.tr(title)}\n{summary}"
            for index, (title, summary) in enumerate(
                zip(stage_titles, self.decision.stages if self.decision else ())
            )
        )
        basis = (
            self.decision.basis
            if self.decision and self.decision.source == "api"
            else self.app.tr("这是按等级概率产生的模拟选择，不是模型解题决策。")
            if self.decision
            else self.app.tr("本题没有有效决策记录。")
        )
        explanation = (
            process
            + "\n\n"
            + record
            + "\n\n"
            + self.app.tr("作答时的决策依据：")
            + "\n"
            + basis
            + "\n\n"
            + self.app.tr("题库解析：")
            + "\n"
            + q.explanation
        )
        self.thinking_status.configure(text=explanation)
        self.result.configure(
            text=f"{self.app.tr('正确答案')}：{q.answer}\n{q.explanation}\n"
            f"{self.player_name} {self.player.correct} + {self.player.time} + {self.player.extra} = {self.player.total}\n"
            f"{self.opponent_name} {self.ai.correct} + {self.ai.time} + {self.ai.extra} = {self.ai.total}"
        )
        self.next.state(["!disabled"])
        self.fit_result()
        if self.player_hp == 0 or self.ai_hp == 0 or self.index == len(self.questions) - 1:
            self.next.configure(text=self.app.tr("查看结果"))

    def show_decision_stage(self, stage):
        """Replace the previous activity; never expose an opponent answer early."""
        if self.current_stage == stage:
            return
        self.current_stage = stage
        messages = (
            "先读题，看看它问的是什么……",
            "再看看各个选项，比较它们与题意是否相符……",
            "选一个答案，再检查有没有漏掉条件……",
        )
        self.thinking_status.configure(text=f"{stage + 1} / 3\n\n{self.app.tr(messages[stage])}")

    def show_expression(self, state):
        app = self.app
        sheet = app.project_root / "assets" / "battle" / "expressions.png"
        path = sheet if sheet.exists() else app.project_root / "AI-assistant-icon.png"
        try:
            self.portrait.image = portrait_image(
                app.root, path, state, T.px(190), sheet=path == sheet
            )
            self.portrait.configure(image=self.portrait.image)
        except (tk.TclError, OSError):
            self.portrait.configure(text="AI")

    def advance(self):
        self.index += 1
        if self.index < len(self.questions) and self.player_hp > 0 and self.ai_hp > 0:
            self.round()
            return
        app = self.app
        app.clear(app.tr("对战结果"), show_heading=False, back=self.setup)
        player = sum(pair[0].total for pair in self.records)
        ai = sum(pair[1].total for pair in self.records)
        app.label(
            app.tr("胜利")
            if self.player_hp > self.ai_hp
            else app.tr("平局")
            if self.player_hp == self.ai_hp
            else app.tr("惜败"),
            "Question.TLabel",
        )
        app.label(f"{self.player_name} {player} : {ai} {self.opponent_name}")
        app.label(f"HP {self.player_hp} : {self.ai_hp}")
        app.button(app.tr("再战一次"), self.setup, "Accent.TButton")

    def leave(self):
        if self.active and not messagebox.askyesno(
            self.app.tr("答题对战"), self.app.tr("退出当前对战？"), parent=self.app.root
        ):
            return
        self.active = False
        self.generation += 1
        self.setup()
