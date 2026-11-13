# WhaleMate - Software Requirements Specification

Version: V2 documentation consolidation, 2026-11-13.

English requirements are presented first, followed by the equivalent Chinese requirements using the same identifiers. Both parts describe the current implementation. Earlier requirements and amendments are preserved in [the specification archive](docs/archive/SPECIFICATION_PRE_BILINGUAL_20261113.md). Historical exclusions of AI features or student bank access no longer describe the current scope.

## English

### 1. Purpose, users and scope

WhaleMate is a configurable desktop learning companion built with Python and Tkinter. Students practise single-choice questions, configure their own question banks, receive guided help from Big Whale, review mistakes and track learning sessions. Administrators maintain public content, moderate personal banks and manage local accounts. Developers maintain a separated, testable codebase.

Core practice works offline. The optional assistant and API battle opponent require a configured external service. Local simulation remains available without an API. This specification covers the existing local desktop application, not cloud identity or online multiplayer.

### 2. Functional requirements

#### FR-01: Navigation and home

The sidebar shall provide Home, Start a quiz, Notebook and review, Quiz battle, Statistics and history, Question management, User management and Settings in that order, subject to role visibility. Guests shall not access personal notebooks, history or management pages. Students shall see their personal-bank centre but not user management. Main pages shall have a consistent back arrow; forms and imports return to their owning list. Home shall combine daily goals, recent learning, activity and a companion card. Guest home shall not reveal another user's records.

#### FR-02: Quiz configuration

Users shall choose a question bank before its available subject, topic and difficulty. Bank changes shall refresh dependent filters. Numeric fields shall accept direct typing as well as increment/decrement controls. Question count shall be positive; selection shall shuffle matching questions without repetition and cap requests at available matches. Empty banks, invalid settings or no matches shall produce useful feedback instead of starting an empty quiz.

#### FR-03: External question data and ownership

Questions shall be loaded from UTF-8 JSON arrays, not hardcoded. Each record includes `id`, `subject`, `topic`, `difficulty`, `type`, `question`, `options`, `answer`, `explanation` and optional `question_image`/`option_images`. Only `single_choice` is currently supported. At least two distinct non-empty options and an exact answer match are required; option-image arrays shall match the option count. IDs shall be unique within a bank, and personal writes shall avoid public IDs.

Public questions shall be readable for practice by every role and writable only by enabled administrators. Personal questions shall be stored by owner UUID and remain inaccessible to other students. Administrators may inspect and maintain any personal bank through a clearly selected owner. Public and personal banks remain separate practice sources; publication and cross-owner batch import are not implemented.

#### FR-03A: Daily learning plan

A single home card shall display progress and the configured bank, subject and difficulty. A compact settings action shall open bank, subject/random subject, difficulty/all difficulty and daily quantity (1-500) controls. Continuing daily practice shall directly select random matching questions for the remaining quantity. Each successful submission immediately records activity, including submissions in unfinished sessions. Legacy plan files shall remain readable without losing events. No-match cases shall offer adjustment guidance.

#### FR-04: Answering and results

The quiz shall show one question, optional pictures, labelled options and progress. Each question may be submitted once. Submission shall show correctness, the correct answer and reference explanation, then enable Continue/View results in a fixed action area. Standard quizzes award one point per correct answer, without negative marks. Results shall show total/correct/incorrect counts, accuracy and score. The final successful submission shall persist the completed session even if the result page has not yet been opened.

#### FR-04A: Big Whale companion

The home page shall offer a single-turn study question. Normal quiz assistance shall provide an answer-free guiding hint first, then a reference-grounded explanation and answer on a second successful request; failures may be retried. Thinking, correct and incorrect expressions shall match the current state. Submission encouragement and bottom feedback shall use local data without additional API requests.

Normal assistance sends text only. The first hint excludes the reference answer/explanation; the second includes them. No profile, credential or learning-history data shall be sent. Endpoint/model/key shall be configurable via HTTPS, with OS-protected credentials excluded from source control. Normal requests shall have 2,500-character input and 320-token output limits and run outside the UI thread. English UI instructions shall request English replies. Source question content remains unchanged.

