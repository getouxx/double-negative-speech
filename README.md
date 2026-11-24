# 绕弯说话术 / double-negative-speech

**中文绕弯话术的生成与解码 Skill：把否定当算子处理——否定极性的奇偶折叠 × 作用域定域 × 量词范围 × 条件套嵌。**

当前版本 **v1.2.0**。调用契约（字段、状态、退出码、规则编号）见 [`references/contract.md`](references/contract.md)，变更记录见 [`CHANGELOG.md`](CHANGELOG.md)。

范围说清楚：它只管**逻辑绕**（否定层数、否定修饰谁、量词全称与否、条件让步骨架），不管**词义绕**（生造词、别扭搭配、同音错字）。前者能唯一解码，后者读不懂就是写坏了。

## 快速开始

不装 Agent 也能跑。克隆后依次走一遍生成与验证：

```bash
git clone https://github.com/getouxx/double-negative-speech.git
cd double-negative-speech
```

**第一步：锁定真实意思。** 想表达"我该认真干活了"，先原样写下来，不加工：

> 我该认真干活了

**第二步：选绕度。** 默认中绕——双重否定 + 反向修饰，读一遍会愣住，但还能解：

> 要说再这么下去还算在做事，恐怕没几个人不觉得勉强。

**第三步：折叠验证。** 把绕句和原句一起交给 CLI，确认极性没漂：

```bash
$ python3 scripts/wanhua.py compare "要说再这么下去还算在做事，恐怕没几个人不觉得勉强" "我该认真干活了"
"same_polarity": true,
"advice": "极性一致，可继续核对作用域"
```

极性一致只说明正负没翻转，还得继续核作用域——这正是下一步。

**第四步：歧义自检。** 生成的句子必须扛得住规则层检查：

```bash
$ python3 scripts/wanhua.py check "要说再这么下去还算在做事，恐怕没几个人不觉得勉强"
{
  "text": "要说再这么下去还算在做事，恐怕没几个人不觉得勉强",
  "polarity": "肯定",
  "weight": 2,
  "pass": true,
  "risks": [],
  "warnings": [],
  "pragmatic": [],
  "note": "规则层无歧义（肯定），语用层未命中常见风险模式"
}
```

规则层通过不等于能交付。换成一句"极性唯一、但一读就像婉拒"的句子，`check` 会给出语用层提示：

```bash
$ python3 scripts/wanhua.py check "这件事，不是不能商量。"
{
  "text": "这件事，不是不能商量。",
  "polarity": "肯定",
  "pass": false,
  "risks": [],
  "pragmatic": [
    {
      "type": "soft-refusal",
      "name": "委婉软化：可能被读成拒绝",
      "evidence": "不是不能",
      "why": "表态场景里「不是不能」常是「不能」的软化说法，读者会当成留面子的拒绝，而不是真的可以",
      "fix": "把态度落在明面上，如「可以谈，但有前提」；不要只靠双重否定暗示",
      "layer": "pragmatic"
    }
  ],
  "note": "规则层唯一（肯定），但语用层有 1 处提示：不改也能用，但要确认上下文能兜住这句的语气"
}
```

读法：`risks` 为空说明否定计数、作用域、量词都没问题；`pass: false` 是因为 `pragmatic` 里有一条——这句在规则上是"可以"，在语用上容易被当成"不一定可以"。这类句子**不必废弃**，但要确认上下文能兜住，或按 `fix` 把态度写明白。

反问同理：

```bash
$ python3 scripts/wanhua.py check "难道这不叫负责吗？"
# "polarity": "否定"
# "pragmatic": [{"type": "rhetorical", "evidence": "难道", ...}]
# "note": "规则层唯一（否定），但语用层有 1 处提示……"
```

换成故意有坑的句子，规则层就拦下来：

```bash
$ python3 scripts/negation_count.py "不想不安装在脑子里的知识"
# 歧义提示：
#   ! 「不」与「不」之间隔着「想」，作用域可能归属不同，需逐段确认
```

**第五步：交付。** 用户没要解析就只给句子；出题、做测试才附答案和错法。

## 同一句话的三档绕度

