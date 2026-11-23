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


def check(sentence: str) -> dict:
    """生成结果的歧义自检：规则层唯一 ≠ 语用层唯一。"""
    rep = nc.analyze(sentence)
    risky = rep.ambiguities + rep.warnings
    return {
        "text": sentence,
        "polarity": rep.polarity,
        "pass": not rep.ambiguities,
        "risks": risky,
        "note": "规则层无歧义" if not rep.ambiguities
        else "规则层已标出歧义：此句不能作为唯一解交付，需改写或补充语境",
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
        print(json.dumps(check(" ".join(rest)), ensure_ascii=False, indent=2))
    elif cmd == "templates":
        for pat, meaning in TEMPLATES:
            print(f"{pat}\t→ {meaning}")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
