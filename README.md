# WhaleMate

A configurable study companion with quizzes, personal question banks, guided help from Big Whale, and gamified player-versus-AI quiz battles.

**Quiz · Configure · Learn together**

Updated: 2026-11-13. English is presented first; an equivalent Chinese guide follows. This guide describes the current V2 implementation. Earlier documentation is retained in [the README archive](docs/archive/README_PRE_BILINGUAL_20261113.md); historical statements do not override this guide.

## English

### 1. Install and run

Use Python 3.10+ with Tcl/Tk. On Windows, double-click `start.bat` or run:

```powershell
cd D:\develop\workplace\INT6181GroupAssessmentV2
python -m pip install -r requirements.txt
python main.py
```

`python -m learning_platform` is another entry point. `python -m tkinter` checks Tk availability. The launcher checks the Python version, Tk and question directory; it does not install Python. Linux needs a graphical desktop and may require `python3-tk`. Core practice uses the standard library; ReportLab is required for PDF exports. Restart the application after changing code.

### 2. Accounts and permissions

Register a unique username of 3-32 word characters or hyphens and a matching password of 6-16 characters. Usernames are case-insensitive. Public registration always creates a student. Passwords are stored as randomly salted PBKDF2 hashes. Legacy longer passwords remain usable until reset.

| Role | Public practice and battles | Own personal bank | Notebook and learning history | Public-bank maintenance | All personal banks and user management |
| --- | --- | --- | --- | --- | --- |
| Guest | Yes | No | No | No | No |
| Student | Yes | Yes | Own profile only | No | No |
| Administrator | Yes | Yes | Own profile; other users through administration | Yes | Yes |

The previously migrated `wutaicheng` account retains its administrator role, credentials and UUID. Registering that name does not grant privileges. Administrators may create, rename, enable/disable and promote/demote accounts, reset passwords and inspect learning data. Renaming preserves the UUID. Password fields left blank during editing retain the existing password. The last enabled administrator cannot be removed or disabled.

Protected actions recheck persisted permissions. A disabled account cannot keep saving or deleting personal questions from an already-open form. Local profiles do not protect against someone who can edit the files directly.

The login form restores the last successful username. Remembering a password is optional and uses Windows DPAPI or macOS Keychain protection. No plaintext password is stored in the user table or committed configuration. Unchecking the option and logging in successfully clears the saved credential. Logout and account switching preserve profile isolation.

### 3. Configure and answer a quiz

Select the question bank first, then its subject, topic, difficulty, question count and optional session time limit. Guests use the public bank. Switching banks refreshes the available subjects and filters. Questions are shuffled without duplication; requests above the matching count use the available questions. An empty bank or no matches produces guidance instead of starting an empty quiz.

Numeric controls accept typing and +/- buttons. A session time limit of 0 means unlimited; the supported range is 0-86400 seconds. Submit one answer per question, then continue. Normal quizzes award one point for a correct answer and no negative points. Results include totals, accuracy and score.

The progress indicator stays at the top and primary actions stay at the bottom. Long question content and feedback can scroll. Selecting an answer or submitting it must not move the companion panel. Optional illustrations are shown when supplied; text-only questions do not receive an invented illustration.

Exiting an unfinished quiz keeps already-submitted wrong answers but does not create a completed history entry. Reaching the session limit saves the result with unanswered questions receiving no points; unanswered questions are not added to the notebook. Incomplete sessions cannot be resumed.

### 4. Question banks and imports

Students manage their own personal bank through the same question-bank centre used by administrators. Public questions are available for practice by everyone, but only administrators can add, edit, delete or import them. Personal questions remain private to their owner and administrators; publishing them publicly is not implemented.

Use search and subject filters, add/edit forms, image controls and preview. New subjects, topics and difficulty values can be entered without changing code. Each question needs at least two unique non-empty options and one correct answer that exactly matches an option. Existing IDs are immutable; stale edits are rejected.