真实意思是"我该正经干活了"，三档产出对比如下——同样是真话，绕度不同，读者付出的解码成本不同：

| 绕度 | 手法 | 产出 | 读者体验 | 适用 |
| --- | --- | --- | --- | --- |
| 轻绕 | 一处双重否定 | 这种状态，不是不该认真一点。 | 愣半秒，随即读通 | 委婉表态、留余地 |
| 中绕 | 双重否定 + 反向修饰 | 要说再这么下去还算在做事，恐怕没几个人不觉得勉强。 | 需要回读一次 | 话术、文案、日常绕 |
| 重绕 | 三重否定 + 条件套嵌 + 语序前置 | 不是不该承认，再这么下去，已经谈不上像话了。 | 数否定词才能定正负 | 选择题陷阱、阅读理解 |

三句回译后必须收敛到同一句"我该正经干活了"；收敛不回去，就不是绕得好，是写错了。

## 理论内核：否定算子

把这套东西当成一个可计算的算子体系，而不是修辞手感：

- **极性折叠**：否定词个数决定整体正负，偶数肯定、奇数否定。多字构式（「没有理由不」「不得不」）内含两次否定，计两票。
- **作用域定域**：极性对了还不够，得知道每个否定管到哪一段。「不［想装进去］」和「［不想］装进去」极性相同，意思相反。
- **量词降级**：否定挂到全称词上，全否会降成特称否定——「不是一点都没有」约等于「多少有一点」，不等于「有」。
- **框架保留**：条件与让步句先抽骨架再填否定，「除非…否则…」里的否定最容易读反。

生成 = 用这套算子把一句直白话折叠；解码 = 反过来把它逐层展开。两边跑完必须收敛到同一句，才算合格。

## 它解决什么问题

「不想不安装在脑子里的知识」这种句子，绕的不是词义，是**否定词的数量与作用范围**。漏数一个「不」，意思就整个翻过来。这个 Skill 把这件事变成可复现的流程，而不是靠语感猜。

## 两种用法

| 用户要什么 | 走哪条路 |
| --- | --- |
| 把直白的话说绕、留余地、不像在表态 | 生成路径 |
| 把绕话翻成人话、判断「勾选/不勾选」到底啥意思 | 解码路径 |
| 出带陷阱的选择题、勾选项、阅读理解题 | 生成路径 + 必须给答案 |

## 生成路径（五步）

1. **先锁定真实意思**，写成一句最直白的话。这句话是地基，中途不许改。
2. **选绕度**：轻 / 中 / 重，默认中绕，出题用重绕。
3. **套句式**，取自 `references/patterns.md`，嵌套不超过三层。
4. **折叠验证**：按解码路径回译一遍，必须与原句完全一致。
5. **歧义自检**：跑 `wanhua.py check`。`risks` 非空＝规则层有歧义，必须改写；`pragmatic` 非空＝规则层唯一但语用有坑（委婉软化/反讽/反问），要么补语境，要么按 `fix` 改。

## 解码路径（七步）

1. 圈否定词 → 2. 数奇偶（偶数＝肯定，奇数＝否定）→ 3. 查作用域 → 4. 查量词陷阱 → 5. 拆条件与让步骨架 → 6. 落成一句肯定句 → 7. 有真歧义就两种解读并列，不硬猜。

## 脚本与命令行

| 命令 | 作用 |
| --- | --- |
| `python3 scripts/negation_count.py "句子"` | 人读版：否定位置、作用域、小句切分、歧义与风险 |
| `python3 scripts/negation_count.py --json "句子"` | 结构化输出，字段稳定，便于接其他工具 |
| `python3 scripts/negation_count.py --ambiguity "句子"` | 只看歧义与风险 |
| `python3 scripts/wanhua.py solve "句子"` | **契约输出**：`status/polarity/confidence/rules/scope/pragmatic_hint/explain/next_step`，宿主首选 |
| `python3 scripts/wanhua.py analyze "句子"` | 纯函数式分析，返回 dict |
| `python3 scripts/wanhua.py compare "绕句" "原句"` | 折叠验证：极性是否一致 |
| `python3 scripts/wanhua.py check "句子"` | 歧义自检：规则层 `risks` + 语用层 `pragmatic`，`pass` 需两者皆空 |
| `python3 scripts/wanhua.py templates` | 列出可用句式与等价意思 |