#### FR-05: Optional images

The UI shall support images for both question stems and options, keep them associated with the correct option, and scale illustrations to the available area. Text-only questions shall not acquire invented illustrations. Missing or invalid images shall produce a readable fallback without crashing. Paths shall resolve within the project. Transparency shall work in dark/light themes.

#### FR-06: Wrong-question notebook

Only signed-in users may access their profile's notebook. Incorrect submissions shall be persisted immediately and deduplicated by question ID, increasing the mistake count on repeated errors. Normal correct answers shall not remove mistakes; correct answers in review shall remove them. Users may review an individual question or all available mistakes. Deleted questions shall retain their record with an unavailable notice. Guests shall not read shared or other users' notebooks.

#### FR-07: Learning history

Completed quiz and review sessions shall persist their identity, local-aware timestamp, subject, question totals, accuracy and score. History shall remain account-isolated across restarts. Manually abandoned incomplete sessions shall not appear as completed history, while already-submitted mistakes remain available. Session timeout shall save partial results and unanswered counts; unanswered questions shall not automatically become mistakes.

#### FR-07A: Likes, notes and queries

Authenticated users shall like and annotate session records. Existing history lacks individual answer details, so annotations apply to sessions rather than invented per-question history. Notes/likes shall be persisted separately from the legacy progress schema. Inclusive local-date ranges, liked status and note presence shall be combinable filters. Calendar pickers and manual `yyyy/mm/dd` entry shall be supported. Summary cards and PDF exports shall reflect the selected query snapshot. Liked hearts shall be blue and unliked hearts white. An unfiltered like toggle shall update locally without rebuilding every record.

#### FR-08: Persistence and recovery

JSON writes shall use atomic replacement. Accounts shall use stable UUID-based directories; renaming shall not detach data. Corrupt account, personal-bank or progress data shall be reported and preserved. Missing files shall receive safe defaults where appropriate. Existing user-table and progress schemas shall not be changed for notes or personal-bank moderation. Backups shall be created before bank mutations. Atomic writes do not provide multi-process transactions.

#### FR-09: Validation and import

Imports shall support JSON and CSV with a 5 MB/1,000-record limit, validation, row-level preview and explicit confirmation. Duplicate IDs and content shall be skipped; malformed headers, column mismatches and invalid fields shall be identified. Confirmation shall recheck current permission, target ownership and duplicates. A preview for one target shall not be applied to another. Public import remains administrator-only. Official templates, separate demonstration files and compatible wrong-question CSV round trips shall be tested. English preview messages shall include `Validation passed`.

#### FR-10: Registration, login and remembered credentials

Registration shall require a unique case-insensitive username (3-32 word characters or hyphens), a 6-16-character password and matching confirmation. Passwords shall use random salts and PBKDF2-HMAC-SHA256 hashes. Public registration shall always create a student, regardless of username. Legacy longer passwords shall continue to authenticate until reset. Startup shall offer login, registration and guest entry; logout/account switching shall preserve isolation.

The form shall restore the last successful username. Remember password shall be opt-in and use OS account protection (Windows DPAPI/macOS Keychain), not plaintext in the user table. Successful login with the option unchecked shall clear the remembered password. Corrupt or undecryptable preferences shall not block ordinary login. Existing guest progress shall be preserved without exposing it through guest notebook/history pages or silently assigning it to a new account.

#### FR-11: Graphical maintenance and moderation

Students and administrators shall share one bank editor with list/search/filter/create/edit/delete/image/preview operations. Students may maintain only their own bank. Administrators may maintain public and all personal banks, with an explicit owner selector and a direct entry from user management. Existing question IDs are immutable; duplicate IDs and stale edits shall be rejected. Unsaved changes and deletions require confirmation. Public edits preserve source-file ownership and extension fields. Failed backups shall not modify the original bank. Every personal save/delete shall revalidate the current session, including an already-open editor after account disablement.

#### FR-12: Local image import

