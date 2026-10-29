"""Question list, editable form and local image upload controls."""

import tkinter as tk
from dataclasses import asdict
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from uuid import uuid4

from .maintenance import QuestionEditor, import_image
from .models import Question, option_label
from .services import image_path


class EditorPage:
    """Use the application's scrollable content area without a second UI toolkit."""

    def __init__(self, app):
        self.app = app
        self.tr = app.tr
        self.repository = QuestionEditor(app.bank.folder, lambda: app.auth.require_admin(app.user))
        self.editing = False

    def show_list(self):
        if not self.app.check_admin():
            return
        self.editing = False
        app = self.app
        app.load_bank()
        app.clear(self.tr("题库管理"))
        app.label(self.tr("题库在本机账户间共享。新增、编辑或删除后立即生效；修改前自动备份。"))
        bar = ttk.Frame(app.body)
        bar.pack(fill="x", pady=8)
        self.search = tk.StringVar()
        self.subject = tk.StringVar(value=self.tr("全部"))
        ttk.Entry(bar, textvariable=self.search, width=28).pack(side="left", padx=4)
        ttk.Combobox(
            bar,
            textvariable=self.subject,
            state="readonly",
            width=18,
            values=[self.tr("全部")] + sorted({q.subject for q in app.questions}),
        ).pack(side="left", padx=4)
        ttk.Button(bar, text=self.tr("搜索 / 筛选"), command=self.refresh_list).pack(
            side="left", padx=4
        )
        app.label(self.tr("搜索 ID、题干或主题；选中一行后编辑或删除。"))
        table_frame = ttk.Frame(app.body)
        table_frame.pack(fill="x")
        table_frame.columnconfigure(0, weight=1)
        self.table = ttk.Treeview(
            table_frame,
            columns=("id", "subject", "topic", "difficulty", "text"),
            show="headings",
            height=12,
            selectmode="browse",
        )
        for column, title, width in [
            ("id", "ID", 105),
            ("subject", self.tr("学科"), 110),
            ("topic", self.tr("主题"), 110),
            ("difficulty", self.tr("难度"), 70),
            ("text", self.tr("题干"), 300),
        ]:
            self.table.heading(column, text=title)
            self.table.column(column, width=width, minwidth=50)
        self.table.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        scroll.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.table.bind("<Double-1>", lambda event: self.edit_selected())
        self.summary = app.label("")
        actions = ttk.Frame(app.body)
        actions.pack(fill="x", pady=8)
        for title, callback in [
            (self.tr("新增题目"), self.edit),
            (self.tr("编辑选中题目"), self.edit_selected),
            (self.tr("删除选中题目"), self.delete_selected),
            (self.tr("返回首页"), app.home),
        ]:
            ttk.Button(actions, text=title, command=callback).pack(side="left", padx=4)
        if app.bank.warnings:
            app.label(self.tr("题库诊断：\n") + "\n".join(app.bank.warnings))
        self.refresh_list()

    def refresh_list(self):
        self.table.delete(*self.table.get_children())
        term = self.search.get().strip().casefold()
        matches = [
            q
            for q in self.app.questions
            if (self.subject.get() == self.tr("全部") or q.subject == self.subject.get())
            and term in f"{q.id} {q.question} {q.topic}".casefold()
        ]
        for q in matches:
            self.table.insert(
                "", "end", iid=q.id, values=(q.id, q.subject, q.topic, q.difficulty, q.question)
            )
        self.summary.configure(
            text=self.tr("显示 {0} / {1} 道题", len(matches), len(self.app.questions))
        )

    def selected(self):
        selection = self.table.selection()
        if not selection:
            messagebox.showinfo(
                self.tr("请选择题目"), self.tr("先在列表中选中一道题。"), parent=self.app.root
            )
            return None
        return self.app.by_id[selection[0]]

    def edit_selected(self):
        question = self.selected()
        if question:
            self.edit(question)

    def delete_selected(self):
        question = self.selected()
        if question and messagebox.askyesno(
            self.tr("删除题目"),
            self.tr("确定删除 {0}？\n原题库将备份，已有错题记录保留。", question.id),
            parent=self.app.root,
        ):
            try:
                self.repository.delete(question)
            except ValueError as exc:
                messagebox.showerror(self.tr("删除失败"), self.tr(str(exc)), parent=self.app.root)
                return
            self.show_list()

    def edit(self, question=None):
        if not self.app.check_admin():
            return
        app = self.app
        self.original = question
        self.editing = True
        self.rows = []
        app.clear(self.tr("编辑题目") if question else self.tr("新增题目"))
        app.label(self.tr("带 * 为必填。题干和选项可分别附图；选择一个正确选项，然后预览或保存。"))
        data = (
            asdict(question)
            if question
            else {
                "id": "Q-" + uuid4().hex[:12],
                "subject": "",
                "topic": "",
                "difficulty": "easy",
                "question": "",
                "explanation": "",
                "options": ["", "", "", ""],
                "question_image": None,
            }
        )
        self.fields = {}
        for key, title in [
            ("id", self.tr("题目 ID *（保存后不可修改）")),
            ("subject", self.tr("学科 *（可新增）")),
            ("topic", self.tr("主题 *（可新增）")),
            ("difficulty", self.tr("难度 *（可新增）")),
        ]:
            app.label(title)
            var = tk.StringVar(value=data[key])
            self.fields[key] = var
            choices = sorted({getattr(q, key) for q in app.questions}) if key != "id" else []
            entry = ttk.Combobox(app.body, textvariable=var, values=choices, width=42)
            if key == "id" and question:
                entry.state(["disabled"])
            entry.pack(anchor="w")
        app.label(self.tr("题干 *"))
        self.question_text = tk.Text(app.body, height=3, width=65, wrap="word")
        self.question_text.insert("1.0", data["question"])
        self.question_text.pack(fill="x")
        self.question_image = tk.StringVar(value=data["question_image"] or "")
        self.image_control(app.body, self.question_image)
        app.label(self.tr("答案选项 *（至少 2 项；圆钮表示正确答案）"))
        self.answer_index = tk.IntVar(
            value=question.options.index(question.answer) if question else 0
        )
        self.options_frame = ttk.Frame(app.body)
        self.options_frame.pack(fill="x")
        for index, text in enumerate(data["options"]):
            images = data.get("option_images")
            self.add_option(text, images[index] if images else None)
        buttons = ttk.Frame(app.body)
        buttons.pack(anchor="w", pady=5)
        ttk.Button(buttons, text=self.tr("添加选项"), command=self.add_option).pack(
            side="left", padx=4
        )
        ttk.Button(buttons, text=self.tr("移除最后一个选项"), command=self.remove_option).pack(
            side="left", padx=4
        )
        app.label(self.tr("解析 *"))
        self.explanation = tk.Text(app.body, height=3, width=65, wrap="word")
        self.explanation.insert("1.0", data["explanation"])
        self.explanation.pack(fill="x")
        app.button(self.tr("预览题目"), self.preview)
        app.button(self.tr("保存题目"), self.save)
        app.button(self.tr("取消并返回列表"), self.cancel)
        self.initial = self.snapshot()

    def add_option(self, text="", image=None):
        frame = ttk.LabelFrame(
            self.options_frame, text=self.tr("选项 {0}", option_label(len(self.rows))), padding=8
        )
        frame.pack(fill="x", pady=5)
        value = tk.StringVar(value=text)
        path = tk.StringVar(value=image or "")
        ttk.Radiobutton(
            frame, text=self.tr("正确答案"), variable=self.answer_index, value=len(self.rows)
        ).pack(anchor="w")
        ttk.Entry(frame, textvariable=value, width=65).pack(fill="x")
        self.image_control(frame, path)
        self.rows.append((frame, value, path))

    def remove_option(self):
        if len(self.rows) <= 2:
            messagebox.showinfo(
                self.tr("保留选项"), self.tr("单选题至少需要两个选项。"), parent=self.app.root
            )
            return
        self.rows.pop()[0].destroy()
        if self.answer_index.get() >= len(self.rows):
            self.answer_index.set(0)

    def image_control(self, parent, variable):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=6)
        ttk.Label(frame, textvariable=variable, wraplength=430).pack(anchor="w")
        ttk.Button(frame, text=self.tr("上传图片"), command=lambda: self.upload(variable)).pack(
            side="left", padx=3
        )
        ttk.Button(
            frame, text=self.tr("查看图片"), command=lambda: self.preview_image(variable)
        ).pack(side="left", padx=3)
        ttk.Button(frame, text=self.tr("移除图片"), command=lambda: variable.set("")).pack(
            side="left", padx=3
        )

    def upload(self, variable):
        if not self.app.check_admin():
            return
        source = filedialog.askopenfilename(
            parent=self.app.root,
            title=self.tr("选择本地图片"),
            filetypes=[(self.tr("图片"), "*.png *.gif *.ppm *.pgm")],
        )
        if not source:
            return
        try:
            relative = import_image(self.app.project_root, Path(source), self.app.root)
            variable.set(relative)
            self.preview_image(variable)
        except ValueError as exc:
            messagebox.showerror(self.tr("上传失败"), self.tr(str(exc)), parent=self.app.root)

    def render_image(self, parent, value, references):
        if not value:
            return
        try:
            photo = tk.PhotoImage(
                master=self.app.root, file=str(image_path(self.app.project_root, value))
            )
            factor = max(1, (photo.width() + 479) // 480, (photo.height() + 219) // 220)
            photo = photo.subsample(factor)
            references.append(photo)
            ttk.Label(parent, image=photo).pack(anchor="w", pady=4)
        except (ValueError, tk.TclError, OSError) as exc:
            ttk.Label(parent, text=self.tr("图片无法显示：{0}", exc), wraplength=500).pack(
                anchor="w"
            )

    def preview_window(self, title):
        window = tk.Toplevel(self.app.root)
        window.title(title)
        window.geometry("650x650")
        canvas = tk.Canvas(window)
        scroll = ttk.Scrollbar(window, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        content = ttk.Frame(canvas, padding=16)
        item = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=e.width))
        window.image_references = []
        return window, content

    def preview_image(self, variable):
        if variable.get():
            window, content = self.preview_window(self.tr("图片预览"))
            self.render_image(content, variable.get(), window.image_references)

    def snapshot(self):
        return (
            {key: var.get() for key, var in self.fields.items()},
            self.question_text.get("1.0", "end-1c"),
            self.explanation.get("1.0", "end-1c"),
            self.question_image.get(),
            [(text.get(), image.get()) for _, text, image in self.rows],
            self.answer_index.get(),
        )

    def can_leave(self):
        return (
            not self.editing
            or self.snapshot() == self.initial
            or messagebox.askyesno(
                self.tr("未保存的修改"), self.tr("放弃当前题目的未保存修改？"), parent=self.app.root
            )
        )

    def cancel(self):
        if self.can_leave():
            self.show_list()

    def build_question(self):
        options = [value.get().strip() for _, value, _ in self.rows]
        fields = {key: var.get().strip() for key, var in self.fields.items()}
        if any(fields[key] in {"全部", "All"} for key in ("topic", "difficulty", "subject")):
            raise ValueError(self.tr("“全部”是筛选保留名称，请换一个名称。"))
        data = {
            **fields,
            "type": "single_choice",
            "options": options,
            "answer": options[self.answer_index.get()],
            "question": self.question_text.get("1.0", "end-1c").strip(),
            "explanation": self.explanation.get("1.0", "end-1c").strip(),
            "question_image": self.question_image.get() or None,
            "option_images": [image.get() or None for _, _, image in self.rows],
        }
        return Question.from_dict(data)

    def preview(self):
        try:
            q = self.build_question()
        except ValueError as exc:
            messagebox.showerror(self.tr("请完善题目"), self.tr(str(exc)), parent=self.app.root)
            return
        window, content = self.preview_window(self.tr("题目预览"))
        for text in [f"{q.subject} / {q.topic} / {q.difficulty}", q.question]:
            ttk.Label(content, text=text, wraplength=550).pack(anchor="w", pady=5)
        self.render_image(content, q.question_image, window.image_references)
        for index, option in enumerate(q.options):
            ttk.Label(content, text=f"{option_label(index)}: {option}", wraplength=550).pack(
                anchor="w", pady=5
            )
            self.render_image(content, q.option_images[index], window.image_references)
        ttk.Label(
            content,
            text=self.tr("正确答案：{0}\n解析：{1}", q.answer, q.explanation),
            wraplength=550,
        ).pack(anchor="w")

    def save(self):
        try:
            self.repository.save(self.build_question(), self.original)
        except ValueError as exc:
            messagebox.showerror(self.tr("保存失败"), self.tr(str(exc)), parent=self.app.root)
            return
        self.editing = False
        self.show_list()
        messagebox.showinfo(
            self.tr("保存成功"), self.tr("题库已更新，可以返回首页开始练习。"), parent=self.app.root
        )