也能当库用，脱离 Agent 框架：

```python
from wanhua import solve, analyze, compare, check
analyze("不是不该改")["polarity"]      # '肯定'
compare("不是不该改", "该改")["same_polarity"]  # True
```

输出里 `scope` 是**浅层启发式**标定的作用域（按标点与连词切小句），跨小句的深层修饰仍需人工确认——工具负责把可疑处圈出来，不负责替你下最后判断。

## 给宿主的契约：一次 `solve` 就够了

```bash
$ python3 scripts/wanhua.py solve "差点没赶上"
{
  "skill": "double-negative-speech",
  "version": "1.2.0",
  "mode": "decode",
  "input_text": "差点没赶上",
  "status": "ambiguous",
  "polarity": "肯定",
  "confidence": 0.5,
  "rules": [
    {
      "id": "R-SPECIAL",
      "note": "「差点没」：『差点没』字面两否，实际多指『差点儿』（事情没发生）"
    }
  ],
  "scope": [
    {"token": "差点没", "weight": 2, "kind": "ambiguous", "scope": "差点没赶上"}
  ],
  "pragmatic_hint": {
    "heuristic": true,
    "coverage": "有限覆盖：委婉软化 / 反讽 / 反问；不覆盖语气强度、礼貌层级、方言差异",
    "items": [],
    "affects_polarity": false
  },
  "explain": "否定权重合计 2，按奇偶折叠为肯定；触发规则 R-SPECIAL",
  "next_step": "不能作为唯一解：补语境，或按 rules 里对应规则改写"
}
```
（真实输出，退出码 `3`。）

五种 `status` 决定能不能交付：

| `status` | 什么时候出现 | 宿主怎么办 |
| --- | --- | --- |
| `ok` | 规则层干净 | 直接交付 |
| `low_confidence` | 有词汇化否定或层级过深，无歧义 | 交付时带上 `rules` |
| `ambiguous` | 量词降级 / 特殊形式 / 作用域分歧 / 规则冲突 | 不能当唯一解，补语境或并列两种读法 |
| `unknown` | 没有否定词（`polarity: null`） | 不是绕弯句，按普通语义理解 |
| `error` | 空输入、超 200 字、文件读不了 | 修输入重试，**别把 error 当否定** |

退出码：`0` 可交付、`3` 需补语境、`4` 输入错误（错误写 `stderr`）、`2` 参数错误。完整字段与规则编号表在 `references/contract.md`。

## 准确率：有标注集，能回落就报警

```bash
$ python3 scripts/evaluate.py
用例数：33
极性准确率：84.38%
状态准确率：100.00%
错例：
  - [lexical-limitation] 难免有些遗憾  polarity: 期望 肯定 / 实得 否定
  - [special-form-limitation] 他差点没摔倒  polarity: 期望 否定 / 实得 肯定
  ...
```

标注集 `tests/labeled_cases.json` 记的是**语义极性**（人判），不是字面折叠结果——所以上表能暴露漏数、量词、特殊形式造成的翻转。已知漏判（词汇化否定、`差点没`、复杂辖域）如实留在错例里，不调标注迁就规则；`tests/test_accuracy.py` 把 80% / 90% 作为下限，掉下去就红。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

61 条用例，分四个文件：

- `tests/test_negation_count.py`（32 条）：极性奇偶、构式权重、词汇化否定、歧义结构、量词降级（含反例）、作用域边界、假阳性、CLI 契约；`FailureCaseTests` 直接对应 `failure_cases.md` 的 FC-04/09/12/15/16。
- `tests/test_wanhua.py`（11 条）：`check` 的规则层/语用层分离、委婉软化正反例、反讽需带否定词、`compare` 折叠验证、字段契约。
- `tests/test_contract.py`（15 条）：`solve` 字段稳定性、状态语义、退出码 `0/3/4`、空输入与超长输入、错误走 `stderr`、规则编号可追溯。
- `tests/test_accuracy.py`（3 条）：标注集极性/状态准确率下限。

改规则前先跑基线，改完再跑，红一条就说明行为被改坏了。

