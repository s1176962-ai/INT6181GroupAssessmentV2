# SRS Guide and Implementation Mapping

Updated: 2026-11-13. English first, followed by Chinese.

## English

### Authoritative requirements

[specification.md](../specification.md) is the complete English-first bilingual SRS. Matching requirement IDs are used in both languages. This file explains implementation decisions and maps requirements to modules; it does not maintain a separate competing specification. The original guide is preserved in [the archive](archive/SRS_GUIDE_PRE_BILINGUAL_20261113.md).

### Implementation decisions

- One Python/Tkinter desktop UI with local JSON. Core practice remains offline; optional assistant/API battles use configured HTTPS services. PDF export requires ReportLab.
- UUID-based account isolation, persisted administrator/student roles and enabled status. Public registration never grants administrator privileges. Permission checks protect mutations even when an editor was opened before disablement or demotion.
- Public banks are readable for practice by everyone and writable by administrators. Students manage their own personal questions; administrators may select any owner for moderation. Cross-owner bulk import/public publishing remains out of scope.
- Normal quizzes award one point for each correct answer. Mistakes are saved immediately; only correct review removes them. Manually abandoned sessions do not create completed history, while timeouts save partial results without treating unanswered items as mistakes.
- Daily plans and session likes/notes use separate profile files. Journal queries and PDF exports share an inclusive local-date filter and the same timestamp conversion.
- JSON/CSV imports validate and preview rows before confirmation, bind the target and recheck duplicates and authorization. Mutations preserve corrupt source data, create backups and reject stale edits.
- Normal quiz assistance has a first hint and a second explanation. API battles submit one structured decision with concise summaries and optional labelled images; no answer key is sent. Reading/comparison/checking activity is simulated UI progress, not an internal reasoning transcript.
- Battle correctness and speed produce a score difference that reduces the losing side's HP. API failures, invalid decisions and late responses void the round without points or damage.
- All fixed report text/metadata is English; source questions and notes retain their language. PDF/CSV timestamps use local `yyyy/mm/dd hh:mm:ss`, with the timezone labelled in PDF. Latin typography and Unicode fallback preserve full-width punctuation such as `！`.
- Responsive controls, fixed quiz actions, bounded image caching and timer cleanup reduce unnecessary work without changing stored learning data. Settings support language, theme, window size and optional wheel selection.

### Requirement-to-module mapping

| Requirement | Implementation |
| --- | --- |
| FR-01 Home/navigation | `gui.Application.home`, sidebar and chrome |
| FR-02 Configuration | `gui.Application.configure`, `services.select_questions`, `modern.Stepper` |
| FR-03 Question data | `models.Question`, `repositories.QuestionRepository` |
| FR-03A Daily plan | `repositories.LearningPlanRepository`, daily-plan GUI |
| FR-04 Quiz | `services.QuizEngine`, `gui.Application.show_question` |
| FR-04A Companion | `ai_assistant.py`, quiz/home assistant UI |
| FR-05 Images | `gui.Application.show_image`, `image_cache.py`, `assets/` |
| FR-06 Notebook | `services.QuizEngine.submit`, `gui.Application.notebook` |
| FR-07 History | `models.score`, `repositories.ProgressRepository`, `history_ui.py` |
| FR-07A Likes/notes/queries | `history_notes.py`, `history_ui.py`, `date_picker.py` |
| FR-08 Persistence | `storage.JsonStore`, repositories and backup services |
| FR-09 Validation/import | `models.py`, `importing.py`, import preview UI |
| FR-10 Accounts | `auth.AuthService`, `login_preferences.py`, login GUI |
| FR-11 Bank maintenance | `maintenance.QuestionEditor`, `bank_access.ManagedPersonalBank`, `editor_ui.py` |
| FR-12 Image import | `maintenance.import_image`, editor image controls |
| FR-13 Sample banks | `data/questions/` and `assets/` |
| FR-14 User management | `auth.py`, `user_ui.UserPage`, fresh service authorization |
| FR-15 Letter labels | `models.option_label`, quiz/editor/report presentation |
| FR-16 Language/theme | `i18n.Translator`, `locales/en.json`, design tokens |
| FR-17 Battles | `battle.py`, `battle_ui.py`, structured/image API requests |
| FR-18 Reports | `exports.py`, `pdf_report.py`, `history_notes.display_time` |
| FR-19 Display | `display.py`, `modern.py`, `gui.py`, fixed action docks |
| NFR-01 to NFR-06 | Layered modules, bounded caches, error handling, tests and guides |

### Verification and limitations

Run `python -m unittest discover -s tests -v`, `python -m ruff check .` and `python -m compileall -q learning_platform tests`. Tests use temporary profiles and mocked networking where appropriate. Real API checks are reported separately and do not establish general model accuracy. Local files are not protected from someone with filesystem access, atomic writes do not provide multiprocess locking, and cancelled image edits may leave unused resources.

See [README](../README.md), [test cases](TEST_CASES.md), [test report](TEST_REPORT.md), [development conventions](DEVELOPMENT.md), [battle rules](BATTLE.md), [import rules](QUESTION_BANK_IMPORT.md), [V2 integration history](V2_INTEGRATION.md) and [changelog](CHANGELOG.md).