Administrators can choose **All personal banks** and select an owner, or select a user in user management and open **Personal bank**. They can inspect, create, edit or remove that owner's questions. Changes are backed up before writing. Importing on behalf of another owner is not provided.

Public and personal imports use JSON/CSV selection, validation, preview and explicit confirmation. Invalid rows are identified; duplicate IDs/content are skipped. Confirmation rechecks permissions, the target bank and current duplicates before writing. The English preview uses **Validation passed**. Files are limited to 5 MB and 1,000 records.

- [JSON test file](examples/import_test_json.json) and [CSV test file](examples/import_test_csv.csv) contain three different questions each and can be imported consecutively.
- Repeat imports safely skip existing questions.
- Wrong-question CSV exports can be imported as review questions. Compatible legacy exports with a correct answer and a different last answer are accepted as two-option questions.
- See [import rules](docs/QUESTION_BANK_IMPORT.md) for templates, field definitions and duplicate handling.

The editor accepts PNG/GIF/PPM/PGM images, checks decoding, and limits uploads to 10 MB and 16 million pixels. Convert JPEG/WebP to PNG before editor upload. Files are copied to unique names under `assets/uploads/`; source files are not moved. Removing an image reference does not delete a file that other questions or backups may need.

Example JSON (top-level array):

```json
[
  {
    "id": "NEW001",
    "subject": "New Subject",
    "topic": "Shapes",
    "difficulty": "easy",
    "type": "single_choice",
    "question": "Which shape has four equal sides and four right angles?",
    "options": ["Circle", "Square"],
    "answer": "Square",
    "explanation": "A square has four equal sides and four right angles.",
    "question_image": null,
    "option_images": [null, null]
  }
]
```

Public files live under `data/questions/`; personal files live under `data/profiles/<UUID>/questions.json`. Direct JSON changes require reloading or restarting. Public additions are stored in `custom.json`. Changes preserve unrelated records; source files are backed up. Corrupt personal data is reported instead of silently overwritten.

### 5. Daily goals, notebook and learning journal

The home goal card shows the selected bank, subject, difficulty and progress. Its wrench opens daily-plan settings, including a daily quantity of 1-500 questions. **Continue today's practice** starts matching practice directly for the remaining quantity. Submitted answers immediately update daily activity, including submissions in an unfinished quiz. Plans and answer events are stored separately from progress.

The wrong-question notebook belongs to the signed-in account. Repeated mistakes increase a question's count. Only a correct answer in review removes a mistake; a correct normal-quiz answer does not. Deleted questions retain a readable unavailable entry.

The learning journal supports likes and notes on **session records**, inclusive date-range queries, liked/note-presence filters and summary cards for the current query. Use the calendar controls or `yyyy/mm/dd`. A liked heart is blue; an unliked heart is white. Notes and likes are saved separately in `history_notes.json` without changing the legacy progress schema. Older records do not contain per-question answer details.

### 6. Big Whale study companion

Configure the HTTPS endpoint, model and protected API key in Settings. The home card offers a single-turn study question. In a normal quiz, **Ask Big Whale** provides a guiding hint on the first request and an explanation with the answer on the second. Failed requests may be retried. The companion uses thinking/correct/incorrect expressions and local encouragement after submission; the bottom answer feedback does not call an API.

Normal-quiz assistance sends text only. The first hint does not include the answer key; the second request includes the reference answer and explanation. It does not send images, account credentials, profiles or learning history. Normal assistance limits input to 2,500 characters and output to 320 tokens. See [assistant prompts](docs/AI_ASSISTANT_PROMPT.md). API use requires connectivity and may incur provider charges; core practice remains offline.

### 7. Quiz battles

All roles can enter battles from the sidebar. Both sides answer the same public-bank question within 30 seconds. Levels are Beginner, Normal, Hard and Hell, with simulated timing ranges of 12-24, 8-18, 4-12 and 2-7 seconds respectively. Local simulation uses correctness probabilities of 50%, 72%, 88% and 97%; API levels guide checking behaviour and timing rather than guaranteeing those accuracy rates.

