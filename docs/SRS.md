# SRS 与实现决策

完整、权威的需求规格及本次 1.3 更新位于 [specification.md](../specification.md)。此处引用原文，避免维护两份完整需求造成不一致。

## 本次实现决策

- 使用 Tkinter 桌面界面、Python 标准库及本地 JSON，不引入网络依赖。
- 按本次需求加入本地注册/登录、管理员用户与题库管理、个人进度隔离及中英文设置。旧进度保留为访客记录。
- 每题 1 分；正确率按两位小数显示；空统计为 0%，不允许开启空练习。
- 超出可用题数时抽取全部匹配题，顺序随机且不重复。
- 错题按 ID 去重；普通练习答对不移除，错题复习答对才移除。
- 每次提交保存错题变化，最后一次提交将完整成绩和错题一起原子保存；未完成轮次不入历史。
- 损坏的进度文件显示诊断且不覆盖；修复或备份移走后可继续。
- 题库记录逐条校验，无效记录跳过；删除的错题保留记录并显示状态。
- 图片使用项目内相对路径，缺失或无法解码时显示可读文本。

## 需求对应

| 需求 | 实现 |
| --- | --- |
| FR-01 主菜单 | gui.Application.home |
| FR-02 配置 | gui.Application.configure / services.select_questions |
| FR-03 题库 | models.Question / repositories.QuestionRepository |
| FR-04 答题 | services.QuizEngine / gui.Application.show_question |
| FR-05 图片 | gui.Application.show_image / assets |
| FR-06 错题 | services.QuizEngine.submit / gui.Application.notebook |
| FR-07 成绩历史 | models.score / gui.Application.history |
| FR-08 持久化 | storage.JsonStore / repositories.ProgressRepository |
| FR-09 校验 | models、repositories、services 的校验及 GUI 错误提示 |
| FR-10 本地账户 | auth.AuthService / gui 登录页面 |
| FR-11 题库维护 | maintenance.QuestionEditor / editor_ui.EditorPage |
| FR-12 图片上传 | maintenance.import_image / editor_ui 图片控件 |
| FR-13 扩充题库 | 三科各 20 题，总计 60 题 |
| FR-14 权限与用户管理 | auth 的持久化权限检查 / user_ui.UserPage |
| FR-15 字母选项 | models.option_label / 练习、错题、编辑器、预览 |
| FR-16 界面语言 | i18n.Translator / locales/en.json / 设置页 |
| NFR-01–06 | 单一界面、模块分层、外部题库、异常处理、unittest、README |

运行和数据格式详见 [README](../README.md)，实际验证与限制见 [测试报告](TEST_REPORT.md)。

代码与注释规范见 [DEVELOPMENT](DEVELOPMENT.md)，版本记录见 [CHANGELOG](CHANGELOG.md)。


## 2026-10-29 V2 整合更新

当前正式目录为 `D:\develop\workplace\INT6181GroupAssessmentV2`。完整变更、账户迁移、窗口设置及测试范围见 [V2_INTEGRATION](V2_INTEGRATION.md)。本文件先前版本内容保留为历史；当前界面采用 V2 深色主题，测试保留 V2 原有套件。