The editor shall accept PNG/GIF/PPM/PGM with a 10 MB and 16-million-pixel limit, validate decoding, and copy files to unique names under `assets/uploads/`. JPEG/WebP need conversion before editor upload. Source files shall not be moved or overwritten. Cancelled dialogs or invalid uploads shall preserve the previous field. Detaching an image shall not automatically delete potentially shared or backed-up files; unused uploads may remain.

#### FR-13: Example content

The application shall retain 60 example single-choice questions: 20 each for English, Mathematics and Science, covering multiple topics, easy/medium/hard difficulties, explanations and optional illustrations. Original sample IDs/content shall be preserved. Adding another subject shall primarily require data, not core-code changes.

#### FR-14: Roles and user administration

Accounts shall have persisted `admin`/`student` roles and an `enabled` status. The previously migrated `wutaicheng` account shall retain its UUID, credential hash and progress; future registration of that name shall never auto-promote. Administrators may list/create/rename/enable/disable/promote/demote accounts, reset passwords and inspect learning data. They shall never see plaintext passwords, hashes or salts in the UI. Password edits left empty retain the existing credential; reset confirmation and length rules still apply.

The application shall keep at least one enabled administrator. Privileged services shall re-read account state rather than trusting a cached role. Disabled accounts shall not log in or write from an existing session. Losing administrator status shall prevent further edits to other users' or public content. Local roles are not a security boundary against direct filesystem access.

#### FR-15: Option labels

Options shall use A/B/C/D and continue through Z/AA where required, with a readable separator or separate letter column. Repeated letter prefixes and native selection markers shall not duplicate the same label. Presentation changes shall not alter stored answer text or correctness comparisons. Reports and editor previews shall retain unambiguous labels.

#### FR-16: Language and theme

English shall be the default interface language for new settings, with Simplified Chinese available. Saved choices shall persist and apply to newly rendered pages. Login, navigation, configuration, feedback, management and import diagnostics shall be translated via the catalog. Stored role/status values are language independent. Question content, usernames and paths shall not be automatically translated. Dark/light themes shall remain supported; existing preferences shall not be discarded because defaults changed.

#### FR-17: Quiz battles and decision records

All roles may battle against a local simulation or an optional API opponent using existing public-bank questions. Both sides receive the same question and a 30-second deadline. Correct answers earn 100 points plus speed bonuses of 50/40/30/20/10 within 5/10/15/20/30 seconds; wrong answers earn no correctness/speed points. Extra points remain an extension field. Initial HP choices are 100/200/300/500/1,000. The lower round score loses HP equal to the difference, bounded at zero. HP depletion or question exhaustion ends the match.

Local levels use probabilities 50%/72%/88%/97% and simulated timing ranges 12-24/8-18/4-12/2-7 seconds. API levels guide checking behaviour and simulated timing without guaranteeing those accuracy rates. API output shall bind question ID, selected option, simulated time and concise decision summaries. Reading, option comparison and choosing/checking are replacing UI activity stages, not a live internal reasoning trace. Answer-related content stays hidden until both sides finish. Results shall show the stored decision and separate reference explanation, not a newly invented retrospective justification.

API battles may send stem/option images together with text, but never the answer key or reference explanation. Images shall be labelled, remain inside the project, use PNG/JPEG/GIF/WebP, and be limited to 8 MiB per image/16 MiB total. Official DeepSeek image requests use `deepseek-flash`; custom endpoints need a compatible model. Structured output is capped at 800 tokens. Invalid or failed responses and responses received at/after the deadline shall void the round with no points or HP change and allow retry. These API decisions remain fallible. Online multiplayer and skill-card selection are future work.

#### FR-18: English exports and timestamps

All report templates, fixed fields, PDF metadata and footers shall be English regardless of UI language; source questions, explanations and notes shall retain their wording. Journal export shall be PDF-only and include the queried snapshot, likes and complete notes. Notebook export shall include importable CSV and illustrated PDF with options, answers, explanation, counts and last-attempt time. Deleted questions shall have readable English fallback text.

