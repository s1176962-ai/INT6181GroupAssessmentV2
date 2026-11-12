# 项目长期笔记 · INT6181GroupAssessmentV2

## 定位
完全离线的 Tkinter 桌面多学科（English / Mathematics / Science）单选练习平台，Python 3.10+，核心仅标准库 + JSON，PDF 导出才需 reportlab。正式目录 `D:\develop\workplace\INT6181GroupAssessmentV2`，启动 `python main.py` 或双击 `start.bat`（→ launcher.py 自检）。

## 架构速查
`main.py / __main__.py → gui.Application`（单类，4209 行，全部页面）→ 服务层 `services / auth / i18n / ai_assistant / importing / exports / maintenance / display / motion` → 仓储层 `repositories / login_preferences / pdf_report / widgets` → `storage.JsonStore`（临时文件 + fsync + os.replace 原子写）→ `data/*.json`、`data/profiles/<uuid>/`、`assets/`。无循环导入。`user_ui.UserPage` / `editor_ui.EditorPage` 通过 app 回调反向调用 UI 方法。

页面切换靠方法直调 + `clear(title, back=)` 销毁重建，无路由/页面栈；滚动为单 Canvas + create_window；状态全在 Application 实例属性；仅登录 PBKDF2 与 AI 请求两处后台线程，UI 更新回主线程 after。

## 关键约定
- **测试必须用 `py -3`**（项目 Python 3.13.9 + Tk 8.6 + reportlab）：`py -3 -m unittest discover -s tests`，当前 **84 项全通过**。内置 Python 缺 tkinter/reportlab 会误报 5 个 error。
- `specification.md` 是唯一权威 SRS；`docs/SRS.md` 只是索引映射表；`docs/archive/v2-before-integration/` 全为历史快照；`docs/V2_INTEGRATION.md` 是当前整合状态；`docs/CHANGELOG.md` 是版本时间线。
- 视觉规范：`DESIGN.md` v2.2 必须与 `learning_platform/ui_tokens.py` 同步；后者是**运行时可切换调色板**（`THEMES={"dark","light"}` / `theme_name()` / `set_theme()`；深色 #0C0E11、浅色 #F6F7F9）。**所有颜色必须在渲染时按 `T.<TOKEN>` 读取**（`from . import ui_tokens as T`）；禁止直接 import 颜色值或写进函数默认值，否则切主题不生效。新增 token：`RAISED/NAV_BG/SCROLL_*/CHECK_*`。
- 主题与语言：新配置默认 `language=en` + `theme=dark`；主题存 `data/settings.json` 的 `theme`，经 `Translator.set_theme()` 持久化。切换走 `Application.apply_theme()`（重绘 ttk 样式 → 销毁重建 nav → `_rebuild_screen()` 按 `_nav_key` 重建当前页 → fade_in）。**新增页面必须同步 `_rebuild_screen()` 的 pages 映射并设置 `_nav_key`**，否则切主题会跳回错误页面。
- 动效：`motion.py` 纯 `root.after()` 帧循环（`fade_in/circle_transition/slide_prepare/submit_feedback/grow_progress/roll_count/paint_path`），无第三方依赖；settings 有 motion 开关，须尊重减弱动效。
- **范围边界（用户 2026-11-10 明确）：只改登录页，首页保持原 V2 四卡 2×2 布局，不要主动改首页**；首页美化必须等用户单独下指令。极简首页曾误做后已从备份恢复，快照在 `.workbuddy-ai/backup/gui-minimal-home.py`。
- 安全：密码 PBKDF2-HMAC-SHA256 600k 轮随机盐；AI Key 与「记住密码」用 DPAPI / macOS 钥匙串加密；`data/` 下账户、进度、备份不得提交（.gitignore 已配置）。分享项目时排除真实账户数据。
- 题库 schema：JSON 数组，字段 `id, subject, topic, difficulty, type, question, options, answer, explanation, question_image, option_images`；type 仅 `single_choice`；ID 为 ENG/MAT/SCI + 三位数字。新增题型须同步改 `models.py` / `services.py` / `gui.py` / `editor_ui.py` / `importing.py` / `exports.py` / `pdf_report.py` / `en.json`。

## 已完成（2026-11-10 第二阶段）
双主题可切换、**简约登录页重设计**（首页原样保留）、默认英文、词条与测试同步、DESIGN/README/CHANGELOG 更新；84 项测试全通过；双主题截图在 `.workbuddy-ai/preview/`。首页已按用户要求从 `.workbuddy-ai/backup/gui.py` 恢复并令牌化（脚本 `restore_home.py`）。

## 后续改造方向
1. 界面美观优化（剩余）：重绘浅色题图/占位图/学科图/PDF 以适配深色主题（**最大剩余视觉冲突**）；清剩余内联字体与符号化按钮（首页仍有 🔧）；删 `gui.py` 中 ~500 行 legacy 死代码并拆分 4209 行单类。**首页视觉改版需用户先明确同意**。
2. 创新功能（用户尚未选）：间隔重复、成就徽章/XP、数据可视化看板（可复活 `_plan_ring`/`_weekly_chart` 死代码）、自适应错题推荐、多题型、模拟考试/每题限时。
3. 文档：`specification.md` 仍写 AI「不在范围」且 FR-10「不记住密码」与实现矛盾；统一前不要以其做 PPT 事实源。
4. PPT：以 CHANGELOG + TEST_REPORT + V2_INTEGRATION + 本次改造为事实源；避开旧测试数量（54/61）、旧目录名、AI 范围等过时表述；仓库内缺老师评分表/rubric 与疑似「7 项任务清单」，做 PPT 前需向用户确认。
