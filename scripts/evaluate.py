#!/usr/bin/env python3
"""在标注测试集上评估解码效果：极性准确率、状态准确率、错例清单。

用法：
    python3 scripts/evaluate.py                       # 默认读 tests/labeled_cases.json
    python3 scripts/evaluate.py --min-acc 0.80        # 低于阈值退出码 1（可用于 CI）
    python3 scripts/evaluate.py --json                # 机器可读

指标定义：
    极性准确率 = polarity 与标注一致的条数 / 标注了 polarity 的条数
    状态准确率 = status 与标注一致的条数 / 标注了 status 的条数
    否定类召回 = 判为"否定"且标注也是否定的条数 / 标注为否定的条数
    否定类精确 = 判为"否定"且标注也是否定的条数 / 全部判为否定的条数
    这里比的是【语义极性】（人判），语用态度另由 pragmatic 层提示，不参与计分。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wanhua  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CASES = ROOT / "tests" / "labeled_cases.json"
HOLDOUT_CASES = ROOT / "tests" / "holdout_cases.json"


def load_cases(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["cases"]


def evaluate(cases: list[dict]) -> dict:
    polarity_total = polarity_hit = status_total = status_hit = 0
    neg_want = neg_hit = neg_pred = 0
    misses: list[dict] = []
    for case in cases:
        got = wanhua.solve(case["text"])
        want_p, want_s = case.get("polarity"), case.get("status")
        if want_p is not None:
            polarity_total += 1
            if want_p == "否定":
                neg_want += 1
                if got["polarity"] == "否定":
                    neg_hit += 1
            if got["polarity"] == "否定":
                neg_pred += 1
            if got["polarity"] == want_p:
                polarity_hit += 1
            else:
                misses.append({"text": case["text"], "field": "polarity",
                               "want": want_p, "got": got["polarity"], "tag": case.get("tag")})
        if want_s is not None:
            status_total += 1
            if got["status"] == want_s:
                status_hit += 1
            else:
                misses.append({"text": case["text"], "field": "status",
                               "want": want_s, "got": got["status"], "tag": case.get("tag")})

    n = len(cases)
    return {
        "cases": n,
        "polarity_accuracy": round(polarity_hit / polarity_total, 4) if polarity_total else 0.0,
        "negative_recall": round(neg_hit / neg_want, 4) if neg_want else 0.0,
        "negative_precision": round(neg_hit / neg_pred, 4) if neg_pred else 0.0,
        "negative_support": neg_want,
        "status_accuracy": round(status_hit / status_total, 4) if status_total else None,
        "misses": misses,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="标注集评估")
    ap.add_argument("--cases", default=str(DEFAULT_CASES))
    ap.add_argument("--holdout", action="store_true", help="改跑 tests/holdout_cases.json（独立编写的盲测集）")
    ap.add_argument("--min-acc", type=float, default=0.80, help="极性准确率下限（labeled 基线 0.84，holdout 基线 0.75）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    path = Path(args.cases)
    if args.holdout:
        path = HOLDOUT_CASES
    if not path.exists():
        print(f"找不到标注集：{path}", file=sys.stderr)
        return 4
    result = evaluate(load_cases(path))

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"用例数：{result['cases']}")
        print(f"极性准确率：{result['polarity_accuracy']:.2%}")
        print(f"否定类召回：{result['negative_recall']:.2%}（{result['negative_support']} 条否定句）")
        print(f"否定类精确：{result['negative_precision']:.2%}")
        if result["status_accuracy"] is not None:
            print(f"状态准确率：{result['status_accuracy']:.2%}")
        if result["misses"]:
            print("错例：")
            for m in result["misses"]:
                print(f"  - [{m['tag']}] {m['text']}  {m['field']}: 期望 {m['want']} / 实得 {m['got']}")
        else:
            print("无错例")

    return 0 if result["polarity_accuracy"] >= args.min_acc else 1


if __name__ == "__main__":
    sys.exit(main())