CSV shall use UTF-8 BOM and neutralize formula prefixes. Generation and record timestamps shall consistently use the machine's local timezone and `yyyy/mm/dd hh:mm:ss`; PDF shall state the timezone. Raw ISO timestamps shall not appear as record display text. Unicode font fallback shall preserve Chinese and full-width punctuation without black missing-glyph squares for supported characters. Changed report code does not alter PDFs already exported.

#### FR-19: Responsive layout and input

Window settings shall offer automatic sizing and 960x640/1080x720/1280x800 presets bounded to the display, compact spacing and a persistent optional wheel-selector setting. They shall not change OS resolution. Controls in paired rows shall align despite wrapped titles. Primary quiz/battle actions shall remain reachable without scrolling long content; question/feedback regions retain their own scrolling. Results shall not push the next button offscreen. Display preferences shall persist and theme changes shall preserve current answers.

### 3. Non-functional requirements

- **NFR-01 Usability:** consistent navigation, visible primary actions/focus, compact readable layouts, accessible overflow and clearly differentiated feedback.
- **NFR-02 Maintainability:** separate models, persistence, services, UI, imports, moderation and exports; meaningful names, comments for identity/data-preservation decisions, updated README/SRS/changelog/tests, and Ruff checks. Compatibility re-exports and historical backups shall be handled explicitly by tooling.
- **NFR-03 Extensibility:** new subjects use data; new types extend validation, grading and UI without duplicating storage. Extra battle scores and future public publishing shall have clear boundaries.
- **NFR-04 Reliability/performance:** recoverable errors preserve source data; failed/late API requests do not penalize HP. Network work runs outside Tk's UI thread. Caches are bounded, unnecessary repainting is avoided, timers are cleaned up at shutdown, and like toggles avoid whole-page reconstruction when filters permit.
- **NFR-05 Testability:** temporary-data unit/integration tests cover grading, selection, persistence, imports, backup failure, role revocation, disabled sessions, UI language, exports, timestamps, caches and battle error handling. Automated network tests use mocks; real API checks are documented separately.
- **NFR-06 Compatibility:** Python 3.10+, Tk and a graphical desktop; core operation uses the standard library, with ReportLab for PDFs. Windows is the primary tested environment. No hidden cloud dependency for practice.

### 4. Deliverables and acceptance

Deliverables are the runnable application, sample banks/images, import templates, local-account administration, personal-bank moderation, daily plans, notebook/journal, optional companion and battle modules, English reports, automated tests, bilingual README/SRS, coding guidance and test/change records.

Acceptance requires documented startup; data-driven public/personal selection; correct single-submit grading and persistence; notebook removal only during correct review; guest/account isolation; permissions rechecked after disablement/demotion; backup/stale-edit protection; import validation and round trips; fixed primary actions; bilingual UI with original question content preserved; guided two-request assistance; API choices and images correctly bound to the current question; void late/failed battle rounds; English exports with readable local timestamps, pictures and notes; and successful checks with limitations recorded in the test report.

### 5. Boundaries and history

No cloud sync, self-service password recovery, online multiplayer, resumable incomplete session, adaptive learning engine, generated-question service, skill-card selection or general public-publishing workflow is claimed. JSON atomic replacement is not multi-process locking. Unused image files may remain. API latency, accuracy and visual understanding are not guaranteed. One real MAT009 visual decision returning 5 with three summaries is a limited integration check, not a general accuracy claim.

The project retains its earlier CLI/desktop history, migrated accounts, source banks and documented changes. Read [implementation mapping](docs/SRS.md), [README](README.md), [changelog](docs/CHANGELOG.md) and [test report](docs/TEST_REPORT.md) alongside this SRS. Older documents are historical evidence, not current permission or feature rules.

## 中文

### 1. 目的、用户与范围

WhaleMate 是使用 Python/Tkinter 的可配置桌面伴学软件，支持单选练习、自由题库配置、大肥鱼引导式帮助、错题复习和学习记录。管理员维护公共内容、监管个人题库和管理本地账户，开发者维护分层且可测试的代码。

