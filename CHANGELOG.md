# 变更记录

规则表一改，Agent 的行为就会漂。所以每次改词表、改阈值、改契约，都在这里留一行：改了什么、影响哪类句子、测试怎么变。

## v1.3.0 — 2026-11-25

**分层兜底 + 规则溯源 + 盲测（契约扩展，宿主需新增分支）**

- 新增 `certainty` 三档：`certain` / `uncertain` / `out_of_scope`。`uncertain` 的极性仅供参考；`out_of_scope` 时 `polarity` 与 `confidence` 一律为 `null`，不再"硬判一个低置信度极性"。
- 新增 `status` 取值 `out_of_scope`：反问/反讽迹象已翻转字面极性，或规则层完全给不出证据时使用；退出码 `3`。
- 新增 `rules_version`（规则库语义化版本，当前 1.3.0），与 `skill.version` 解耦。
- `check` 新增 `matched_rules`（命中规则 ID）与 `conflicts`（互斥组合 + 原因）；目前冲突清单为精选三条（`R-SPECIAL`+`R-LEXICAL`、`R-QUANT`+`R-SPECIAL`、`R-SCOPE`+`R-DEPTH`），未列入表示未检查，不是"不冲突"。
- 新增 `tests/holdout_cases.json`（60 条独立编写的盲测句）与 `tests/test_holdout.py`：极性 88.33%、否定类召回 92.31%、精确 85.71%；错例 7 条全在已声明盲区（`难免`/`不免`/`难免不`、`差点没`、无否定词）。
- `scripts/evaluate.py` 新增 `--holdout` 与否定类精确/召回指标。
- 新增 `pyproject.toml`：`pip install -e .` / `uv tool install .` 可直接得到 `wanhua`、`negation-count` 命令；`SKILL.md` description 补英文一句，新增 `README.en.md`。
- 测试 61 → 73 条，全绿。

## 文档补充 — 2026-11-25

**「宿主没有 Python 怎么办」**（兼容变更，脚本行为与契约版本不变）

- 新增 `references/manual-mode.md`：无 `python3` / 沙箱禁执行时的降级执行卡（切句、否定词表与权重、作用域线索、量词、层数与冲突、输出模板）。
- 契约新增 `mode` 取值 `manual`；该模式下 `confidence` 必须为 `null`，`status` 不产 `error`，`explain` 必须声明"未跑脚本校验"。
- `SKILL.md` 新增"没有 Python 环境怎么办"一节；`README.md` 补同一问题；`contract.md` 补降级段。
- 影响：宿主可据 `mode` 判断结论是否经过机器校验；规则表未改，测试基线不变（61 条全绿）。

## v1.2.0 — 2026-11-24

**契约化（破坏性变更前的最后一次形状调整）**

- 新增 `scripts/wanhua.py solve`：固定 12 个字段的契约输出（`status / polarity / confidence / rules / scope / pragmatic_hint / explain / next_step`），定义见 `references/contract.md`。
- 新增 `status` 五态：`ok / low_confidence / ambiguous / unknown / error`；无否定词一律 `unknown` + `polarity:null`，不再假装"肯定"。
- 新增退出码：`0` 可交付、`3` 需补语境、`4` 输入错误（错误信息走 `stderr`）。
- `negation_count.py` 的每条歧义/风险加规则编号（`R-SPECIAL / R-LEXICAL / R-QUANT / R-SCOPE / R-DEPTH / R-NONE / R-CONFLICT`），`--json` 新增 `status / confidence / rule_ids / skill_version`。
- 新增输入防御：空输入、超 200 字、文件读不了，一律不猜，返回 `error`。
- 新增规则冲突检测：同句三条以上规则同时触发时报 `R-CONFLICT`。

**可测试性**

- 新增 `tests/labeled_cases.json`（33 条语义标注）与 `scripts/evaluate.py`（极性/状态准确率 + 错例清单）。
- 当前基线：极性 84.38%、状态 100%；已知漏判为词汇化否定（难免/不免）、特殊形式（差点没）、复杂辖域，全部如实留在错例里，不调标注迁就规则。
- 测试 43 → 61 条，新增 `tests/test_contract.py`（15 条契约）与 `tests/test_accuracy.py`（3 条指标）。

**文档**

- `SKILL.md` 重写为"给 Agent 看的 API 文档"：适用/不适用、契约摘要、失败语义、安全边界、版本兼容。
- 新增 `references/contract.md`；`patterns.md`、`examples.md` 补覆盖范围、适用条件与反例。
- 新增安全边界：不用于欺骗、伪造承诺、规避法律或合规表述；需要明确立场时提示直说。

## v1.1.0 — 2026-11-24

- `wanhua.py check` 拆两层：`risks`（规则层歧义，必须改）与 `pragmatic`（语用提示：委婉软化 / 反讽 / 反问），`pass` 需两者皆空。
- `failure_cases.md` 每条加 `FC-xx` 编号与「回归用例」列，附案例↔测试对照表。
- `install.sh` 只装进已存在的候选目录；一个都没有时报错（退出码 1）并提示 `--path`。
- 测试 27 → 43 条。

## v1.0.0 — 2026-11-22

- 首个发布版本：`SKILL.md` 双路径（生成/解码）、`references/patterns.md`、`references/examples.md`、`scripts/negation_count.py`（极性折叠、作用域浅层边界、歧义提示）。
- `wanhua.py` 提供 `analyze / compare / check / templates`。
- GPL-3.0。
