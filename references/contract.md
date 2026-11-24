# 调用契约（v1.2.0）

宿主要能可靠调用一个 Skill，靠的不是 README 写得好看，而是**字段固定、状态可判、失败有语义**。这份文件就是契约本身；`SKILL.md` 只做摘要，细节以本文为准。

## 入口

| 入口 | 用途 | 稳定性 |
| --- | --- | --- |
| `python3 scripts/wanhua.py solve "<句子>"` | 契约输出，宿主首选 | 稳定，字段变更算破坏性变更 |
| `python3 scripts/wanhua.py check "<句子>"` | 生成后的歧义自检 | 稳定 |
| `python3 scripts/wanhua.py compare "<绕句>" "<原句>"` | 折叠验证 | 稳定 |
| `python3 scripts/negation_count.py "<句子>"` | 人读版诊断 | 稳定 |
| `python3 scripts/negation_count.py --json "<句子>"` | 结构化诊断 | 稳定（新增字段兼容） |
| `python3 scripts/wanhua.py templates` | 句式表 | 稳定 |

## 输入

- 一条中文句子，长度 1~200 字（`MAX_INPUT_CHARS = 200`）。
- 允许中英混排、任意标点、Emoji；脚本按字符扫描，不依赖分词。
- 超过 200 字请先按标点切句，逐句调用——工具不做长文分段。

## 输出（`solve`）

```json
{
  "skill": "double-negative-speech",
  "version": "1.2.0",
  "mode": "decode",
  "input_text": "不是不该改",
  "status": "ok",
  "polarity": "肯定",
  "confidence": 0.95,
  "rules": [],
  "scope": [
    {"token": "不是不", "weight": 2, "kind": "construct", "scope": "不是不该改"}
  ],
  "pragmatic_hint": {
    "heuristic": true,
    "coverage": "有限覆盖：委婉软化 / 反讽 / 反问；不覆盖语气强度、礼貌层级、方言差异",
    "items": [],
    "affects_polarity": false
  },
  "explain": "否定权重合计 2，按奇偶折叠为肯定",
  "next_step": "规则层干净，可交付；仍建议核对作用域是否符合原意"
}
```

### 字段

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `skill` / `version` | string | 固定 slug 与版本号；宿主可据此判断契约是否变化 |
| `mode` | `decode` / `manual` | 脚本只输出 `decode`；`manual` 由宿主在没有 Python 环境时自行填写，见下节 |
| `input_text` | string | 原样回显（已 strip），便于日志对齐 |
| `status` | enum | `ok` / `low_confidence` / `ambiguous` / `unknown` / `error`，见下 |
| `polarity` | `"肯定"` / `"否定"` / `null` | 规则层折叠结果；`unknown` 与 `error` 时为 `null` |
| `confidence` | 0~1 / `null` | 规则置信度，不是语言正确率；脚本取值 0.95 / 0.7 / 0.5 / 0.3 / 0.0，`manual` 模式必须是 `null` |
| `rules` | array | 触发的规则，元素 `{id, note}`，`id` 形如 `R-QUANT`，用于可解释展示 |
| `scope` | array | 每个否定词的作用域浅层边界 `{token, weight, kind, scope}` |
| `pragmatic_hint` | object / null | **启发式**语用提示，明确标 `heuristic: true`、`affects_polarity: false` |
| `explain` | string | 一句话说明极性是怎么算出来的，供宿主转述给用户 |
| `next_step` | string | 宿主下一步该做什么（交付、补语境、改写） |

## status 语义

| status | 触发条件 | 宿主应做什么 |
| --- | --- | --- |
| `ok` | 无歧义、无风险 | 可直接交付；仍建议核对作用域 |
| `low_confidence` | 有风险但无歧义（词汇化否定、层级过深） | 可交付，但把 `rules` 一并说明 |
| `ambiguous` | 规则层已标出歧义（量词、特殊形式、作用域、冲突） | **不能当唯一解**：补语境、改写，或并列两种解读 |
| `unknown` | 没有命中否定词 | 不是绕弯句，按普通语义理解；`polarity` 为 `null` |
| `error` | 空输入、超长、读取失败 | 修输入后重试，不要把 `error` 当成"否定" |

## 退出码

| 码 | 含义 |
| --- | --- |
| `0` | `ok` / `low_confidence` |
| `2` | 参数错误（argparse 默认） |
| `3` | `ambiguous` / `unknown`——JSON 仍然有效，只是不能当唯一解 |
| `4` | 输入或运行时错误（空、超长、文件读不了）；错误信息写 `stderr` |

`negation_count.py` 同样遵守 `0 / 4`；它的 `--json` 输出与 `solve` 共享 `status/confidence/rule_ids`。

## 规则编号

| id | 含义 |
| --- | --- |
| `R-SPECIAL` | 特殊形式歧义（差点没 / 好不） |
| `R-LEXICAL` | 词汇化否定（未必 / 难以 / 难免不…） |
| `R-QUANT` | 量词降级（否定 + 全称词） |
| `R-SCOPE` | 作用域分歧（助动词隔开两处否定） |
| `R-DEPTH` | 有效否定层数 ≥4 |
| `R-NONE` | 未发现否定词 |
| `R-CONFLICT` | 同句三条以上规则同时触发，极性可能互相覆盖 |

## 失败与边界行为（明确约定）

- **空输入**：`status=error`、退出码 4、`explain="空输入"`。不猜、不返回"肯定"。
- **超长输入**：`status=error`、退出码 4，提示切句。不静默截断。
- **无否定词**：`status=unknown`、`polarity=null`。不硬给"肯定"。
- **中英混排 / 标点异常 / Emoji**：不报错，非中文字符按普通字符跳过。
- **语用层**：只给提示，永不改 `polarity`，`affects_polarity:false` 是硬约定。
- **脚本崩溃**：退出码非 0 且 `stderr` 有信息；宿主应视为"未得出结论"，而不是"否定"。

## 无 Python 环境：`manual` 降级

脚本不可用时（无 `python3`、沙箱禁执行、用户要求不跑脚本），宿主按 `references/manual-mode.md` 的规则表人工执行，输出同一形状但有三处差异：

- `mode` = `"manual"`；`confidence` = `null`（禁止编造数值）。
- `status` 只用 `ok` / `low_confidence` / `ambiguous` / `unknown`，不产 `error`。
- `explain` 必须带"manual 模式：按规则表人工执行，未跑脚本校验"。

这是**新增取值**的兼容变更：脚本行为不变，契约版本仍为 v1.2.0，宿主按 `mode` 字段决定是否采信。

## 兼容性

- Python ≥ 3.8，仅用标准库（`json`/`re`/`sys`/`argparse`/`pathlib`/`dataclasses`/`unittest`）。
- 新增字段属于兼容变更；删除或改名字段、改 `status` 取值、改退出码语义，属于破坏性变更，必须升 `version` 并写进 `CHANGELOG.md`。
- 契约在 v1.2.0 冻结；此后的规则调整只影响 `confidence` 与具体 `rules`，不改字段形状。
