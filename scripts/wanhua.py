#!/usr/bin/env python3
"""绕弯 CLI：Skill 的稳定接口层，脱离 Agent 框架也能调用。

用法：
    python3 scripts/wanhua.py solve "不是不该改"        # 契约输出（默认 JSON）
    python3 scripts/wanhua.py analyze "不是不该认真一点"
    python3 scripts/wanhua.py compare "不是不该改" "该改"
    python3 scripts/wanhua.py check "差点没赶上"
    python3 scripts/wanhua.py templates

退出码：0=ok/low_confidence；3=ambiguous/unknown；4=输入或运行时错误；2=参数错误。
契约字段见 references/contract.md。

Python 调用：
    from wanhua import solve, analyze, compare, check
    solve("不是不该改")["polarity"]   # → "肯定"
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import negation_count as nc  # noqa: E402

__version__ = "1.3.0"

SKILL_NAME = "double-negative-speech"

TEMPLATES = [
    ("不是不 X", "X（语气留余地）"),
    ("并非不 X", "X"),
    ("不能不 X", "必须 X"),
    ("没有理由不 X", "应该 X"),
    ("未必不 X", "大概 X"),
    ("未尝不可 X", "可以 X"),
    ("不是没有 X", "有 X"),
    ("谁说 X 不 Y", "Y（反问式）"),
    ("除了 X，没有别的 Y", "只能 X"),
    ("除非 X，否则不能 Y", "X 才算 Y"),
    ("即使不 X，也不等于不 Y", "不 X 也可能 Y"),
    ("不是不该 X，而是尚未 Y", "该 X，但还没 Y"),
]

# 语用层风险：极性在规则层唯一，但读者可能按另一种语气去读。
# 每条 = (类型, 名称, 正则, 为什么有风险, 怎么补)
PRAGMATIC_CHECKS = [
    (
        "soft-refusal",
        "委婉软化：可能被读成拒绝",
        re.compile(r"(不是不(能|可|会|行|让|给)|并非不(能|可|会|行)|不是没(办法|可能|道理|余地))"),
        "表态场景里「不是不能」常是「不能」的软化说法，读者会当成留面子的拒绝，而不是真的可以",
        "把态度落在明面上，如「可以谈，但有前提」；不要只靠双重否定暗示",
    ),
    (
        "sarcasm",
        "反讽：字面与态度可能相反",
        re.compile(r"(可真是|真是够|好一个|算你|真有你的|果然)"),
        "带「可真是」「好一个」的否定句在口语里常是反讽，字面肯定、实际否定",
        "补一个语境词或直接说结论，别让读者猜这是夸还是损",
    ),
    (
        "rhetorical",
        "反问：字面极性会被翻转",
        re.compile(r"(难道|岂不|岂能|谁说|何尝|莫非)"),
        "反问句的实际断言与字面极性相反：字面「不」，意思是「就是」",
        "要么明确按反问写并给答案，要么改成陈述句，不留两种读法",
    ),
]

# 语用层只覆盖这三类，别当成完整语用推理
PRAGMATIC_COVERAGE = "有限覆盖：委婉软化 / 反讽 / 反问；不覆盖语气强度、礼貌层级、方言差异"


def analyze(sentence: str) -> dict:
    """返回结构化解码结果（极性、作用域、歧义、风险）。"""
    return asdict(nc.analyze(sentence))


def compare(a: str, b: str) -> dict:
    """比较两句极性是否一致，用于生成后的折叠验证。"""
    ra, rb = nc.analyze(a), nc.analyze(b)
    return {
        "left": {"text": a, "polarity": ra.polarity, "weight": ra.total_weight},
        "right": {"text": b, "polarity": rb.polarity, "weight": rb.total_weight},
        "same_polarity": ra.polarity == rb.polarity,
        "advice": "极性一致，可继续核对作用域" if ra.polarity == rb.polarity
        else "极性相反，回译失败：不是绕得不好，是写错了",
    }


def pragmatic_risks(sentence: str) -> list[dict]:
    """语用层提示：规则层唯一，但语气/态度可能被读偏。

    只报提示，不判对错——语用要靠语境定，脚本做不到，也不该假装能做到。
    """
    hits: list[dict] = []
    for kind, name, pattern, why, fix in PRAGMATIC_CHECKS:
        m = pattern.search(sentence)
        if m:
            hits.append({
                "type": kind,
                "name": name,
                "evidence": m.group(0),
                "why": why,
                "fix": fix,
                "layer": "pragmatic",
                "heuristic": True,
            })
    # 反讽只在句子里真的带否定词时才成立，避免把「他真是够努力」误报
    if any(h["type"] == "sarcasm" for h in hits):
        if not nc.analyze(sentence).negations:
            hits = [h for h in hits if h["type"] != "sarcasm"]
    return hits


def check(sentence: str) -> dict:
    """生成结果的歧义自检：规则层唯一 ≠ 语用层唯一。

    两层分开报：
      risks     —— 规则层歧义（否定计数/作用域/量词/特殊形式），非空即不能作为唯一解交付
      pragmatic —— 语用层提示（委婉软化/反讽/反问），不强制改写，但要确认语境兜得住
    """
    rep = nc.analyze(sentence)
    risks = list(rep.ambiguities)
    warnings = list(rep.warnings)
    pragmatic = pragmatic_risks(sentence)
    passed = not risks and not pragmatic

    if risks:
        note = f"规则层已标出 {len(risks)} 处歧义：此句不能作为唯一解交付，需改写或补充语境"
    elif pragmatic:
        note = (f"规则层唯一（{rep.polarity}），但语用层有 {len(pragmatic)} 处提示："
                "不改也能用，但要确认上下文能兜住这句的语气")
    else:
        note = f"规则层无歧义（{rep.polarity}），语用层未命中常见风险模式"

    return {
        "text": sentence,
        "polarity": rep.polarity,
        "weight": rep.total_weight,
        "certainty": rep.certainty,
        "matched_rules": rep.rule_ids,
        "conflicts": rep.conflicts,
        "pass": passed,
        "risks": risks,
        "warnings": warnings,
        "pragmatic": pragmatic,
        "note": note,
    }


def _split_rules(items: list[str]) -> list[dict]:
    """把带 [R-XXX] 前缀的条目拆成 {id, note}，供宿主做可解释展示。"""
    out: list[dict] = []
    for item in items:
        m = re.match(r"\[(R-[A-Z]+)\]\s*(.*)", item)
        if m:
            out.append({"id": m.group(1), "note": m.group(2)})
        else:
            out.append({"id": "R-RAW", "note": item})
    return out


def solve(text: str, mode: str = "decode") -> dict:
    """Skill 级契约输出：固定字段、显式状态、置信度、可追溯规则。

    字段定义见 references/contract.md。status 语义：
      ok             —— 规则层干净，可直接交付
      low_confidence —— 能算，但有词汇化/层级风险，建议复核
      ambiguous      —— 规则层已标歧义，不能当唯一解
      unknown        —— 没有否定词，本句不在绕弯范畴
      error          —— 输入不合法（空、超长）
    """
    raw = (text or "").strip()
    base = {
        "skill": SKILL_NAME,
        "version": __version__,
        "mode": mode,
        "input_text": raw,
    }
    if not raw:
        return {**base, "status": "error", "polarity": None, "confidence": 0.0,
                "certainty": "out_of_scope", "rules_version": nc.RULES_VERSION,
                "rules": [], "scope": [], "pragmatic_hint": None,
                "explain": "空输入", "next_step": "传入一句中文句子，长度 1~200 字"}
    if len(raw) > nc.MAX_INPUT_CHARS:
        return {**base, "status": "error", "polarity": None, "confidence": 0.0,
                "certainty": "out_of_scope", "rules_version": nc.RULES_VERSION,
                "rules": [], "scope": [], "pragmatic_hint": None,
                "explain": f"输入 {len(raw)} 字，超过上限 {nc.MAX_INPUT_CHARS} 字",
                "next_step": "按标点切成小句，逐句分析"}

    rep = nc.analyze(raw)
    pragmatic = pragmatic_risks(raw)

    # 语用层已翻转（反问/反讽）或压根没有否定词 —— 规则层给不出可信极性，
    # 直接报 out_of_scope，不硬塞一个低置信度的"肯定/否定"。
    pragmatic_flip = any(p["type"] in ("rhetorical", "sarcasm") for p in pragmatic)
    if rep.status == "unknown":
        status, certainty = ("out_of_scope", "out_of_scope") if pragmatic else ("unknown", "out_of_scope")
    elif pragmatic_flip:
        status, certainty = "out_of_scope", "out_of_scope"
    else:
        status, certainty = rep.status, rep.certainty

    polarity = None if status in ("unknown", "out_of_scope") else rep.polarity
    explain = (
        f"否定权重合计 {rep.total_weight}，按奇偶折叠为{rep.polarity}"
        if rep.total_weight else "未命中否定词"
    )
    if rep.rule_ids:
        explain += f"；触发规则 {'、'.join(rep.rule_ids)}"

    if rep.total_weight == 0 and not pragmatic:
        explain = "未命中否定词"
    elif status == "out_of_scope":
        kinds = "、".join(sorted({p["type"] for p in pragmatic})) or "无否定证据"
        explain = (
            f"规则层给不出可信极性：命中语用迹象 {kinds}，"
            "反问/反讽会翻转字面极性，纯规则匹配无法定论"
        )

    if status == "unknown":
        next_step = "不是绕弯句，按普通语义理解"
    elif status == "out_of_scope":
        next_step = "超出规则覆盖范围，建议人工复核：不要在此给出极性结论"
    elif status == "ambiguous":
        next_step = "不能作为唯一解：补语境，或按 rules 里对应规则改写"
    elif rep.status == "low_confidence":
        next_step = "可用，但先看 risks（多为词汇化否定或层级过深）"
    else:
        next_step = "规则层干净，可交付；仍建议核对作用域是否符合原意"

    return {
        **base,
        "status": status,
        "certainty": certainty,
        "rules_version": nc.RULES_VERSION,
        "polarity": polarity,
        "confidence": None if status == "out_of_scope" else rep.confidence,
        "rules": _split_rules(rep.ambiguities + rep.warnings),
        "scope": [{"token": n.token, "weight": n.weight, "kind": n.kind, "scope": n.scope}
                  for n in rep.negations],
        "pragmatic_hint": {
            "heuristic": True,
            "coverage": PRAGMATIC_COVERAGE,
            "items": pragmatic,
            "affects_polarity": False,
        },
        "explain": explain,
        "next_step": next_step,
    }


EXIT_OK = 0
EXIT_NEEDS_CONTEXT = 3
EXIT_INPUT_ERROR = 4


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 1
    cmd, rest = argv[0], argv[1:]

    if cmd == "solve":
        if not rest:
            print("solve 需要一句文本", file=sys.stderr)
            return EXIT_INPUT_ERROR
        result = solve(" ".join(rest))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["status"] == "error":
            return EXIT_INPUT_ERROR
        return EXIT_OK if result["status"] in ("ok", "low_confidence") else EXIT_NEEDS_CONTEXT
    if cmd == "analyze" and rest:
        print(json.dumps(analyze(" ".join(rest)), ensure_ascii=False, indent=2))
    elif cmd == "compare" and len(rest) >= 2:
        print(json.dumps(compare(rest[0], rest[1]), ensure_ascii=False, indent=2))
    elif cmd == "check" and rest:
        result = check(" ".join(rest))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == "templates":
        for pat, meaning in TEMPLATES:
            print(f"{pat}\t→ {meaning}")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
