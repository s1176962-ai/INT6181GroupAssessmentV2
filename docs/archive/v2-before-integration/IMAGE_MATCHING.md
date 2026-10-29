# 题目插图匹配清单

题库字段：`question_image`、`option_images`（均可为 `null`）。  
路径相对于项目根目录。旧题目无图片字段或为 `null` 时，答题页会显示学科色块占位，不会崩溃。

## 资源目录

| 路径 | 用途 |
|------|------|
| `assets/images/placeholder.png` | 通用缺图占位 |
| `assets/images/subjects/english.png` | 英语学科色块 |
| `assets/images/subjects/mathematics.png` | 数学学科色块 |
| `assets/images/subjects/science.png` | 科学学科色块 |
| `assets/images/questions/` | 建议按 `{id}.png` 存放题目插图 |
| `assets/circle.png` / `assets/square.png` | 题库中已有几何题插图 |

命名建议：`assets/images/questions/ENG001.png`

## 当前题库状态

已用 `scripts/generate_question_art.py` 为全部 60 道题生成扁平教育插画，路径为 `assets/images/questions/{id}.png`。  
`MAT003` 仍使用原有 `assets/circle.png`（与选项图一致）；其余题目已写入对应 `question_image`。  
如需更精细的写实插画，可替换同名 PNG，无需改代码。

### 历史建议主题（可继续精细化替换）

### English

| ID | 建议插图主题 | 建议路径 |
|----|--------------|----------|
| ENG001 | 苹果 | `assets/images/questions/ENG001.png` |
| ENG002 | 冷热对比 | `assets/images/questions/ENG002.png` |
| ENG003–ENG020 | 按题干主题（词汇/语法） | `assets/images/questions/{id}.png` |

学科回退：`assets/images/subjects/english.png`

### Mathematics

| ID | 建议插图主题 | 建议路径 |
|----|--------------|----------|
| 已有几何图的题目 | 继续使用 `assets/circle.png` / `assets/square.png` | 保持题库内路径 |
| 其余 MAT* | 数字、图形、公式示意 | `assets/images/questions/{id}.png` |

学科回退：`assets/images/subjects/mathematics.png`

### Science

| ID | 建议插图主题 | 建议路径 |
|----|--------------|----------|
| SCI* | 实验器材、自然现象、人体示意 | `assets/images/questions/{id}.png` |

学科回退：`assets/images/subjects/science.png`

## 说明

- 不要调用在线图像生成 API。
- 补图后只需在 JSON 中写入相对路径即可；加载失败会显示占位提示。
- 本清单不是已完成配图声明。
