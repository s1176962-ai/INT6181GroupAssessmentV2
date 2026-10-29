# V2 当前版本说明 · 2026-10-29

正式目录：`D:\develop\workplace\INT6181GroupAssessmentV2`。运行 `python main.py`。当前采用 V2 深色界面和配图题库；保留 V2 测试，恢复窗口尺寸设置并迁入原版账户。完整差异与需求补充见 [V2 整合说明](docs/V2_INTEGRATION.md)。以下保留原版文档历史，其中旧目录、旧布局和测试数量以本说明为准。

# Software Requirements Specification (SRS)

Version 1.3 — updated 2026-10-27: refreshed desktop layout, persistent header account navigation,
and isolated workflow regression tests. Version 1.2 account and language requirements remain applicable.

## Project Title
Configurable Multi-Subject Python Quiz Platform

## 1. Introduction

### 1.1 Purpose
The purpose of this project is to develop a configurable quiz platform using Python. The platform allows students to practise different subjects, answer questions, receive immediate feedback, review incorrect answers, and track their learning progress.

The software should be suitable for beginner-level Python developers, with a clear structure, readable code, and simple data storage.

### 1.2 Scope
The system will provide a unified quiz experience for subjects such as English, Mathematics, and Science. Questions will be stored separately from the program so that new subjects and questions can be added without rewriting the core quiz logic.

Version 1.2 provides local accounts, administrator-controlled question and user management, and a bilingual interface. Advanced AI features remain out of scope.

### 1.3 Target Users
- Students who want to practise different subjects.
- Teachers or administrators who prepare and maintain question banks.
- Project team members who test, maintain, and extend the software.

## 2. Functional Requirements

### FR-01: Home Menu
The system shall provide a main menu with access to:
- Start a quiz.
- Review the wrong-question notebook.
- View learning statistics and history.
- Administrators may manage the shared question bank and local users.
- Log out or switch between local accounts and guest mode.
- Exit the application.

### FR-02: Subject and Quiz Configuration
The system shall allow users to:
- Select an available subject.
- Select a topic or difficulty level when available.
- Choose the number of questions.
- Start a quiz using the selected settings.

The available choices shall be based on the question data. The system shall handle cases where no questions match the selected settings.

### FR-03: Question Bank
The system shall load questions from external JSON files rather than hardcoding all questions into the application.

Each question should support the following fields:
- Unique question ID.
- Subject.
- Topic.
- Difficulty.
- Question type.
- Question text.
- Answer options.
- Correct answer.
- Explanation.
- Optional question image.
- Optional images for answer options.

The system shall validate question data and handle missing files or invalid question formats gracefully.

Administrators shall be able to add, edit, preview, and remove questions through a graphical maintenance page. Direct JSON maintenance remains supported.

### FR-04: Quiz Interface
The system shall:
- Display the current question and its answer options.
- Support single-choice questions in the initial version.
- Allow users to select and submit an answer.
- Immediately display whether the answer is correct or incorrect.
- Show the correct answer and explanation after submission.
- Provide a button to move to the next question.
- Display the current question number and total question count.
- Display the final result when the quiz is completed.

Users shall not accidentally submit multiple answers for the same question.

### FR-05: Image Support
The system shall support optional images in questions and answer options.

Image paths shall be stored in the question data. If an image is missing or cannot be loaded, the application shall display a readable fallback rather than crashing.

Text-only questions shall continue to work normally.

### FR-06: Wrong-Question Notebook
The system shall:
- Record questions answered incorrectly.
- Display saved incorrect questions.
- Show answer options, correct answers, and explanations.
- Allow users to practise saved incorrect questions again.
- Update the wrong-question status when a question is answered correctly during review, according to the project's chosen review rule.
- Persist the notebook between application sessions.

Repeated incorrect answers should not create duplicate entries for the same question ID.

### FR-07: Score and Learning History
After each quiz, the system shall display:
- Total questions.
- Number of correct answers.
- Number of incorrect answers.
- Accuracy percentage.
- Total score.

