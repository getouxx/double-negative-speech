#!/usr/bin/env python3
"""Skill 契约测试：状态语义、退出码、输入防御、可解释字段。

这些用例锁的是"宿主 Agent 能不能稳定调用"这件事，不是语言正确性。
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
import negation_count as nc  # noqa: E402


def run_cli(argv):
    """跑 CLI，返回 (exit_code, stdout, stderr)。"""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = wanhua.main(argv)
    return code, out.getvalue(), err.getvalue()


class ContractFieldTests(unittest.TestCase):
    def test_fields_are_stable(self):
        res = wanhua.solve("不是不该改")
        for key in ("skill", "version", "mode", "input_text", "status", "certainty",
                    "rules_version", "polarity", "confidence", "rules", "scope",
                    "pragmatic_hint", "explain", "next_step"):
            self.assertIn(key, res)

    def test_confidence_bounds(self):
        for text in ("不是不该改", "差点没赶上", "今天天气很好"):
            res = wanhua.solve(text)
            self.assertGreaterEqual(res["confidence"], 0.0)
            self.assertLessEqual(res["confidence"], 1.0)

    def test_rules_are_traceable(self):
        res = wanhua.solve("差点没赶上")
        self.assertTrue(res["rules"])
        for rule in res["rules"]:
            self.assertRegex(rule["id"], r"^R-[A-Z]+$")
            self.assertTrue(rule["note"])

    def test_pragmatic_is_labelled_heuristic(self):
        res = wanhua.solve("这件事不是不能商量")
        hint = res["pragmatic_hint"]
        self.assertTrue(hint["heuristic"])
        self.assertFalse(hint["affects_polarity"])
        self.assertIn("有限覆盖", hint["coverage"])


class StatusTests(unittest.TestCase):
    def test_ok(self):
        res = wanhua.solve("不是不该改")
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["polarity"], "肯定")

    def test_ambiguous(self):
        res = wanhua.solve("差点没赶上")
        self.assertEqual(res["status"], "ambiguous")
        self.assertIn("R-SPECIAL", [r["id"] for r in res["rules"]])

    def test_unknown_when_no_negation(self):
        res = wanhua.solve("今天天气很好")
        self.assertEqual(res["status"], "unknown")
        self.assertIsNone(res["polarity"])
        self.assertEqual(res["confidence"], 0.0)


class InputGuardTests(unittest.TestCase):
    def test_empty_input(self):
        code, out, err = run_cli(["solve", ""])
        self.assertEqual(code, wanhua.EXIT_INPUT_ERROR)
        self.assertIn('"status": "error"', out)

    def test_too_long_input(self):
        text = "不" * (nc.MAX_INPUT_CHARS + 1)
        res = wanhua.solve(text)
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["polarity"], None)

    def _run_nc(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = nc.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_negation_count_empty_goes_to_stderr(self):
        code, out, err = self._run_nc([])
        self.assertEqual(code, 4)
        self.assertIn("空输入", err)
        self.assertEqual(out.strip(), "")

    def test_negation_count_too_long(self):
        code, out, err = self._run_nc(["不" * (nc.MAX_INPUT_CHARS + 1)])
        self.assertEqual(code, 4)
        self.assertIn("输入过长", err)

    def test_mixed_script_and_punctuation(self):
        res = wanhua.solve("这个 plan 不可行！！")
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["polarity"], "否定")


class ExitCodeTests(unittest.TestCase):
    def test_ok_exit_zero(self):
        code, out, _ = run_cli(["solve", "不是不该改"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["status"], "ok")

    def test_ambiguous_exit_three(self):
        code, out, _ = run_cli(["solve", "差点没赶上"])
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(out)["status"], "ambiguous")

    def test_solve_without_text(self):
        code, out, err = run_cli(["solve"])
        self.assertEqual(code, wanhua.EXIT_INPUT_ERROR)
        self.assertIn("需要一句文本", err)


class CertaintyTierTests(unittest.TestCase):
    """分层兜底：certain / uncertain / out_of_scope 三档，不许硬判。"""

    def test_certain_on_clean_sentence(self):
        res = wanhua.solve("不是不该改")
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["certainty"], "certain")
        self.assertEqual(res["polarity"], "肯定")

    def test_uncertain_keeps_polarity_but_flags(self):
        res = wanhua.solve("差点没赶上")
        self.assertEqual(res["status"], "ambiguous")
        self.assertEqual(res["certainty"], "uncertain")
        self.assertTrue(res["rules"])

    def test_rhetorical_is_out_of_scope_not_guessed(self):
        res = wanhua.solve("难道这不叫负责吗？")
        self.assertEqual(res["status"], "out_of_scope")
        self.assertEqual(res["certainty"], "out_of_scope")
        self.assertIsNone(res["polarity"])
        self.assertIsNone(res["confidence"])
        self.assertIn("人工复核", res["next_step"])

    def test_unknown_without_pragmatic_stays_unknown(self):
        res = wanhua.solve("会议改到下周了")
        self.assertEqual(res["status"], "unknown")
        self.assertIsNone(res["polarity"])

    def test_out_of_scope_exit_three(self):
        code, out, _ = run_cli(["solve", "难道这不叫负责吗？"])
        self.assertEqual(code, wanhua.EXIT_NEEDS_CONTEXT)
        self.assertEqual(json.loads(out)["status"], "out_of_scope")


class RuleProvenanceTests(unittest.TestCase):
    """可解释：命中的规则、规则冲突、规则库版本都要暴露出来。"""

    def test_check_exposes_matched_rules(self):
        res = wanhua.check("不是不该改")
        self.assertIn("matched_rules", res)
        self.assertIn("conflicts", res)
        self.assertEqual(res["certainty"], "certain")

    def test_conflict_detected(self):
        res = wanhua.check("差点没让人难免不生气")
        self.assertEqual(len(res["conflicts"]), 1)
        self.assertEqual(sorted(res["conflicts"][0]["rules"]), ["R-LEXICAL", "R-SPECIAL"])
        self.assertFalse(res["pass"])

    def test_rules_version_present(self):
        res = wanhua.solve("不是不该改")
        self.assertEqual(res["rules_version"], nc.RULES_VERSION)
        self.assertEqual(res["version"], wanhua.__version__)


if __name__ == "__main__":
    unittest.main()
