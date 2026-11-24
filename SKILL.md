---
name: double-negative-speech
display_name: "绕弯说话术"
description: 生成或解码“绕弯子”的中文句子：用双重否定、多重否定、反向修饰、条件套嵌、范围挪移把真实意思埋在句子里，或把这类绕晕人的句子翻成一句直白人话。当用户要（1）把直白的话说得绕、留有余地、不像在表态，（2）出带陷阱的选择题/勾选项/阅读理解题、做话术测试，（3）判断“勾选/不勾选”“能不能/是不是”这类句子到底什么意思，（4）把绕口句子翻译成人话、拆解语义时使用。也可用于审校此类表述是否会产生歧义。 English: generate or decode Chinese double-negation / hedging constructions with an explainable, rule-based contract; returns fixed JSON fields with a certainty tier instead of guessing.
---

# 绕弯说话术

> 契约版本 v1.3.0，字段与语义见 `references/contract.md`；变更记录见 `CHANGELOG.md`。

## 什么时候用

- 用户给了一句绕口的中文，想知道到底肯定还是否定、在说什么。
- 用户要把一句直白话"说绕一点""留点余地""别那么像表态"。
- 用户要出带陷阱的选择题 / 勾选项 / 阅读理解题，或要检查自己的表述会不会被读反。
- 用户要审校文案里"不是不能""未必不"这类双重否定是否产生歧义。

## 什么时候不用

- **词义绕**：生造词、别扭搭配、同音错字造成的读不懂——这是写坏了，不是逻辑绕，工具帮不上。
- **语音识别 / 转写错误**：同音误听不是否定算子问题。
- **需要明确立场的场合**：合同、合规声明、承诺、法律表述、对外公告。这类文本不要绕，直接建议用户直说。
- **纯修辞润色**：只要求"文采好一点""更委婉"，不涉及否定/量词/条件逻辑时，不必套这个 Skill。
- **超长文本**（>200 字一句）：先按标点切句，逐句调用。

## 一句话原理

绕弯 = **否定词数量 + 否定作用范围 + 语序** 三者一起做手脚。漏数一个否定词，或认错它修饰谁，意思就整个翻面。

## 输出契约（摘要）

宿主调用 `python3 scripts/wanhua.py solve "<句子>"`，得到固定字段的 JSON。完整定义见 `references/contract.md`，这里只列宿主必须理解的部分：

| 字段 | 取值 | 宿主怎么用 |
| --- | --- | --- |
| `status` | `ok` / `low_confidence` / `ambiguous` / `unknown` / `out_of_scope` / `error` | 决定能不能直接交付 |
| `certainty` | `certain` / `uncertain` / `out_of_scope` | 三档兜底：uncertain 的极性仅供参考，out_of_scope 不给极性 |
| `rules_version` | string | 规则库语义化版本，规则漂移可追溯 |
| `polarity` | `肯定` / `否定` / `null` | 结论；`unknown`、`error` 时为 `null` |
| `confidence` | 0~1 / `null` | 只是规则置信度，不是语言正确率；`manual` 模式必须为 `null` |
| `rules` | `[{id, note}]` | 歧义来自哪条规则，可原样转述给用户 |
| `scope` | `[{token, weight, kind, scope}]` | 每个否定词管到哪一小句 |
| `pragmatic_hint` | `{heuristic:true, coverage, items, affects_polarity:false}` | **只是提示**，永不改 `polarity` |
| `explain` / `next_step` | string | 可直接转述的一句话说明与下一步 |

示例（真实输出，节选）：

```json
{
  "status": "ok",
  "polarity": "肯定",
  "confidence": 0.95,
  "rules": [],
  "scope": [{"token": "不是不", "weight": 2, "kind": "construct", "scope": "不是不该改"}],
  "explain": "否定权重合计 2，按奇偶折叠为肯定"
}
```

## 状态与退出码

| status | 含义 | 宿主动作 |
| --- | --- | --- |
| `ok` | 规则层干净 | 可交付 |
| `low_confidence` | 有风险（词汇化否定、层级过深）但无歧义 | 交付时把 `rules` 一并说明 |
| `ambiguous` | 规则层已标歧义 | **不能当唯一解**：补语境、改写，或两种解读并列 |
| `unknown` | 没有否定词 | 不是绕弯句，按普通语义理解 |
| `out_of_scope` | 反问/反讽已翻转字面极性，规则层给不出可信结论 | **不要给极性**，交人工复核 |
| `error` | 空输入 / 超长 / 读文件失败 | 修输入，**不要把 error 当成否定** |

退出码：`0` 可交付、`3` 需补语境或交人工（`ambiguous` / `unknown` / `out_of_scope`）、`4` 输入或运行时错误（错误写 `stderr`）、`2` 参数错误。

## 确定性三档（分层兜底）

否定和双重否定是统计模型最容易翻车的地方，纯规则也有明确的失效区。所以结论分三档，不硬判：

| `certainty` | 什么时候 | 宿主怎么用 |
| --- | --- | --- |
| `certain` | 规则覆盖、无歧义、无已知风险 | 极性可直接采信 |
| `uncertain` | 命中 `R-SPECIAL` / `R-LEXICAL` / `R-SCOPE` / `R-DEPTH` / `R-CONFLICT` | 极性仅供参考，**要复核** |
| `out_of_scope` | 反问/反讽已翻转字面极性，或压根没有否定词 | `polarity` 为 `null`，明确报"超出规则覆盖范围，建议人工复核" |