Correct answers earn 100 points. Correct responses within 5/10/15/20/30 seconds receive +50/+40/+30/+20/+10 speed points. Wrong answers receive no correctness or speed points. Extra points are reserved for future game features. Initial HP can be 100, 200, 300, 500 or 1,000. The lower-scoring side loses HP equal to the round score difference, with a minimum of zero. Battle ends when HP is depleted or the selected questions are exhausted.

**Local** is a labelled probability simulation. **API** submits a structured choice and concise decision summaries. Reading, comparing options, and choosing/checking appear as replacing activity stages, not a live transcript of internal reasoning. Choices and saved summaries are revealed after both sides finish; no second request invents a retrospective rationale. API failures, invalid decisions and late responses void the round with no points or HP changes and allow retry.

API battles send the question text, options and any attached stem/option images, but not the answer key or explanation. Official DeepSeek image requests use `deepseek-flash`; text requests retain the configured model. Custom endpoints need a compatible vision model. Images must stay within the project and use PNG/JPEG/GIF/WebP, with limits of 8 MiB per image and 16 MiB total. Structured output is capped at 800 tokens. See [battle details](docs/BATTLE.md). Skill-card selection and online multiplayer are not implemented.

### 8. Export reports

All fixed report text, column labels, PDF metadata and footers are **English**, regardless of interface language. Question content and user notes retain their original wording. Unicode font fallback preserves Chinese text and full-width punctuation such as `！` without replacing Latin text with a CJK font.

The journal exports the queried snapshot to PDF, including likes and complete notes. The notebook offers CSV and illustrated PDF exports. CSV uses UTF-8 BOM and protects spreadsheet-formula prefixes. Timestamps are converted to the machine's local timezone and displayed as `yyyy/mm/dd hh:mm:ss`; PDF states the timezone. Reports include generation time and relevant record times. Existing PDF files must be exported again to reflect changes.

### 9. Display and settings

Choose English or Simplified Chinese and a dark/light theme. New settings default to English and dark mode. Stored preferences are preserved. Content, usernames and paths are not automatically translated. Window settings offer automatic sizing and 960x640, 1080x720 and 1280x800 presets, compact spacing and an optional mouse-wheel selector setting. They do not change the operating system's resolution. Long content retains scrolling and navigation uses a consistent back arrow.

### 10. Architecture, storage and maintenance

| Area | Main modules or paths |
| --- | --- |
| Entry and launch | `main.py`, `learning_platform/__main__.py`, `launcher.py`, `start.bat` |
| UI and design | `gui.py`, `modern.py`, `tokens.py`, `ui_tokens.py`, `widgets.py`, `dpi.py` |
| Models and quiz rules | `models.py`, `services.py`, `repositories.py`, `storage.py` |
| Accounts and moderation | `auth.py`, `bank_access.py`, `user_ui.py` |
| Bank editor and import | `editor_ui.py`, `maintenance.py`, `importing.py` |
| Companion and battles | `ai_assistant.py`, `battle.py`, `battle_ui.py` |
| Journal and exports | `history_ui.py`, `history_notes.py`, `date_picker.py`, `exports.py`, `pdf_report.py` |
| Display and images | `display.py`, `image_cache.py`, `assets/` |
| Private account data | `data/users.json`, `data/profiles/<UUID>/` |
| Local preferences | `data/settings.json`, `data/display.json`, `data/login_state.json`, `data/ai_settings.json` |

JSON writes use atomic replacement. Keep one running instance per data directory; no multiprocess transactions are provided. Source/portrait caches are bounded, repeated redraws are avoided and timers are cancelled when the window closes. Keep real accounts, credentials, profiles and backups out of commits. Repair corrupt files or move a backup aside deliberately; do not delete user data as a troubleshooting shortcut.

```powershell
python -m unittest discover -s tests -v
python -m ruff check .
python -m compileall -q learning_platform tests
```

