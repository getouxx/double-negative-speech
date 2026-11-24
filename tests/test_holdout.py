#!/usr/bin/env python3
"""hold-out 盲测：独立编写的 60 条句子，专门回答「没被规则覆盖过的句子准不准」。

这与 labeled_cases 的分工：
  labeled_cases  规则回归（写了规则就该过），错了说明规则被改坏
  holdout_cases  盲测（没参照规则编写），错了说明规则覆盖不到
"""
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

import evaluate  # noqa: E402

HOLDOUT = HERE / "holdout_cases.json"

# 盲测错例只允许落在这几类已知盲区；跑出新类别就说明覆盖声明需要更新
KNOWN_BLIND_SPOTS = {"lexical-limit", "special-limit", "single"}


class HoldoutTests(unittest.TestCase):
    def setUp(self):
        self.cases = evaluate.load_cases(HOLDOUT)
        self.result = evaluate.evaluate(self.cases)

    def test_size_at_least_fifty(self):
        self.assertGreaterEqual(len(self.cases), 50)

    def test_accuracy_floor(self):
        self.assertGreaterEqual(self.result["polarity_accuracy"], 0.75)

    def test_negative_recall_floor(self):
        self.assertGreaterEqual(self.result["negative_recall"], 0.85)

    def test_misses_stay_in_known_blind_spots(self):
        for miss in self.result["misses"]:
            self.assertIn(miss["tag"], KNOWN_BLIND_SPOTS,
                          f"盲测出现新错例类型 {miss['tag']}：{miss['text']}")


if __name__ == "__main__":
    unittest.main()