规则库另有语义化版本 `rules_version`：`matched_rules`（命中的规则 ID）与 `conflicts`（互斥规则组合）都随 `check` 输出，规则漂移时宿主能立刻看出来。

## 失败与边界行为

- 空输入不猜、不返回"肯定"；超长不静默截断——两者都是 `error`。
- 规则判不了就报 `ambiguous`，并列两种读法，不硬选一个当答案。
- 语用层只覆盖 **委婉软化 / 反讽 / 反问** 三类，不覆盖语气强度、礼貌层级、方言差异；它只出提示，不参与极性计算。
- 脚本只用标准库，Python ≥ 3.8；崩溃或依赖缺失时退出码非 0，宿主应视为"没得出结论"。

## 没有 Python 环境怎么办

脚本是加速器，不是前提。先试一次 `python3 scripts/wanhua.py solve`，失败再降级，别跳过机器校验。

降级时按 `references/manual-mode.md` 的规则表人工执行，输出同一形状，但三处必须改：

- `mode` = `"manual"`（不是 `decode`）；
- `confidence` = `null`，**禁止编一个 0.95 出来**；
- `explain` 里写明"manual 模式：按规则表人工执行，未跑脚本校验"。

`status` 只用 `ok / low_confidence / ambiguous / unknown`（人工不会"崩溃"，不产 `error`）；`rules` 仍用同一套 `R-*` 编号；判不准一律 `ambiguous`，不赌。

manual 结果不算"已验证"：对外文本要复核，日志里保留 `mode: manual`，别抹成 `decode`。

## A. 生成路径

1. **锁定真实意思**，写成一句最直白的话（地基，中途不改）。
2. **选绕度**：轻（一处双重否定）/ 中（双重否定 + 反向修饰，默认）/ 重（三重否定、条件套嵌、语序前置，出题用）。
3. **套句式**，取自 `references/patterns.md`，嵌套不超过三层。
4. **折叠验证**：`python3 scripts/wanhua.py compare "<绕句>" "<原句>"`，`same_polarity` 必须为 `true`。
5. **歧义自检**：`python3 scripts/wanhua.py check "<句子>"`；`risks` 非空必须改写，`pragmatic` 非空按 `fix` 补语境。
6. **交付**：只给句子；出题时必须同时给正确答案与每个错误选项对应的具体错法。

## B. 解码路径

1. **跑脚本**：`python3 scripts/wanhua.py solve "<句子>"`，看 `status / polarity / rules / scope`。
2. **看奇偶**：`scope` 的 `weight` 合计，偶数→肯定、奇数→否定；多字构式（`没有理由不`、`不得不`）已计两票。
3. **核作用域**：`scope` 是浅层边界（按标点与连词切小句），跨小句的深层修饰要人工确认。
4. **查量词**：`R-QUANT` 出现时，问清是全否还是部分否（`不是所有人都不` ≠ `所有人都不`）。
5. **拆条件让步**：`除非…否则…`、`即使…也…` 先抽骨架再填否定。
6. **落成人话**：一句结论，动词用肯定式。
7. **不确定就并列**：`ambiguous` 或 `unknown` 时，把可能读法都写出来，不硬猜。

## 硬规则

- 生成的句子**必须有唯一解**；歧义到读者无法判定，是失败不是高级。
- 否定最多三层；第四层起只标风险，不承诺可解。
- 不用同音、错字、生造词制造绕——那是错字，不是绕弯。
- 「差点没」「好不」「难免不」一律标 `ambiguous`，不硬判正负。
- 用户要"人话"时只给结果，不顺带讲语法。

## 安全与误用边界

- **不用于欺骗**：不用它伪造承诺、隐瞒条件、把拒绝包装成同意，或让对方无法复述自己的义务。
- **不用于规避明确表态**：合同条款、合规声明、法律文书、对外公告、安全提示，遇到这类需求先提示"建议直说"，再按用户要求处理。
- **不用于操纵**：不教人用歧义套取利益、拖住对方、规避责任。
- **输出可解释**：任何歧义判定都要能说出是哪条规则（`R-QUANT` / `R-SPECIAL` / `R-SCOPE`…）导致的，不能只给结论。
- 用户明确要求"必须给准话"时，生成侧一律给直白版，不加绕度。

## 版本与兼容

- 当前 **v1.2.0**，契约在 `references/contract.md` 冻结；变更记录见 `CHANGELOG.md`。
- 新增字段兼容；删字段、改 `status` 取值、改退出码语义算破坏性变更，必须升版本。
- 宿主只依赖三件事：SKILL.md 的 `name`（slug）、`scripts/` 的 CLI 契约、纯标准库的 Python 3.8+ 环境；没有 Python 时走 `manual` 降级（见上节），不假装跑过脚本。

## 资源（按需加载）

- 调用契约、状态与退出码、规则编号：`references/contract.md`
- 句式模板、适用条件与扩展方式：`references/patterns.md`
- 成对例句、正例反例与边界：`references/examples.md`
- 真实翻车案例（带 `FC-xx` 与回归用例）：`references/failure_cases.md`
- 盲测集（独立编写、未参照规则表）：`tests/holdout_cases.json`
- 没有 Python 时的降级执行卡：`references/manual-mode.md`
- 分析器（极性/作用域/歧义/置信度）：`scripts/negation_count.py`
- 契约层 CLI（`solve` / `check` / `compare` / `templates`）：`scripts/wanhua.py`
- 标注集评估：`scripts/evaluate.py` + `tests/labeled_cases.json`
- 回归用例：`tests/`（规则层 / 契约 / 准确率），改规则前后各跑一次
- 安装到各平台：`install.sh`
