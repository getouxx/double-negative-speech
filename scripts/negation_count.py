#!/usr/bin/env python3
"""否定分析器：极性折叠 + 作用域浅层边界 + 歧义提示 + 特殊否定形式。

用法：
    python3 negation_count.py "不想不安装在脑子里的知识"
    python3 negation_count.py --json "没有理由不承认这不是个办法"
    python3 negation_count.py --ambiguity "差点没赶上"
    python3 negation_count.py --file input.txt

输出的是**可回归的结构化结果**，不是最终语义结论。作用域为浅层启发式标定
（按标点与连词切分小句），跨小句的深层修饰仍需人工确认。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# ---------------------------------------------------------------- 词表
# (表面形式, 否定权重, 类型, 说明)
# 权重 = 该形式内含的否定次数。长构式先匹配，避免「没有理由不」被拆成「没有」+「不」只记一票。
NEGATION_ENTRIES: list[tuple[str, int, str, str]] = [
    # 多字构式（内含两次否定 → 正）
    ("没有理由不", 2, "construct", "『没有理由不』= 应该"),
    ("未尝不可", 2, "construct", "『未尝不可』= 可以"),
    ("未尝不", 2, "construct", "『未尝不』= 不是不，即肯定"),
    ("不能不", 2, "construct", "『不能不』= 必须"),
    ("不得不", 2, "construct", "『不得不』= 必须（无可奈何）"),
    ("不是没有", 2, "construct", "『不是没有』= 有，但语气留余地"),
    ("无不", 2, "construct", "『无不』= 全都"),
    ("无非", 2, "construct", "『无非』= 只是"),
    ("不无", 2, "construct", "『不无』= 有（书面）"),
    ("并非不", 2, "construct", "『并非不』= 是"),
    ("不是不", 2, "construct", "『不是不』= 是，只是程度留了口"),
    # 词汇化否定（单次否定，但字形不像「不」）
    ("难免不", 1, "lexical", "『难免不』易与『难免』混用，属歧义高频区"),
    ("难免", 1, "lexical", "『难免』= 不可避免，语气近肯定"),
    ("不免", 1, "lexical", "『不免』= 难免"),
    ("未必", 1, "lexical", "『未必』= 不一定"),
    ("难以", 1, "lexical", "『难以』= 很难"),
    ("缺乏", 1, "lexical", "『缺乏』= 没有"),
    ("避免", 1, "lexical", "『避免』= 使之不发生"),
    ("拒绝", 1, "lexical", "『拒绝』= 不愿意"),
    ("否认", 1, "lexical", "『否认』= 说不"),
    ("禁止", 1, "lexical", "『禁止』= 不许"),
    ("取消", 1, "lexical", "『取消』= 使之无效"),
    ("排除", 1, "lexical", "『排除』= 不算在内"),
    # 歧义结构（字面两次否定，语用未必）
    ("差点没", 2, "ambiguous", "『差点没』字面两否，实际多指『差点儿』（事情没发生）"),
    ("险些没", 2, "ambiguous", "『险些没』同上，是否发生需看语境"),
    ("好不", 2, "ambiguous", "『好不热闹』= 很热闹，是程度义而非否定"),
    ("几乎不", 1, "basic", "『几乎不』= 极少"),
    # 基础否定
    ("没", 1, "basic", "基础否定"),
    ("未", 1, "basic", "基础否定"),
    ("不", 1, "basic", "基础否定"),
    ("无", 1, "basic", "基础否定"),
    ("非", 1, "basic", "基础否定"),
    ("否", 1, "basic", "基础否定"),
    ("别", 1, "basic", "祈使否定"),
    ("勿", 1, "basic", "祈使否定"),
    ("莫", 1, "basic", "祈使否定"),
    ("甭", 1, "basic", "基础否定"),
]

# 含否定字形但不表否定的常见词，遇到先整词跳过
FALSE_POSITIVES = [
    "非常", "无比", "无论", "无数", "无聊", "未来", "别人", "别的", "无妨",
    "不管", "不停", "不断", "不料", "不禁", "不由得", "差不多", "了不起",
]

# 小句切分：标点 + 连词。作用域暂定到本小句结束。
CLAUSE_PUNCT = "，,。；;：:！!？?、"
CLAUSE_CONJ = [
    "但是", "然而", "不过", "而是", "而且", "并且", "所以", "因此", "因为",
    "如果", "假如", "要是", "除非", "否则", "即使", "虽然", "尽管", "只要",
    "只有", "或者", "以及", "同时", "然后",
]

QUANTIFIERS = ["全都", "全部", "任何", "一切", "完全", "丝毫", "一律", "都"]
# 「一点」只有在「一点都不/也没」这类否定框架里才是全称降级信号，否则只是程度补语
QUANTIFIER_PAIR = re.compile(r"(一点|丝毫)(都|也)")
QUANTIFIER_MAX_GAP = 8
SCOPE_SPLITTERS = ["想", "愿意", "打算", "能够", "可以", "会", "敢", "该", "需要"]
DEPTH_WARN = 4


@dataclass
class Negation:
    token: str
    start: int
    end: int
    weight: int
    kind: str
    note: str
    scope: str = ""


@dataclass
class Report:
    text: str
    negations: list[Negation] = field(default_factory=list)
    total_weight: int = 0
    polarity: str = ""
    clauses: list[str] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def split_clauses(text: str) -> list[tuple[int, int, str]]:
    """按标点与连词切小句，返回 (start, end, 内容)。"""
    marks = [i for i, ch in enumerate(text) if ch in CLAUSE_PUNCT]
    for conj in CLAUSE_CONJ:
        marks.extend(m.start() for m in re.finditer(conj, text))
    marks = sorted(set(marks))
    spans: list[tuple[int, int, str]] = []
    prev = 0
    for i in marks:
        if i > prev:
            spans.append((prev, i, text[prev:i]))
        spans.append((i, i + 1, text[i]))
        prev = i + 1
    if prev < len(text):
        spans.append((prev, len(text), text[prev:]))

    # 合并成"有意义小句"：纯标点/连词片段并回前一句
    chunks: list[tuple[int, int, str]] = []
    start = 0
    for s, e, seg in spans:
        if not seg.strip(CLAUSE_PUNCT + "".join(CLAUSE_CONJ)):
            chunks.append((start, e, text[start:e]))
            start = e
    if start < len(text):
        chunks.append((start, len(text), text[start:]))
    return chunks


def _scope_for(text: str, start: int, chunks: list[tuple[int, int, str]]) -> str:
    for s, e, seg in chunks:
        if s <= start < e:
            return seg.strip().strip(CLAUSE_PUNCT)
    return text[start:].strip(CLAUSE_PUNCT)


def scan(text: str) -> list[Negation]:
    hits: list[Negation] = []
    i = 0
    while i < len(text):
        for fp in FALSE_POSITIVES:
            if text.startswith(fp, i):
                i += len(fp)
                break
        else:
            for surface, weight, kind, note in NEGATION_ENTRIES:
                if text.startswith(surface, i):
                    hits.append(Negation(surface, i, i + len(surface), weight, kind, note))
                    i += len(surface)
                    break
            else:
                i += 1
    return hits


def analyze(text: str) -> Report:
    text = text.strip()
    rep = Report(text=text)
    rep.negations = scan(text)
    rep.total_weight = sum(n.weight for n in rep.negations)
    rep.polarity = "肯定" if rep.total_weight % 2 == 0 else "否定"

    chunks = split_clauses(text)
    rep.clauses = [c[2].strip() for c in chunks if c[2].strip()]
    for n in rep.negations:
        n.scope = _scope_for(text, n.start, chunks)

    # 歧义与风险
    for n in rep.negations:
        if n.kind == "ambiguous":
            rep.ambiguities.append(f"「{n.token}」：{n.note}")
        elif "歧义" in n.note:
            rep.ambiguities.append(f"「{n.token}」：{n.note}")

    for n in rep.negations:
        if n.kind not in ("basic", "construct"):
            continue
        window = text[n.end:n.end + QUANTIFIER_MAX_GAP]
        found = next((q for q in QUANTIFIERS if q in window), None)
        if found is None and QUANTIFIER_PAIR.search(window):
            found = "一点…都/也"
        if found:
            rep.ambiguities.append(
                f"「{n.token}」后接全称词「{found}」，可能降成特称否定："
                f"「{n.scope}」需确认是「全否」还是「部分否」"
            )

    # 同一小句内、被助动词隔开的两个否定 → 作用域可能读反
    for i in range(len(rep.negations) - 1):
        a, b = rep.negations[i], rep.negations[i + 1]
        if a.scope and b.scope and a.scope == b.scope:
            between = text[a.end:b.start]
            if any(s in between for s in SCOPE_SPLITTERS):
                rep.ambiguities.append(
                    f"「{a.token}」与「{b.token}」之间隔着「{between.strip() or '助动词'}」，"
                    "作用域可能归属不同，需逐段确认"
                )

    decisive = sum(n.weight for n in rep.negations if n.kind != "ambiguous")
    if decisive >= DEPTH_WARN:
        rep.warnings.append(f"有效否定层数 {decisive}，超过 {DEPTH_WARN - 1} 层，读者难以稳定解码")
    if rep.total_weight == 0:
        rep.warnings.append("未发现否定词，本句不在绕弯范畴内")
    if any(n.kind == "lexical" for n in rep.negations):
        lexical = [n.token for n in rep.negations if n.kind == "lexical"]
        rep.warnings.append(f"含词汇化否定 {'、'.join(lexical)}，纯字面计数容易漏")
    return rep


def render(rep: Report) -> str:
    out = [f"句子：{rep.text}", f"字数：{len(rep.text)}", f"否定位置：{len(rep.negations)} 处"]
    for idx, n in enumerate(rep.negations, 1):
        out.append(
            f"  {idx}. 第 {n.start + 1} 字 「{n.token}」（{n.weight} 个否定 · {n.kind}）"
            f"  作用域≈「{n.scope}」"
        )
    out.append(f"否定总数：{rep.total_weight}")
    out.append(f"整体倾向：{rep.polarity}")
    if rep.clauses:
        out.append("小句切分：")
        out.extend(f"  - {c}" for c in rep.clauses)
    if rep.ambiguities:
        out.append("歧义提示：")
        out.extend(f"  ! {a}" for a in rep.ambiguities)
    if rep.warnings:
        out.append("风险：")
        out.extend(f"  ! {w}" for w in rep.warnings)
    out.append("\n作用域为浅层启发式标定；跨小句的深层修饰仍需人工确认。")
    return "\n".join(out)


def to_json(rep: Report) -> str:
    return json.dumps(asdict(rep), ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="中文否定分析：极性、作用域、歧义")
    ap.add_argument("sentence", nargs="*", help="待分析句子")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--ambiguity", action="store_true", help="只输出歧义与风险")
    ap.add_argument("--file", help="从文件读取句子")
    args = ap.parse_args(argv)

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8").strip()
    else:
        text = " ".join(args.sentence).strip()
    if not text:
        ap.print_help()
        return 1

    rep = analyze(text)
    if args.json:
        print(to_json(rep))
    elif args.ambiguity:
        items = rep.ambiguities + rep.warnings
        print("\n".join(items) if items else "未发现明显歧义")
    else:
        print(render(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