The system shall save quiz history, including the date and time, subject, number of questions, and result. Users shall be able to view previous quiz results after restarting the application.

### FR-08: Data Persistence
The system shall use simple local files, such as JSON, to store question data, wrong-question records, and learning history.

The application shall create required data files or handle their absence safely. Invalid saved data shall produce a useful error message rather than an unexplained crash whenever practical.

### FR-09: Input Validation and Error Handling
The system shall handle:
- Empty question banks.
- Invalid quiz settings.
- Missing or invalid question fields.
- Invalid user selections.
- Missing image files.
- Missing or malformed saved progress files.

The application should remain usable after recoverable errors.

### FR-10: Local Registration and Login
- Show a login page at startup, with registration and guest entry.
- Require a unique, case-insensitive username (3–32 word characters or hyphens), a password of 6–16 characters, and matching confirmation during registration.
- Store randomly salted PBKDF2-HMAC-SHA256 password hashes, never plaintext passwords.
- Support logout and account switching; do not remember plaintext passwords.
- Store each account's wrong notebook and history in a separate UUID-based profile directory.
- Preserve existing `data/progress.json` as guest progress. Do not silently migrate or overwrite it.
- Malformed account data shall produce a useful error without overwriting the file.
- Accounts are local learning profiles, not a security boundary against someone with filesystem access. No cloud identity or password recovery is required.

### FR-11: Graphical Question-Bank Maintenance
- Only enabled administrators may view or use question maintenance. Ordinary accounts and guests do not see its navigation entry. Re-check persisted authorization before mutation and image upload.
- List questions with ID, subject, topic, difficulty, and text. Provide subject filtering and ID/text/topic search.
- Provide a form for required fields, question and option images, a selectable correct answer, and a preview.
- Allow new subject/topic/difficulty values without code changes. Reserve the UI label `全部` for filters.
- Allow adding/removing options with at least two unique non-empty options; require a valid correct answer.
- Keep an existing question's ID immutable, reject duplicate IDs, and detect stale edits.
- Confirm deletions and discarding unsaved form edits.
- Save new records to `custom.json`; edit/delete records in their source file while preserving unrelated and extension fields.
- Back up an existing source file outside the scanned question directory before replacing it. If backup fails, do not modify the original.
- Apply changes immediately and persist across restarts. Deleted questions' notebook records remain with an unavailable notice.

### FR-12: Local Image Import
- Provide file selection, preview, replace and remove controls for both question images and each answer option.
- Support PNG, GIF, PPM and PGM without third-party runtime dependencies; JPEG/WebP must first be converted to PNG.
- Validate decoding before copying, with a 10 MB file limit and a 16-million-pixel limit.
- Copy images to unique filenames under `assets/uploads/` and store project-relative paths. Never move or overwrite the selected source file.
- Cancelling the file dialog leaves the image unchanged; invalid images show an error and leave the form usable.
- Removing an image detaches its reference. Do not automatically delete files that may be referenced by other questions or backups; unused uploads may remain after cancelled edits.

### FR-13: Expanded Example Content
- Ship 60 single-choice questions: 20 each for English, Mathematics and Science.
- Cover easy, medium and hard levels, multiple topics, explanations and image demonstrations.
- Preserve the IDs and content of the original 15 sample questions.

### FR-14: Administrator Permissions and User Management
- Support `admin` and `student` roles, plus an `enabled` boolean status. Legacy records default to enabled students.
- Upgrade the existing `wutaicheng` account to administrator once, retaining its UUID, password hash and progress. Back up the original account file. Do not hardcode privilege by username or auto-promote future registrations.
- Public registration always creates a student. The interface hides question and user management from students and guests; service-level checks re-read the current account before privileged operations.
- Only administrators may list accounts, inspect another account's history and wrong notebook, add accounts, rename accounts, reset passwords, enable/disable login, or grant/revoke administrator status.
- Show only account identity, role, status and learning data; never show password hashes, salts or plaintext passwords.
- Renaming preserves UUID-based progress. Empty password input during editing retains the old hash; new/reset passwords must be 6–16 characters with matching confirmation.
- For compatibility, previously stored longer passwords continue to authenticate until reset; the application does not know their plaintext length from hashes.
- Disabled accounts cannot log in. Existing sessions are checked on subsequent protected actions and quiz submission; disabled sessions return to login without saving a new answer.
- Reject any update that would leave no enabled administrator. Losing administrator status also prevents previously opened editors from saving.