Tests use temporary data. GUI tests need Tk and a display. Ruff is a development tool and is not required to run the app. See the [test report](docs/TEST_REPORT.md), [test cases](docs/TEST_CASES.md), [development guide](docs/DEVELOPMENT.md), [design guide](DESIGN.md), [SRS](specification.md), [requirement mapping](docs/SRS.md), [integration history](docs/V2_INTEGRATION.md) and [changelog](docs/CHANGELOG.md).

### 11. Limits and project history

The application supports local accounts and single-choice questions, with no cloud sync or self-service password recovery. Cancelled image edits may leave unused uploads. API decisions and visual recognition can be wrong; concise summaries are not proof of correctness. One real MAT009 image request returned option 5 with three summaries; that is a connectivity check, not comprehensive model evaluation. Other operating systems and all DPI/layout combinations have not been exhaustively checked.

The original CLI projects contributed atomic JSON storage, direct answer comparison and model/service/repository separation. The desktop project was extracted from `caseStudy/final`, then integrated into the current V2 directory. It ships 60 sample questions across English, Mathematics and Science, with optional pictures; new subjects can be added through data. Historical implementation notes remain in the archive and linked change records.

## 中文

### 1. 安装与启动

使用包含 Tcl/Tk 的 Python 3.10+。Windows 可双击 `start.bat`，或执行：

```powershell
cd D:\develop\workplace\INT6181GroupAssessmentV2
python -m pip install -r requirements.txt
python main.py
```

也可使用 `python -m learning_platform`；`python -m tkinter` 可检查 Tk。启动器检查 Python 版本、Tk 和题库目录，不会自动安装 Python。Linux 需要图形桌面，部分发行版需安装 `python3-tk`。核心练习使用标准库；PDF 导出需要 ReportLab。修改代码后需重启程序。

### 2. 账户与权限

注册使用不重复的用户名（3-32 位文字、数字、下划线或短横线）及两次一致的 6-16 位密码，用户名不区分大小写。公开注册始终创建普通用户。密码使用随机盐 PBKDF2 哈希；旧版长密码可继续登录，直到重置。

| 角色 | 公共练习与对战 | 个人题库 | 错题本与学习记录 | 公共题库维护 | 全部个人题库及用户管理 |
| --- | --- | --- | --- | --- | --- |
| 游客 | 可以 | 不可以 | 不可以 | 不可以 | 不可以 |
| 普通用户 | 可以 | 仅本人 | 仅本人 | 不可以 | 不可以 |
| 管理员 | 可以 | 可以 | 本人；管理入口可查看他人 | 可以 | 可以 |

已迁移的 `wutaicheng` 保留管理员身份、凭据和 UUID；新注册同名账户不会获得特权。管理员可以新增、改名、启停、调整角色、重置密码和查看学习数据。改名不改变 UUID，编辑时密码留空表示保留原密码，系统必须保留至少一个启用的管理员。

受保护操作重新读取账户权限；账号停用后，已打开的个人题目编辑页也不能继续保存或删除。本地账户不能阻止有文件系统访问权限的人直接改文件。

登录页恢复上次成功登录的用户名。记住密码是可选功能，使用 Windows DPAPI 或 macOS 钥匙串保护，不在用户表或受版本控制的配置中保存明文。取消勾选并成功登录会清除已记忆凭据。退出或切换账户保持个人数据隔离。

### 3. 配置与答题

先选题库，再选该题库的科目、主题、难度、题数和整轮限时。游客只使用公共题库。切换题库会刷新关联筛选。题目随机且不重复，超出匹配数量时使用全部可用题；空题库或无匹配时提示调整。

数值控件支持直接输入和 +/-。限时为 0 表示不限时，范围 0-86400 秒。每题只能提交一次，然后继续；普通练习答对得 1 分，不倒扣，结果显示数量、正确率和分数。

进度固定在上方，主要按钮固定在下方；长题目及反馈可滚动。选择或提交答案不应挤动伴学面板。只显示题目明确提供的插图，纯文字题不自动补图。