核心练习离线运行；可选伴学和 API 对战需要外部服务，本地模拟无需 API。本规格描述本地桌面应用，不包含云身份或在线多人系统。

### 2. 功能需求

#### FR-01：导航与首页

侧栏顺序为首页、开始练习、错题本、答题对战、学习记录、题库管理、用户管理、设置，并按角色隐藏无权入口。游客不可查看个人错题、历史或管理页；普通用户可维护本人题库但无用户管理。主要页提供统一返回箭头，表单/导入返回所属列表。首页整合每日目标、最近学习、活动及伴学卡片，不向游客显示他人记录。

#### FR-02：练习配置

先选择题库，再加载对应科目、主题和难度；切换题库刷新关联筛选。数字可直接输入或使用加减按钮。题量为正整数，匹配题随机且不重复，超出时使用可用数量。空题库、非法配置或无匹配时给出可恢复提示，不启动空练习。

#### FR-03：外部题目与归属

从 UTF-8 JSON 数组读取题目，包含 `id`、`subject`、`topic`、`difficulty`、`type`、`question`、`options`、`answer`、`explanation` 和可选图片字段。目前仅支持 `single_choice`；至少两个不同非空选项，答案完全匹配选项，选项图数组与选项数一致。库内 ID 唯一，个人写入避免公共 ID。

公共题目供所有角色练习，仅启用管理员可写；个人题库按 UUID 保存，不向其他普通用户开放。管理员明确选择所属账户后可以监管。两种题库保持独立来源，尚未实现公开发布和跨所属账户批量导入。

#### FR-03A：每日计划

首页单卡显示进度、题库、科目和难度，紧凑设置入口配置公共/个人题库、科目或随机、难度或全部及 1-500 题每日量。继续练习直接抽取剩余匹配题，每次成功提交立即保存活动，未完成轮次也计入每日进度。旧计划兼容且不丢事件，无匹配时提示调整。

#### FR-04：答题与结果

显示单题、可选图片、字母选项和进度，每题仅提交一次。提交后显示正误、正确答案及题库解析，并在固定操作区启用继续/结果。普通练习答对 1 分，不倒扣，结果显示总数、正确、错误、正确率和分数。最后成功提交立即保存完整轮次，不依赖打开结果页。

#### FR-04A：大肥鱼伴学

首页支持单轮问答；普通练习第一次给不揭晓答案的引导提示，第二次给依据参考答案的讲解，失败可重试。头像对应思考、答对、答错。提交鼓励及底部反馈使用本地内容，不额外调用 API。

普通伴学仅传文字，首问不含参考答案/解析，第二次包含；不发送个人资料、凭据或历史。HTTPS 地址、模型及受系统保护的 Key 可配置并排除版本控制。普通输入 2500 字符、输出 320 tokens，网络请求在 UI 线程外运行。英文界面使用英文控制词要求英文回复，题目原文不改。

#### FR-05：可选图片

题干和选项图须关联正确选项并按可用区域缩放。文字题不补造插图；缺失或损坏图片给可读回退，不崩溃。路径限制在项目内，透明图支持深浅主题。

#### FR-06：错题本

仅登录用户可访问本人错题本。错误提交立即持久化，按题目 ID 去重并累加次数；普通练习答对不移除，错题复习答对才移除。支持单题或全部复习；删除题目保留不可用记录，游客不得读取共享或他人错题。

#### FR-07：学习历史

完成练习/复习保存身份、带时区时间、科目、数量、正确率和分数，重启后按账户隔离。手动退出未完成轮次不入完整历史，但保留已提交错题。限时结束保存部分结果与未答数量，未答不自动记错。

#### FR-07A：点赞、笔记与查询

登录用户可点赞和记录每轮笔记；旧历史没有逐题明细，不得虚构逐题历史。元数据独立保存，支持包含首尾的本机日期范围、点赞和笔记状态组合查询、日历与手工日期输入。统计及 PDF 与查询快照一致。点赞蓝心、未点赞白心；无点赞筛选时局部更新，避免重建列表。

#### FR-08：持久化与恢复

