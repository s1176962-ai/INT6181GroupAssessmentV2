# 历史用例说明

本文件保留原版 12 个流程用例设计。V2 按要求保留自己的测试，未包含 test_workflow_*.py；下列分组命令仅适用于原版。V2 请运行 `python -m unittest discover -s tests -v`。参见 [整合说明](V2_INTEGRATION.md)。

# 功能测试用例

所有测试文件和测试方法使用 `test_` 前缀，继承 `unittest.TestCase`。每个用例自行创建临时数据，结束后清理，不读取或修改真实账号、学习记录及题库。用例之间没有执行顺序依赖。

## 用例清单

| 编号 | 文件 | 操作与输入 | 预期结果 |
| --- | --- | --- | --- |
| TC01 | test_workflow_quiz.py | 筛选 Mathematics / Arithmetic / easy，申请 5 题；实际有 2 题，一对一错，然后重新读取进度 | 仅抽取匹配的 2 题；正确 1、错误 1、得分 1、正确率 50%；保存学科和历史 |
| TC02 | test_workflow_quiz.py | 两题均答错，再复习并答对第一题 | 仅移除第一题，第二题保留；两轮历史存在，后一轮标为 review |
| TC03 | test_workflow_quiz.py | 提交空答案；随后提交正确答案，再尝试重复提交错误答案 | 空答案不创建存档；重复提交被拒绝，已有存档不变 |
| TC04 | test_workflow_quiz.py | 开始 3 题练习，仅提交第一题错误答案后结束 | 第一题进入错题本，未完成轮次不产生最终成绩 |
| TC05 | test_workflow_accounts.py | 用普通账户完成练习，分别读取该账户与管理员的进度 | 仅答题账户出现历史，其他账户的记录不受影响 |
| TC06 | test_workflow_accounts.py | 管理员停用普通账户，尝试登录；再启用并登录 | 停用时拒绝登录，恢复后使用原身份成功登录 |
| TC07 | test_workflow_accounts.py | 完成练习后，管理员改名并设置新密码 | 原凭据失效，新凭据可登录，UUID 与原成绩保留 |
| TC08 | test_workflow_accounts.py | 普通用户尝试提升自己的角色、读取管理员的进度 | 两项操作均被拒绝，账户文件内容不变 |
| TC09 | test_workflow_bank.py | 新增属于 New Subject 的题目，按此学科筛选并完成练习 | 新学科无需修改程序即可使用，历史记录该学科 |
| TC10 | test_workflow_bank.py | 将题目从 2+3 改为 2+2，正确答案从 5 改为 4 | 下一轮按新答案判题，备份中保留原题 |
| TC11 | test_workflow_bank.py | 答错一题后从题库中删除它 | 题库中不再出现该题，已有错题和历史记录不丢失 |
| TC12 | test_workflow_bank.py | 尝试新增与已有题目 ID 相同的题目 | 拒绝保存，原文件及题目数量不变 |

## 运行与截图

在 PowerShell 中先进入项目目录：

```powershell
cd D:\develop\workplace\INT6181GroupAssessment
```

分别运行以下命令。每组仅 4 个用例，`-v` 会显示方法名、用例说明和结果，便于在同一屏内查看。

答题流程：

```powershell
python -m unittest discover -s tests -p "test_workflow_quiz.py" -v
```

账号与权限：

```powershell
python -m unittest discover -s tests -p "test_workflow_accounts.py" -v
```

题库维护：

```powershell
python -m unittest discover -s tests -p "test_workflow_bank.py" -v
```

一次运行全部新增用例：

```powershell
python -m unittest discover -s tests -p "test_workflow_*.py" -v
```

全部回归测试：

```powershell
python -m unittest discover -s tests -v
```

截图保留执行命令、用例结果和底部的 `Ran ... tests` 与 `OK`。如果出现 `FAIL` 或 `ERROR`，先保留错误输出，根据断言检查实际结果，再修复和重新执行。运行时间随机器变化，以实际输出为准。

这组用例覆盖服务之间的业务流程，原有 `test_core.py`、`test_extensions.py`、`test_roles_and_language.py` 和 `test_gui.py` 继续覆盖字段验证、文件故障、图片、语言和真实控件交互。界面视觉效果仍需实际打开检查。