中途退出保留已提交的错题，不产生完整成绩历史。限时结束会保存成绩，未答题不得分且不自动加入错题本。未完成轮次不能恢复。

### 4. 题库与导入

普通用户通过统一题库中心维护本人题目；公共题目供所有人练习，仅管理员可以增删改和导入。个人题目仅本人及管理员可管理，尚未开放发布为公共题目的功能。

列表支持搜索和科目筛选，表单支持图片和预览。科目、主题和难度可新增；至少两个不同且非空的选项，正确答案必须与某个选项完全一致。已有 ID 不可修改，过期编辑会被拒绝。

管理员可从“所有个人题库”按账户检查、新增、编辑和删除，或从用户管理选中用户后打开个人题库。写入前备份；暂不提供替其他用户批量导入。

公共和个人导入均经过选择 JSON/CSV、校验、预览、明确确认。无效行显示原因，重复 ID/内容跳过；确认时重新检查权限、目标题库及当前重复项。英文界面显示 `Validation passed`。文件限制 5 MB、1000 条。

- [JSON 测试文件](examples/import_test_json.json) 与 [CSV 测试文件](examples/import_test_csv.csv) 各含 3 道不同题目，可连续导入。
- 重复导入安全跳过。
- 错题 CSV 可导入为复习题；兼容旧版包含正确答案及不同最近错误答案的双选项转换。
- 模板、字段和去重规则见[题库导入说明](docs/QUESTION_BANK_IMPORT.md)。

编辑器接受 PNG/GIF/PPM/PGM，校验解码并限制 10 MB、1600 万像素；JPEG/WebP 上传前需转为 PNG。图片复制到 `assets/uploads/` 的独立名称，不移动原图；移除引用不会自动删除其他题目或备份可能使用的文件。

JSON 示例见上方英文部分，同一格式适用于两种语言。公共题库位于 `data/questions/`，个人题库位于 `data/profiles/<UUID>/questions.json`。直接修改 JSON 后需要重新加载或重启；公共新增写入 `custom.json`。维护保留无关记录并备份；个人数据损坏时报告错误，不静默覆盖。

### 5. 每日目标、错题本与学习记录

首页目标卡片显示题库、科目、难度和进度；扳手打开设置，每日题量 1-500。“继续今日练习”直接抽取剩余题量。每次提交立即记录当天活动，未完成轮次也计入每日进度；计划与事件独立保存。

错题本归当前登录账户所有，重复错误累加次数；只有错题复习答对才移除，普通练习答对不会移除。被删除的题目保留可读的不可用提示。

学习记录对每轮练习提供点赞和笔记，可按包含首尾的日期范围、是否点赞、是否有笔记组合查询，统计卡与查询结果一致。日期使用日历或 `yyyy/mm/dd`。已点赞为蓝心，未点赞为白色空心；笔记与点赞独立保存到 `history_notes.json`，不修改旧进度结构。旧记录不包含逐题作答明细。

### 6. 大肥鱼伴学助手

在设置中配置 HTTPS 地址、模型和受保护的 API Key。首页支持单轮学习提问；普通答题页第一次“问问大肥鱼”给引导提示，第二次给答案及解析，失败可重试。头像随思考、答对、答错变化；提交后的鼓励及底部反馈使用本地内容，不调用 API。

普通伴学仅传文字。第一次不含答案键，第二次含参考答案与解析；不发送图片、账户凭据、个人资料或历史记录。输入上限 2500 字符，输出 320 tokens；控制词见[助手说明](docs/AI_ASSISTANT_PROMPT.md)。API 需要联网且可能产生费用，核心练习无需联网。

### 7. 答题对战

所有角色均可进入对战，双方回答公共题库同一道题，每题 30 秒。入门、普通、困难、地狱的模拟时间分别为 12-24、8-18、4-12、2-7 秒。本地正确率分别为 50%、72%、88%、97%；API 难度控制检查要求和时间，不保证这些正确率。

