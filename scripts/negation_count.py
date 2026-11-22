#!/usr/bin/env python3
"""否定词计数助手：标出句子里的否定词位置，并按奇偶给出整体倾向。

用法：
    python3 negation_count.py "不想不安装在脑子里的知识"

只做机械计数，不判断作用域。作用域必须人工按 SKILL.md 的 B3 步检查。
多字构式（如「没有理由不」「不得不」）内含两个否定，权重计 2。
"""
import sys

# (串, 权重)：权重 = 该构式内含的否定次数
NEGATIONS = [
    ("没有理由不", 2), ("不是不", 2), ("不能不", 2), ("不得不", 2),
    ("未尝不可", 2), ("非...不可", 2),
    ("未必", 1), ("难以", 1), ("缺乏", 1), ("避免", 1), ("拒绝", 1),
    ("否认", 1), ("禁止", 1), ("取消", 1), ("排除", 1),
    ("没", 1), ("未", 1), ("不", 1), ("无", 1), ("非", 1),
    ("否", 1), ("别", 1), ("勿", 1), ("莫", 1),
]
# 含否定字形但不表否定的常见词，先跳过，避免误计
FALSE_POSITIVES = ["非常", "无比", "无论", "无数", "无聊", "未来", "别人", "别的", "无妨"]


def scan(text: str):
    hits = []
    i = 0
    while i < len(text):
        matched = False
        for fp in FALSE_POSITIVES:
            if text.startswith(fp, i):
                i += len(fp)
                matched = True
                break
        if matched:
            continue
        for tok, weight in NEGATIONS:
            raw = tok.replace("...", "")
            if text.startswith(raw, i):
                hits.append((i, tok, weight))
                i += len(raw)
                matched = True
                break
        if not matched:
            i += 1
    return hits


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    text = " ".join(sys.argv[1:]).strip()
    hits = scan(text)

    print(f"句子：{text}")
    print(f"字数：{len(text)}")
    print(f"否定位置：{len(hits)} 处")
    for idx, (pos, tok, weight) in enumerate(hits, 1):
        raw = tok.replace("...", "")
        print(f"  {idx}. 第 {pos + 1} 字  「{tok}」（含 {weight} 个否定）"
              f"  上文：…{text[max(0, pos - 6):pos]}｜下文：{text[pos + len(raw):pos + len(raw) + 6]}…")

    total = sum(w for _, _, w in hits)
    print(f"否定总数：{total}")
    print("整体倾向：" + ("肯定（否定为偶数）" if total % 2 == 0 else "否定（否定为奇数）"))

    if total >= 4:
        print("警告：否定层数达到 4 层，读者几乎无法稳定解码，建议拆句。")
    if total == 0:
        print("提示：未发现否定词，本句不在绕弯范畴内。")
    print("\n下一步（必须人工做）：逐个确认每个否定词修饰的范围，再判断整体语义。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