## 中文

### 权威需求

[specification.md](../specification.md) 是完整的英文优先双语 SRS，两种语言使用对应需求 ID。本文件记录实现决策及模块对应，不维护另一份有冲突的完整规格。原说明保存在[归档](archive/SRS_GUIDE_PRE_BILINGUAL_20261113.md)。

### 实现决策

- 统一 Python/Tkinter 桌面 UI 与本地 JSON，核心练习离线；可选伴学/API 对战使用配置的 HTTPS 服务，PDF 需要 ReportLab。
- UUID 隔离账户，持久化角色和启用状态，公开注册不提权；即使编辑页早于停用/降级打开，写入仍受当前权限保护。
- 所有人可练公共题，管理员维护公共库；普通用户维护本人，管理员按所属用户监管全部个人题库。跨用户导入和公开发布不在范围内。
- 普通答对 1 分，错题立即存，正确复习才移除。手动退出不产生完整历史，超时保存部分结果，未答不记错。
- 每日计划、每轮点赞/笔记使用独立文件；学习记录查询和 PDF 使用相同的包含首尾日期过滤与本机时间转换。
- JSON/CSV 导入先校验预览再确认，绑定目标题库并复查去重和权限；保留损坏数据，写前备份，拒绝过期编辑。
- 普通伴学先提示再讲解；API 对战一次提交结构化选择、简短摘要及可选标记图片，不传答案键。读题/比较/检查是模拟界面进度，不是内部思维实录。
- 正确分和时间分形成分差并扣除低分方血量；失败、非法或迟到决策使轮次作废，不计分不扣血。
- 固定报告文案和属性始终英文，题目和笔记保留原文；时间为本机 yyyy/mm/dd hh:mm:ss，PDF 标明时区。英文字体与 Unicode 回退保留全角 `！` 等字符。
- 响应式控件、固定操作栏、有上限图片缓存与回调清理减少冗余，不修改学习数据；设置包含语言、主题、窗口和可选滚轮切换。

### 需求与模块对应

| 需求 | 实现 |
| --- | --- |
| FR-01 首页/导航 | `gui.Application.home`、侧栏和顶栏 |
| FR-02 配置 | `gui.Application.configure`、`services.select_questions`、`modern.Stepper` |
| FR-03 题目数据 | `models.Question`、`repositories.QuestionRepository` |
| FR-03A 每日计划 | `repositories.LearningPlanRepository`、计划设置界面 |
| FR-04 答题 | `services.QuizEngine`、`gui.Application.show_question` |
| FR-04A 伴学 | `ai_assistant.py`、首页和答题页助手 |
| FR-05 图片 | `gui.Application.show_image`、`image_cache.py`、`assets/` |
| FR-06 错题本 | `services.QuizEngine.submit`、`gui.Application.notebook` |
| FR-07 历史 | `models.score`、`repositories.ProgressRepository`、`history_ui.py` |
| FR-07A 点赞/笔记/查询 | `history_notes.py`、`history_ui.py`、`date_picker.py` |
| FR-08 持久化 | `storage.JsonStore`、仓库和备份服务 |
| FR-09 校验/导入 | `models.py`、`importing.py`、预览界面 |
| FR-10 账户 | `auth.AuthService`、`login_preferences.py`、登录页 |
| FR-11 维护 | `maintenance.QuestionEditor`、`bank_access.ManagedPersonalBank`、`editor_ui.py` |
| FR-12 图片上传 | `maintenance.import_image`、编辑器图片控件 |
| FR-13 示例题库 | `data/questions/` 和 `assets/` |
| FR-14 用户管理 | `auth.py`、`user_ui.UserPage`、即时权限校验 |
| FR-15 字母标签 | `models.option_label`、答题/编辑器/报告 |
| FR-16 语言/主题 | `i18n.Translator`、`locales/en.json`、设计令牌 |
| FR-17 对战 | `battle.py`、`battle_ui.py`、结构化/图片请求 |
| FR-18 导出 | `exports.py`、`pdf_report.py`、`history_notes.display_time` |
| FR-19 显示 | `display.py`、`modern.py`、`gui.py`、固定操作栏 |
| NFR-01 至 NFR-06 | 分层、有限缓存、异常处理、测试及使用文档 |

### 验证与限制

运行 `python -m unittest discover -s tests -v`、`python -m ruff check .` 及 `python -m compileall -q learning_platform tests`。测试使用临时账户和适当的模拟网络；真实联调单独记录，不代表普遍正确率。本地文件不防直接访问，原子写入不是多进程锁，取消图片编辑可留下未引用文件。

参考 [README](../README.md)、[测试用例](TEST_CASES.md)、[测试报告](TEST_REPORT.md)、[开发规范](DEVELOPMENT.md)、[对战](BATTLE.md)、[导入](QUESTION_BANK_IMPORT.md)、[整合历史](V2_INTEGRATION.md)和[变更](CHANGELOG.md)。