## 安装

```bash
./install.sh                 # 复制到"已存在"的各平台 Skill 目录，不会新建目录
./install.sh --link          # 软链接，改仓库即生效
./install.sh --path ~/skills # 只装到指定位置，目录不存在会自动创建
./install.sh --dry-run       # 只打印计划，不落盘
```

默认候选目录：豆包 `.user_skills`、Claude `~/.claude/skills`、Codex `~/.codex/skills`、`~/.agents/skills`，均可用环境变量（`DOUBAO_SKILLS` 等）覆盖。已存在同名目录时跳过，`--force` 覆盖。

**一个候选目录都不存在时**（新机器、没装过任何 Agent 平台）：脚本不装任何东西，打印检查过的四段路径，以退出码 `1` 结束，并提示两条出路——`./install.sh --path ~/skills`，或 `DOUBAO_SKILLS=/your/skills ./install.sh`。它不会偷偷 `mkdir` 出一堆空目录。

## 安全与误用边界

这个 Skill 能把"拒绝"包装成"不是不能"，所以必须写清红线：

- **不用于欺骗**：不伪造承诺、不隐瞒条件、不把拒绝包装成同意。
- **不用于规避明确表态**：合同、合规声明、法律文书、对外公告、安全提示——这类场景先提示"建议直说"。
- **不用于操纵**：不教人用歧义套取利益、拖住对方、规避责任。
- **输出可解释**：每条歧义都带规则编号（`R-QUANT`/`R-SPECIAL`/`R-SCOPE`…），用户能追问"为什么判成歧义"。
- 用户要求"给准话"时，生成侧只给直白版。

## 版本与兼容

- **v1.2.0**（2026-11-24）：契约化、状态与退出码、标注集评估、安全边界。历史见 `CHANGELOG.md`。
- 运行环境：Python ≥ 3.8，仅标准库，无第三方依赖。
- 兼容规则：新增字段算兼容；删除字段、改 `status` 取值、改退出码语义算破坏性变更，必须升版本。

## 平台适配

仓库里两份 YAML 是 Agent 平台读的元数据，不参与逻辑：

```yaml
interface:
  display_name: "绕弯说话术"      # 面板标题，4~10 汉字
  short_description: "一句话副标题" # 只做展示，不做触发
  default_prompt: "使用 $double-negative-speech 帮我完成……"

policy:
  allow_implicit_invocation: true  # 允许不点名也被触发
```

对应关系：`SKILL.md` 的 `name` = 目录名 = `$` 调用标识，必须是英文 slug；`display_name` 只给人看。

接其他框架时，把 `SKILL.md` 正文当系统提示片段即可，元数据另写：

- **LangChain**：`SystemMessage` 里塞 SKILL.md 正文，`description` 字段当路由条件（相当于 `description` 的触发语义）；工具侧包一个调用 `wanhua.analyze` 的 `Tool`。
- **Semantic Kernel**：写成 `KernelFunction`/plugin，函数体调 `analyze()`，`description` 用来做函数选择；提示词模板里带 `patterns.md` 的句式表。
- 任何框架都别依赖 YAML——它只是某个产品的面板配置，换了平台就重写一份。

## 失败案例库

`references/failure_cases.md` 按失败类型归档真实翻车案例：作用域误判、漏数否定、构式拆分错、量词降级、词汇化漏计、特殊否定歧义、层级过深、词义绕冒充逻辑绕。每条带 `FC-xx` 编号、"原句 / 本意 / 失败原因 / 修正 / **回归用例**"。

回归用例列是硬要求：规则能判的必须写成测试方法名（如 FC-04 → `test_fc04_four_layers_flagged`），只能靠人读语气的写 `manual:FC-xx` 并注明原因。文末有一张"案例 ↔ 测试对照"表，改规则时按图索骥。同类累计三条就该改规则，而不是继续攒例句。

## 贡献

见 [CONTRIBUTING.md](CONTRIBUTING.md)：新增句式的格式、失败案例必须绑回归用例、改规则后要跑 `evaluate.py` 且准确率不得低于基线。

## License

GPL-3.0，见 [LICENSE](LICENSE)。