JSON 使用原子替换，UUID 目录在改名后保持不变。损坏账户、个人题库和进度应报告且保留，适当处理缺失文件。笔记和个人监管不改变旧用户表/进度结构，题库修改前备份。原子写入不等于多进程事务。

#### FR-09：校验与导入

JSON/CSV 限制 5 MB、1000 条，经过校验、逐行预览和明确确认。重复 ID/内容跳过，错误表头、列数和字段显示诊断。确认时复查权限、归属和重复项，禁止跨目标题库套用预览。公共导入仅管理员。官方模板、演示文件和错题 CSV 回导纳入测试，英文校验结果显示 `Validation passed`。

#### FR-10：注册、登录与记忆凭据

唯一用户名不区分大小写，3-32 位文字/数字/下划线或短横线，密码 6-16 位并确认一致；使用随机盐及 PBKDF2-HMAC-SHA256。公开注册始终普通用户，旧长密码保留至重置。提供登录、注册、游客和退出切换。

恢复上次成功用户名；记住密码必须主动勾选并使用 Windows DPAPI/macOS 钥匙串，不在用户表存明文。取消勾选并成功登录清除记忆；损坏或无法解密的偏好不能阻止登录。旧访客进度保留，不通过游客错题/历史暴露，也不自动归属新账户。

#### FR-11：图形维护与监管

普通用户与管理员共用题库中心，支持列表、搜索、筛选、增删改、图片和预览。普通用户仅本人，管理员维护公共及全部个人题库，提供所属账户选择和用户管理直达入口。已有 ID 不变，拒绝重复及过期编辑；丢弃未保存内容及删除需确认。公共维护保留源文件和扩展字段，备份失败不得写入。个人保存/删除必须重新校验会话，账号停用后旧表单也不能继续写。

#### FR-12：本地图片上传

编辑器接受 PNG/GIF/PPM/PGM，限制 10 MB、1600 万像素并校验解码，复制为 `assets/uploads/` 唯一文件名；JPEG/WebP 需先转换。不移动或覆盖源图；取消或非法上传保留原字段。解除引用不自动删除可能共享的图片，可保留未引用上传。

#### FR-13：示例内容

保留三科 60 道单选题，各科 20 道，涵盖主题、三级难度、解析与图片示例。原始样例 ID/内容保持，扩展科目主要修改数据。

#### FR-14：角色与用户管理

持久化 admin/student 和 enabled 状态。已迁移 wutaicheng 保留 UUID、凭据哈希及进度，新注册同名不提权。管理员可列出、新增、改名、启停、升降级、重置密码并查看学习数据，界面不显示密码、哈希或盐。密码编辑留空保留，重置仍需长度及确认校验。

保留至少一名启用管理员；服务读取当前状态，不信任缓存角色。停用用户不能登录或从旧会话写入，撤销管理员后不能继续维护公共或他人内容。本地权限不能防止直接修改文件。

#### FR-15：字母选项

选项使用 A/B/C/D 并可延伸 Z/AA，配分隔符或独立字母列。移除重复前缀及重复原生选择标记；不改变存储答案或判题。报告和预览保持明确标签。

#### FR-16：语言与主题

新配置默认英文，可切换简体中文，偏好持久化。登录、导航、配置、反馈、管理和导入诊断经词典翻译，存储角色/状态不依赖语言。题目、用户名、路径不自动翻译；深浅主题及已有偏好保留。

#### FR-17：答题对战与决策记录

所有角色使用已有公共题库对战，本地模拟或 API 可选，双方同题 30 秒。答对 100 分，5/10/15/20/30 秒内额外 50/40/30/20/10，答错无正确/时间分，额外分字段预留。初始血量 100/200/300/500/1000，低分方扣除分差且不低于 0；归零或题目完成结束。

本地正确率 50%/72%/88%/97%，模拟时间 12-24/8-18/4-12/2-7 秒；API 等级控制检查要求和时间，不保证正确率。输出绑定题目、选项、模拟时间与简短摘要。读题、比较、选择检查是替换式活动展示，不是内部思维直播。双方结束前隐藏答案相关内容，之后显示已保存决策及独立题库解析，不事后另编理由。