答对基础 100 分，5/10/15/20/30 秒内答对额外获得 50/40/30/20/10 时间分，答错无正确分或时间分；额外分接口预留。初始血量可选 100、200、300、500、1000；低分方扣除本轮分差血量，下限为 0。血量归零或题目完成后结束。

Local 明确是概率模拟；API 返回结构化选项及简短决策摘要。读题、比较选项、选择检查三段提示依次替换，不代表真实内部思维。双方结束后公开选择与已保存摘要，不在结算后另外生成理由。接口失败、无效决策和迟到响应使当轮作废，不计分、不扣血，可重试。

API 对战发送题干、选项及对应图片，不发送答案键或解析。官方 DeepSeek 图片请求使用 `deepseek-flash`，纯文字保留配置模型；自定义接口需要视觉模型。仅接受项目内图片，格式 PNG/JPEG/GIF/WebP，单图 8 MiB、总计 16 MiB；结构化输出 800 tokens。详见[对战说明](docs/BATTLE.md)。技能卡选择和在线多人对战尚未实现。

### 8. 导出报告

所有报告固定文案、字段、PDF 文档属性和页脚统一英文，不随界面语言变化；题目和用户笔记保留原文。Unicode 字体回退保留中文和全角 `！` 等标点，英文保持 Helvetica。

学习记录按查询快照导出 PDF，包含点赞和完整笔记；错题本提供 CSV 和配图 PDF。CSV 使用 UTF-8 BOM 并处理公式前缀。时间统一转换到本机时区并显示为 `yyyy/mm/dd hh:mm:ss`，PDF 标明时区，含生成时间和相关记录时间。旧 PDF 需要重新导出。

### 9. 显示与设置

支持英文/简体中文及深浅主题，新配置默认英文、深色，已有偏好保留。题目、用户名和路径不自动翻译。窗口可自动适配或选择 960x640、1080x720、1280x800，支持紧凑布局及可选滚轮切换开关，不修改系统分辨率。长内容可滚动，主要页面使用统一返回箭头。

### 10. 架构、存储与维护

上方英文模块表同时列出两种语言版本对应的源码路径：入口与启动器、UI 和令牌、模型与仓库、账户与监管、导入与维护、伴学与对战、学习记录与导出、显示与图片缓存。

JSON 原子替换不等于多进程事务，同一数据目录仅运行一个实例。源图和表情缓存有上限，减少重复重绘，窗口关闭时清理定时器。不要提交真实账户、凭据、个人记录和备份；数据损坏时应先备份再修复，不以删除用户数据作为默认处理。

```powershell
python -m unittest discover -s tests -v
python -m ruff check .
python -m compileall -q learning_platform tests
```

测试使用临时数据，GUI 测试需要 Tk 与图形桌面；运行软件无需 Ruff。参考[测试报告](docs/TEST_REPORT.md)、[测试用例](docs/TEST_CASES.md)、[开发规范](docs/DEVELOPMENT.md)、[视觉规范](DESIGN.md)、[主 SRS](specification.md)、[需求对应](docs/SRS.md)、[整合历史](docs/V2_INTEGRATION.md)及[变更记录](docs/CHANGELOG.md)。

### 11. 限制与项目历史

当前支持本地账户和单选题，不提供云同步或自助密码找回；取消图片编辑可能遗留未引用资源。API 决策和识图可能出错，摘要不能证明答案正确。真实 MAT009 图片请求返回 5 与三段摘要，仅说明单题联通，非全面模型评测。其他系统和所有 DPI 组合尚未全面验收。

原 CLI 项目提供了原子 JSON、直接判题以及模型/服务/仓库分离基础。桌面项目从 `caseStudy/final` 独立，再整合到当前 V2 目录。附带英语、数学、科学三科 60 道配图示例，可通过数据增加新学科。旧版文档完整保存在[归档](docs/archive/README_PRE_BILINGUAL_20261113.md)及关联版本记录中，当前行为以上述英中说明为准。
