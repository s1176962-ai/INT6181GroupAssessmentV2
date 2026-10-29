# 开发与维护规范

## 职责边界

- `models.py`：题目 schema、纯计分逻辑。
- `storage.py`：JSON 读写、文件错误、原子替换。
- `repositories.py`：题库加载、进度校验。
- `services.py`：抽题、答题状态、错题规则、历史事务。
- `auth.py`：账户校验、密码哈希、角色和启用状态校验、用户管理、个人进度路径。
- `maintenance.py`：增删改、备份、过期编辑检测、图片导入。
- `gui.py`：登录、主菜单、练习、错题、历史。
- `user_ui.py`：管理员账户编辑与只读学习数据查看。
- `i18n.py` / `locales/en.json`：显式界面翻译目录及语言持久化，不翻译题库数据。
- `editor_ui.py`：题库列表、表单、图片控件及预览。

## 代码约定

Python 3.10+，UTF-8，4 空格缩进；模块/函数使用 snake_case，类使用 PascalCase，常量使用 UPPER_CASE。Ruff 统一格式与导入顺序，目标行宽 100。可复用账户及维护服务公开接口添加类型注解；复杂数据流用 docstring 或短注释解释原因，避免逐行重复代码含义。

注释重点：UUID 路径、提交先落盘再更新状态、备份不进入题库扫描目录、编辑保留扩展字段。行为变化时同步注释、测试、`specification.md` 和 `CHANGELOG.md`，不在代码中堆叠历史改动注释。

## 开发检查

Ruff 仅用于开发，不是运行依赖。

```powershell
python -m pip install ruff==0.17.2
python -m ruff check .
python -m ruff format --check .
python -m unittest discover -s tests -v
python -m compileall -q learning_platform main.py tests
```

格式化使用 `python -m ruff format .`。测试使用临时账户、题库和进度，不写真实存档。样本测试按交付的 60 道题验证；调整内置题目数量时同步预期和需求文档。

## 数据维护

请关闭其他实例再修改。备份位于 `data/backups/`；恢复时先退出，备份当前文件，将选定快照复制回原 `data/questions/<文件名>.json`。不要把备份放进题库目录而保留两个同 ID 版本。图片与 JSON 分开备份；解除图片关联不清理文件，避免破坏历史备份。

账户、个人档案和备份已被 `.gitignore` 排除；分享项目时不要打包真实用户数据。所有本地账户共享题库，只有管理员可以维护。当前没有并发文件锁、自助密码找回或云同步。

## 权限与翻译维护

管理员操作必须通过 `require_admin` 重新读取持久化角色，禁止仅信任界面缓存。普通注册必须保持 student，禁止按用户名自动提升权限。停用状态应在会话继续使用时检查；修改账号保留 UUID；始终保留一个启用的管理员。

界面文字使用 `self.tr(中文模板, 参数...)`，动态内容用位置占位符；英文译文放入 `locales/en.json`，保持占位符一致。不要翻译题干、选项、用户名或路径等用户数据。新增文案需通过目录覆盖率和占位符一致性测试。
