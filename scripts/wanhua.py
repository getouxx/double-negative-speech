#!/usr/bin/env python3
"""绕弯 CLI：脱离 Agent 框架，直接在脚本里调用分析能力。

用法：
    python3 scripts/wanhua.py analyze "不是不该认真一点"
    python3 scripts/wanhua.py compare "不是不该改" "该改"
    python3 scripts/wanhua.py check "差点没赶上"
    python3 scripts/wanhua.py templates

Python 调用：
    from wanhua import analyze, compare, check
    analyze("不是不该改")["polarity"]   # → "肯定"
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import negation_count as nc  # noqa: E402

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
            })
    # 反讽只在句子里真的带否定词时才成立，避免把「他真是够努力」误报
    if any(h["type"] == "sarcasm" for h in hits):
        if not nc.analyze(sentence).negations:
            hits = [h for h in hits if h["type"] != "sarcasm"]
    # 「难道」本身不是否定，但配上句末语气词才构成完整反问，单独出现只算弱提示
    return hits


def check(sentence: str) -> dict:
    """生成结果的歧义自检：规则层唯一 ≠ 语用层唯一。

    两层分开报：
      risks     —— 规则层歧义（否定计数/作用域/量词/特殊形式），非空即不能作为唯一解交付
      pragmatic —— 语用层提示（委婉软化/反讽/反问/弱断言），不强制改写，但要确认语境兜得住
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
        "pass": passed,
        "risks": risks,
        "warnings": warnings,
        "pragmatic": pragmatic,
        "note": note,
    }


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 1
    cmd, rest = argv[0], argv[1:]

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
