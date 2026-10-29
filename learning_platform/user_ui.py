"""Administrator-only account editing and read-only learning-data inspection."""

import tkinter as tk
from tkinter import messagebox, ttk


class UserPage:
    def __init__(self, app):
        self.app = app
        self.tr = app.tr
        self.editing = False

    def show_list(self):
        app = self.app
        try:
            users = app.auth.list_users(app.user)
        except ValueError as exc:
            app.access_error(exc)
            return
        self.editing = False
        app.clear(self.tr("用户管理"))
        app.label(
            self.tr("管理员可查看学习数据、修改账号、重置密码、停用登录或调整角色。密码不会显示。")
        )
        frame = ttk.Frame(app.body)
        frame.pack(fill="x")
        self.table = ttk.Treeview(
            frame, columns=("name", "role", "status"), show="headings", height=12
        )
        for key, title in [
            ("name", self.tr("用户名")),
            ("role", self.tr("角色")),
            ("status", self.tr("状态")),
        ]:
            self.table.heading(key, text=title)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.table.pack(fill="x")
        self.users = {user["id"]: user for user in users}
        for user in users:
            self.table.insert(
                "",
                "end",
                iid=user["id"],
                values=(
                    user["name"],
                    self.tr("管理员") if user["role"] == "admin" else self.tr("普通用户"),
                    self.tr("启用") if user["enabled"] else self.tr("停用"),
                ),
            )
        app.button(self.tr("新增账户"), self.edit)
        app.button(self.tr("修改选中账户 / 重置密码"), self.edit_selected)
        app.button(self.tr("查看选中账户学习数据"), self.details)
        app.button(self.tr("刷新列表"), self.show_list)
        app.button(self.tr("返回首页"), app.home)

    def selected(self):
        selection = self.table.selection()
        if not selection:
            messagebox.showinfo(
                self.tr("请选择账户"), self.tr("先在列表中选中一个账户。"), parent=self.app.root
            )
            return None
        return self.users[selection[0]]

    def edit_selected(self):
        user = self.selected()
        if user:
            self.edit(user)

    def edit(self, user=None):
        if not self.app.check_admin():
            return
        self.original = user
        self.editing = True
        app = self.app
        app.clear(self.tr("修改账户") if user else self.tr("新增账户"))
        app.label(self.tr("修改用户名不会丢失学习记录。密码 6–16 位；编辑时留空表示保留原密码。"))
        self.name = tk.StringVar(value=user["name"] if user else "")
        self.password = tk.StringVar()
        self.confirmation = tk.StringVar()
        for title, var, secret in [
            (self.tr("用户名"), self.name, False),
            (self.tr("新密码"), self.password, True),
            (self.tr("确认密码"), self.confirmation, True),
        ]:
            app.label(title)
            ttk.Entry(app.body, textvariable=var, show="•" if secret else "", width=40).pack(
                anchor="w"
            )
        self.role = tk.StringVar(value=user["role"] if user else "student")
        app.label(self.tr("角色"))
        ttk.Radiobutton(
            app.body, text=self.tr("普通用户"), variable=self.role, value="student"
        ).pack(anchor="w")
        ttk.Radiobutton(app.body, text=self.tr("管理员"), variable=self.role, value="admin").pack(
            anchor="w"
        )
        self.enabled = tk.BooleanVar(value=user["enabled"] if user else True)
        ttk.Checkbutton(
            app.body, text=self.tr("允许登录（取消勾选即停用）"), variable=self.enabled
        ).pack(anchor="w", pady=10)
        app.button(self.tr("保存账户"), self.save)
        app.button(self.tr("取消并返回列表"), self.cancel)
        self.initial = self.snapshot()

    def snapshot(self):
        return (
            self.name.get(),
            self.password.get(),
            self.confirmation.get(),
            self.role.get(),
            self.enabled.get(),
        )

    def can_leave(self):
        return (
            not self.editing
            or self.snapshot() == self.initial
            or messagebox.askyesno(
                self.tr("未保存的修改"), self.tr("放弃当前账户的未保存修改？"), parent=self.app.root
            )
        )

    def cancel(self):
        if self.can_leave():
            self.show_list()

    def save(self):
        try:
            if self.password.get() != self.confirmation.get():
                raise ValueError(self.tr("两次密码不一致。"))
            if self.original:
                self.app.auth.update_user(
                    self.app.user,
                    self.original["id"],
                    self.name.get(),
                    self.role.get(),
                    self.enabled.get(),
                    self.password.get(),
                )
            else:
                self.app.auth.create_user(
                    self.app.user,
                    self.name.get(),
                    self.password.get(),
                    self.role.get(),
                    self.enabled.get(),
                )
        except ValueError as exc:
            messagebox.showerror(self.tr("保存失败"), self.tr(str(exc)), parent=self.app.root)
            return
        self.password.set("")
        self.confirmation.set("")
        self.editing = False
        if not self.app.check_admin():
            return
        self.show_list()

    def details(self):
        user = self.selected()
        if not user:
            return
        try:
            data = self.app.auth.user_progress(self.app.user, user["id"])
        except ValueError as exc:
            messagebox.showerror(self.tr("无法读取数据"), self.tr(str(exc)), parent=self.app.root)
            return
        app = self.app
        app.clear(self.tr("学习数据：{0}", user["name"]))
        app.label(
            self.tr(
                "完成练习：{0} 次；待复习错题：{1} 道。", len(data["history"]), len(data["wrong"])
            )
        )
        app.button(self.tr("返回用户列表"), self.show_list)
        for record in reversed(data["history"]):
            app.label(
                self.tr(
                    "{0} · {1} · 得分 {2}/{3} · 正确率 {4}%",
                    record["date"],
                    record["subject"],
                    record["score"],
                    record["max_score"],
                    f"{record['accuracy']:.2f}",
                )
            )
        app.label(self.tr("错题记录"))
        for key, record in data["wrong"].items():
            q = app.by_id.get(key)
            app.label(
                self.tr(
                    "{0} · 答错 {1} 次 · 上次选择：{2} · {3}",
                    key,
                    record["count"],
                    record["last_answer"],
                    record["last_seen"],
                )
            )
            if q:
                app.question_content(q)
            else:
                app.label(self.tr("题目已删除或无效。"))
