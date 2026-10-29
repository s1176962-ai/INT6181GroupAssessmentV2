# 小组协作说明

本项目使用 GitHub 私有仓库。仓库所有者邀请小组成员并授予写入权限后，成员才能推送代码。程序中的管理员身份不等于 GitHub 仓库权限。

## 日常修改

先在仓库根目录打开终端，然后执行：

```powershell
git switch main
git pull --ff-only
git switch -c feature/your-change
```

修改代码后运行：

```powershell
python -m unittest discover -s tests -v
```

检查将提交的文件，不要提交账户、学习记录、密码或其他秘密：

```powershell
git status
git add <要提交的文件路径>
git diff --cached
git commit -m "Describe the change"
git push -u origin feature/your-change
```

在 GitHub 创建 Pull Request，请另一名成员检查后再合并到 main。不同成员使用不同分支；不要强制推送覆盖其他人的修改。合并后每个人拉取最新 main。

## 数据与文档

- 代码、示例题库、示例图片、测试与文档纳入版本控制。
- `users.json`、个人进度、语言设置、账户/题库备份和缓存不提交。GitHub 不会同步大家的本机账户和学习记录。
- 全新克隆没有真实账户，也没有自动授予管理员的默认账户；注册得到普通用户。需要测试管理员功能时，由项目维护者在各自本机配置，不上传现有 users.json。
- 新增功能时同步 `specification.md`、相关测试、注释和变更记录。代码规范见 `docs/DEVELOPMENT.md`。
- 题库编辑可能同时修改同一个 JSON 文件，最好预先分配不同学科或题目；发生冲突后保留双方需要的题目并检查 ID 唯一性。
