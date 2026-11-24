#!/usr/bin/env python3
"""标注集准确率回归：低于基线就红，防止规则改动悄悄掉点。

基线（v1.2.0，33 条语义标注）：
    极性准确率 84.38%（词汇化否定/特殊形式/复杂辖域的已知漏判如实保留）
    状态准确率 100%（规则层总能标出该标的风险）
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import evaluate  # noqa: E402

POLARITY_FLOOR = 0.80
STATUS_FLOOR = 0.90


class AccuracyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = evaluate.evaluate(evaluate.load_cases(HERE / "labeled_cases.json"))

    def test_polarity_accuracy_floor(self):
        self.assertGreaterEqual(self.result["polarity_accuracy"], POLARITY_FLOOR,
                                msg=f"极性准确率掉到 {self.result['polarity_accuracy']}，错例：{self.result['misses']}")

    def test_status_accuracy_floor(self):
        self.assertGreaterEqual(self.result["status_accuracy"], STATUS_FLOOR)

    def test_known_limits_are_documented(self):
        """已知漏判必须仍出现在错例里；哪天消失了说明规则改好了，回来更新基线。"""
        tags = {m["tag"] for m in self.result["misses"] if m["field"] == "polarity"}
        self.assertTrue(any(t.endswith("limitation") for t in tags))
        self.assertLessEqual(len(tags), 6)


if __name__ == "__main__":
    unittest.main()
