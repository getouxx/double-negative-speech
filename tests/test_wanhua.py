#!/usr/bin/env python3
"""wanhua.check 的回归测试：规则层歧义 vs 语用层提示。

对应 references/failure_cases.md 的回归用例编号（FC-xx），
规则改动后这些用例必须仍全绿。
"""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import wanhua  # noqa: E402


class CleanSentenceTests(unittest.TestCase):
    def test_fc_p1_clean_sentence_passes(self):
        """FC-P1：极性干净、无常见语用陷阱的句子应 pass。"""
        res = wanhua.check("要说再这么下去还算在做事，恐怕没几个人不觉得勉强")
        self.assertTrue(res["pass"])
        self.assertEqual(res["risks"], [])
        self.assertEqual(res["pragmatic"], [])


class PragmaticTests(unittest.TestCase):
    def test_fc_p2_soft_refusal(self):
        """FC-P2：『不是不能商量』规则层唯一（肯定），语用上常被读成委婉拒绝。"""
        res = wanhua.check("这件事不是不能商量")
        self.assertEqual(res["polarity"], "肯定")
        self.assertEqual(res["risks"], [])
        self.assertFalse(res["pass"])
        self.assertEqual([p["type"] for p in res["pragmatic"]], ["soft-refusal"])
        self.assertEqual(res["pragmatic"][0]["evidence"], "不是不能")

    def test_fc_p3_bushibugai_not_soft_refusal(self):
        """FC-P3：『不是不该认真一点』不是表态拒绝，不能误报委婉软化。"""
        res = wanhua.check("不是不该认真一点")
        self.assertTrue(res["pass"])
        self.assertEqual(res["pragmatic"], [])

    def test_fc_p4_sarcasm(self):
        """FC-P4：『可真是没让我失望』字面否定，口语里是反讽。"""
        res = wanhua.check("你可真是没让我失望")
        self.assertIn("sarcasm", [p["type"] for p in res["pragmatic"]])
        self.assertFalse(res["pass"])

    def test_fc_p5_rhetorical(self):
        """FC-P5：反问句字面极性会被翻转，规则层虽唯一也要提示。"""
        res = wanhua.check("难道这不叫负责吗")
        self.assertEqual(res["polarity"], "否定")
        self.assertIn("rhetorical", [p["type"] for p in res["pragmatic"]])

    def test_fc_p6_sarcasm_needs_negation(self):
        """『真是够努力』没有否定词，不构成反讽，不能误报。"""
        res = wanhua.check("他真是够努力的")
        self.assertEqual(res["pragmatic"], [])


class RuleLayerTests(unittest.TestCase):
    def test_fc_p7_rule_layer_risk_blocks_pass(self):
        """FC-P7：规则层歧义（差点没）优先级高于语用提示，pass 必须为 False。"""
        res = wanhua.check("差点没赶上")
        self.assertFalse(res["pass"])
        self.assertTrue(any("差点没" in r for r in res["risks"]))
        self.assertIn("规则层", res["note"])

    def test_p8_fields(self):
        """字段契约：下游取字段不应 KeyError。"""
        res = wanhua.check("不是不该改")
        for key in ("text", "polarity", "weight", "pass", "risks",
                    "warnings", "pragmatic", "note"):
            self.assertIn(key, res)

    def test_p9_cli_json(self):
        """check 子命令输出可解析 JSON，且退出码为 0（便于管道）。"""
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            code = wanhua.main(["check", "这件事不是不能商量"])
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["pragmatic"][0]["type"], "soft-refusal")


class CompareTests(unittest.TestCase):
    def test_p10_compare_polarity(self):
        """折叠验证：绕句与原句极性一致。"""
        res = wanhua.compare("不是不该改", "该改")
        self.assertTrue(res["same_polarity"])

    def test_p11_compare_mismatch(self):
        """极性相反时必须判定回译失败。"""
        res = wanhua.compare("不该改", "该改")
        self.assertFalse(res["same_polarity"])


if __name__ == "__main__":
    unittest.main()