API 可传标记过的题干/选项图，不传答案键/解析；图必须在项目内，格式 PNG/JPEG/GIF/WebP，单图 8 MiB、总 16 MiB。官方图片请求使用 deepseek-flash，自定义服务需视觉模型；结构化输出 800 tokens。失败、非法及截止时间到达后返回的决策使该轮作废，不计分不扣血并可重试。模型可能出错；在线多人和技能卡为后续功能。

#### FR-18：英文导出与时间

固定报告文案、字段、PDF 属性及页脚始终英文；题目、解析、笔记保留原文。学习记录只按查询快照导出 PDF，包含点赞和完整笔记；错题支持可回导 CSV 与含图片、选项、答案、解析、次数和最近时间的 PDF，删除题目使用英文回退。

CSV 使用 UTF-8 BOM 并防公式前缀；生成及记录时间统一本机时区，显示 yyyy/mm/dd hh:mm:ss，PDF 标明时区，不直出原始 ISO 串。字体回退保留中文和全角标点，支持字符不得显示黑方块。已导出的 PDF 不自动更新。

#### FR-19：响应布局与输入

自动适屏及 960x640/1080x720/1280x800 预设受屏幕边界限制，提供紧凑布局和持久化滚轮选项，不改变系统分辨率。成对控件标题换行仍应对齐。练习/对战主要操作固定可见，题目与反馈独立滚动，结果不挤掉下一题。切换主题保留当前答案。

### 3. 非功能需求

- **NFR-01 易用性：**统一导航、明确主操作/焦点、紧凑可读布局、可用滚动和清晰反馈。
- **NFR-02 可维护性：**分离模型、持久化、服务、界面、导入、监管和导出；命名清晰，注释解释身份和数据保留规则，维护双语 README/SRS、变更及测试，使用 Ruff。兼容导出与历史备份明确配置。
- **NFR-03 扩展性：**学科由数据扩展，题型扩展校验、判题和 UI 而非复制存储；额外对战分及将来公开发布边界明确。
- **NFR-04 可靠性/性能：**可恢复错误保留原数据，失败/迟到请求不扣血，网络在 UI 线程外执行；缓存有上限，减少重复重绘，关闭时取消定时器，允许时局部点赞更新。
- **NFR-05 可测试性：**临时数据测试覆盖判题、筛选、持久化、导入、备份失败、撤权、停用会话、语言、导出、时间、缓存和对战异常；自动网络测试使用模拟，真实联调单独记录。
- **NFR-06 兼容性：**Python 3.10+、Tk、图形桌面；核心标准库，PDF 使用 ReportLab；主要测试平台 Windows，核心练习无隐藏云依赖。

### 4. 交付与验收

交付包括可运行程序、示例题库/图片、导入模板、账户管理、个人监管、每日计划、错题/历史、可选伴学/对战、英文报告、自动测试、双语 README/SRS、开发规范和测试/变更记录。

验收应覆盖启动、公共/个人筛选、单次提交及持久化、复习正确才消错、游客/账户隔离、停用/降级后重新校验、备份及编辑冲突、导入与回导、固定按钮、双语界面保留题目原文、两阶段伴学、图片和决策绑定本题、异常及迟到轮次作废、英文报告时间/图片/笔记，以及记录限制的检查结果。

### 5. 边界与历史

不宣称已实现云同步、自助找回、在线多人、未完成会话恢复、自适应引擎、自动生成题库、技能卡或通用公开发布流程。原子 JSON 不是多进程锁；可有未引用图片。API 延迟、正确率及识图质量不保证；MAT009 返回 5 与三段摘要只是单题联通验证。

保留原 CLI/桌面历史、迁移账户、原题库和变更记录。结合[实现对应](docs/SRS.md)、[README](README.md)、[变更](docs/CHANGELOG.md)和[测试报告](docs/TEST_REPORT.md)阅读；旧文档作为历史证据，不作为当前权限或功能规则。