### FR-15: Lettered Answer Options
- Display options as `A: text`, `B: text`, `C: text`, `D: text` in quizzes, notebooks and previews.
- Use the same letter labels in editor option groups, continuing through Z and AA if needed.
- Change presentation only; stored answer text and correctness checks remain unchanged.

### FR-16: Interface Language Settings
- Provide Settings / Language from both the login page and home screen.
- Offer Simplified Chinese and English. Apply a saved choice immediately to newly rendered screens and remember it in local `data/settings.json` across restarts.
- Translate login, navigation, quiz feedback/results, notebook/history, question and user management, confirmations and ordinary account errors using an explicit catalog.
- Preserve question content, subjects, topics, usernames and paths exactly as data; language switching is not question translation.
- Preserve language-independent role/status values in storage and reserve both `全部` and `All` as filter labels.
- Handle a missing settings file with the Chinese default. Warn about malformed settings and do not silently overwrite them.

## 3. Non-Functional Requirements

### NFR-01: Usability
The interface shall be simple and understandable for students. Navigation, buttons, and feedback messages shall use consistent wording.

### NFR-02: Maintainability
The program shall separate major responsibilities, such as question management, quiz flow, answer checking, progress tracking, and user interface.

The implementation should avoid unnecessary complexity and duplicated logic.

New and modified modules shall use consistent formatting, sorted imports, meaningful names and docstrings. Comments shall explain persistence, identity and data-preservation rules. Maintain a versioned change log and keep the SRS, README and tests consistent with behavior.

### NFR-03: Extensibility
Adding another subject should primarily require adding question data. Adding a new question type should not require rewriting the entire application.

### NFR-04: Reliability
The application shall not crash during normal quiz use or when recoverable data errors occur.

### NFR-05: Testability
Major functions shall be testable independently. Automated tests shall cover answer checking, scoring, question selection, wrong-question handling, and data persistence where practical.

### NFR-06: Compatibility
The application shall run in the team's agreed Python environment and include clear setup and execution instructions.

## 4. Technical Constraints

- Use Python as the main programming language.
- Inspect the existing project and preserve useful code where practical.
- Reuse the existing interface technology if it is suitable and maintainable.
- If the current implementation is unsuitable, use one consistent, beginner-friendly interface technology, preferably Tkinter for a desktop application.
- Use JSON for simple local data storage.
- Avoid unnecessary third-party dependencies.
- Do not require an online service or API for the core quiz functions.
- Include local accounts and the question editor in version 1.2. Do not include AI-generated question services, leaderboards, or cloud synchronisation.

## 5. Project Deliverables

The completed project shall include:

1. A runnable Python quiz application.
2. A configurable question bank with sample questions for at least three subjects.
3. Support for text-based single-choice questions.
4. Optional question and answer-option images.
5. A wrong-question notebook with review functionality.
6. Quiz results and persistent learning history.
7. Automated tests for the main functions.
8. A README containing installation, execution, usage, and data-format instructions.
9. This updated SRS document.
10. A test report summarising test cases, results, and known limitations.
11. A local registration/login interface, account-isolated progress, graphical question editor and image import controls.
12. A change log, coding conventions and automated formatting/static-check configuration.

## 6. Acceptance Criteria

The project will be considered complete when:

1. The application starts successfully using the documented instructions.
2. Users can select a subject and configure a quiz.
3. The application loads questions from external data files.
4. Users can answer questions and receive immediate correctness feedback.
5. The final score and accuracy are calculated correctly.
6. Incorrect answers are recorded in the wrong-question notebook.
7. Users can review and retry incorrect questions.
8. Wrong-question records and quiz history persist after restarting the application.
9. At least one sample question demonstrates image support.
10. Questions from at least three subjects can be loaded without changing the core quiz logic.
11. Automated tests run successfully, with any remaining failures clearly documented.
12. The README explains how to run the application and add questions.
13. Users can register, log out, log in again and see account-isolated progress; guest progress remains available.
14. Administrators can search, add, edit, preview and delete questions in the GUI with validation and backups.
15. Imported images display in saved questions after restarting the application.
16. All 60 sample questions load; tests cover accounts, maintenance, backups, failed writes and image imports.
17. wutaicheng retains its credentials and progress and can open user and question management; ordinary users cannot access either.
18. Administrators can create/edit/disable/re-enable/promote/demote accounts and inspect progress; tests reject unauthorized actions and removal of the last enabled administrator.
19. Quiz, notebook and preview options use letters and separators.
20. Chinese/English switching persists and preserves question data; tests cover both languages and the 6/16-character password boundaries.

## 7. Out of Scope for Version 1.2

The following features are not required for the initial release:
- AI-generated questions or AI tutoring.
- Online multiplayer or classroom competition.
- Cloud storage and online account registration (local registration is included).
- Complex teacher administration dashboards.
- Advanced analytics or adaptive learning algorithms.
- Support for every possible question type.

These features may be considered in future versions after the core application is stable.

## 8. Interface and regression requirements (Version 1.3)

- The top header shall display guest identity with an adjacent login action; authenticated users shall see their name and a logout/switch-account action.
- Login navigation shall open the account form. Logout shall clear the active account and restore the guest progress path.
- Primary actions, keyboard focus, selected answers and feedback shall be visually distinguishable.
- Home shall present progress summaries and responsive feature cards; long pages shall remain scrollable.
- Workflow unittest cases shall use temporary data and verify quiz persistence, account isolation, authorization and question-bank maintenance.

### 8.1 Laptop display preferences

Settings shall offer automatic sizing and 960x640, 1080x720, 1280x800 presets, capped to the current screen with taskbar space reserved. Compact layout shall be enabled by default and configurable without changing system display resolution. Preferences shall persist locally; long content shall retain scrolling.

The four standard home actions shall use a two-by-two grid at normal window widths. Compact administrator views may use three columns for six actions; narrow windows shall fall back to one column.


2026-10-29：新增整轮限时、CSV/PDF 导出、明确的中途退出提示和 Windows 一键启动。使用方式、超时计分规则及修改文件见 [功能说明](docs/FEATURES_3567.md)。PDF 导出新增 reportlab 依赖，核心运行仍使用标准库。


2026-10-29：题数输入改为白底黑字；勾选框使用对勾。PDF 改为蓝白报告样式，包含统计摘要、页脚页码；错题按题分页并加入题干及选项图片、答案与解析，历史使用学科配图。Windows 优先嵌入宋体，保证中文显示。


2026-10-29 练习交互修复：题数变化同步更新开始按钮；配置页压缩为下拉学科与紧凑筛选，开始按钮固定底部；设置增加滚轮修改选项开关（默认关闭，随窗口设置保存）；答题选项只保留一个字母标记，去掉重复前缀及圆点；提交后原位切换可用的继续按钮，底部操作栏保持固定，长题目及反馈在上方内容区滚动。新增题数同步、滚轮持久化和滚动时按钮可见性回归测试。


2026-10-29 练习布局调整：恢复紧凑学科卡片选择，固定操作栏的主要操作在左侧，返回或结束在右侧；答题进度仅保留圆点连线，移除重复矩形进度条。


答题页进度条固定在顶部标题栏下方；题号只在标题栏显示一次。中间仅滚动题目、选项和解析，底部操作栏固定。离开答题页时移除固定进度区域。
