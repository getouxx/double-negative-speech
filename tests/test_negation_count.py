#!/usr/bin/env python3
"""negation_count 的回归测试。

运行：
    python3 -m unittest discover -s tests -v

规则改动前先跑一遍，改动后再跑一遍；任何一条变红都说明极性或作用域行为被改坏了。
"""
import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("negation_count", SCRIPTS / "negation_count.py")
nc = importlib.util.module_from_spec(spec)
sys.modules["negation_count"] = nc
spec.loader.exec_module(nc)


class PolarityTests(unittest.TestCase):
    """极性折叠：偶数否定=肯定，奇数=否定。"""

    def test_single_negation_is_negative(self):
        rep = nc.analyze("这个方案不可行")
        self.assertEqual(rep.polarity, "否定")

    def test_double_negation_is_positive(self):
        rep = nc.analyze("不是不该认真一点")
        self.assertEqual(rep.polarity, "肯定")

    def test_triple_negation_is_negative(self):
        rep = nc.analyze("没有理由不承认这不是个办法")
        self.assertEqual(rep.total_weight, 3)
        self.assertEqual(rep.polarity, "否定")

    def test_no_negation(self):
        rep = nc.analyze("今天天气很好")
        self.assertEqual(rep.polarity, "肯定")
        self.assertIn("未发现否定词，本句不在绕弯范畴内", rep.warnings)


class ConstructTests(unittest.TestCase):
    """多字构式内含两次否定，权重必须计 2。"""

    def test_meiyouliyoubu_weighs_two(self):
        rep = nc.analyze("没有理由不收心")
        self.assertEqual(rep.total_weight, 2)
        self.assertEqual(rep.polarity, "肯定")

    def test_budebu_weighs_two(self):
        rep = nc.analyze("不得不承认")
        self.assertEqual(rep.total_weight, 2)
        self.assertEqual(rep.polarity, "肯定")

    def test_wuwei_weighs_two(self):
        rep = nc.analyze("未尝不可")
        self.assertEqual(rep.total_weight, 2)

    def test_meiyouliyoubu_not_double_counted(self):
        """『没有理由不』整体记 2，不能拆成『没有』1 + 『不』1 再叠加顺序错误。"""
        rep = nc.analyze("没有理由不")
        self.assertEqual(len(rep.negations), 1)
        self.assertEqual(rep.negations[0].token, "没有理由不")
        self.assertEqual(rep.negations[0].weight, 2)


class LexicalNegationTests(unittest.TestCase):
    """词汇化否定：字形不含『不』也要计入。"""

    def test_nanmian_counted(self):
        rep = nc.analyze("难免有些遗憾")
        self.assertEqual(rep.total_weight, 1)

    def test_weibi_counted(self):
        rep = nc.analyze("他未必知道")
        self.assertEqual(rep.total_weight, 1)
        self.assertEqual(rep.polarity, "否定")

    def test_quexao_counted(self):
        rep = nc.analyze("缺乏证据")
        self.assertEqual(rep.total_weight, 1)

    def test_lexical_warning_emitted(self):
        rep = nc.analyze("这种情况难以避免")
        self.assertTrue(any("词汇化否定" in w for w in rep.warnings))


class AmbiguityTests(unittest.TestCase):
    """易歧义结构必须被标出来，而不是当成普通否定计数。"""

    def test_chadianmei_flagged(self):
        rep = nc.analyze("差点没赶上")
        self.assertTrue(any("差点没" in a for a in rep.ambiguities))

    def test_haobu_flagged(self):
        rep = nc.analyze("好不热闹")
        self.assertTrue(any("好不" in a for a in rep.ambiguities))

    def test_ambiguous_not_counted_into_depth(self):
        rep = nc.analyze("差点没赶上")
        self.assertFalse(any("难以稳定解码" in w for w in rep.warnings))

    def test_scope_ambiguity_flagged(self):
        rep = nc.analyze("不想不安装在脑子里的知识")
        self.assertTrue(any("作用域可能归属不同" in a for a in rep.ambiguities))


class QuantifierTests(unittest.TestCase):
    """否定 + 全称词 → 可能降成特称否定。"""

    def test_quantifier_trap_flagged(self):
        rep = nc.analyze("不是所有人都没有意见")
        self.assertTrue(any("特称否定" in a for a in rep.ambiguities))

    def test_yidian_trap_flagged(self):
        rep = nc.analyze("不是一点都没有")
        self.assertTrue(any("特称否定" in a for a in rep.ambiguities))

    def test_yidian_as_degree_not_flagged(self):
        """『认真一点』里的『一点』是程度补语，不是全称词，不能误报。"""
        rep = nc.analyze("不是不该认真一点")
        self.assertFalse(any("特称否定" in a for a in rep.ambiguities))


class ScopeTests(unittest.TestCase):
    """作用域浅层边界：至少给出非空、限定在本小句内的片段。"""

    def test_scope_non_empty(self):
        rep = nc.analyze("这件事我不能不管，但也不想全管")
        for n in rep.negations:
            self.assertTrue(n.scope)

    def test_scope_limited_to_clause(self):
        rep = nc.analyze("我不想去，他说没关系")
        first = rep.negations[0]
        self.assertNotIn("他说没关系", first.scope)

    def test_clauses_split(self):
        rep = nc.analyze("不是不该改，只是时机未到")
        self.assertGreaterEqual(len(rep.clauses), 2)


class FalsePositiveTests(unittest.TestCase):
    """含否定字形但不表否定的词必须跳过。"""

    def test_feichang_skipped(self):
        rep = nc.analyze("非常无聊的一天")
        self.assertEqual(rep.total_weight, 0)

    def test_bieren_skipped(self):
        rep = nc.analyze("别人怎么想")
        self.assertEqual(rep.total_weight, 0)

    def test_buguan_skipped(self):
        rep = nc.analyze("不管怎样")
        self.assertEqual(rep.total_weight, 0)


class InterfaceTests(unittest.TestCase):
    """CLI 契约：JSON 字段齐全，歧义模式只输出风险。"""

    def test_json_fields(self):
        rep = nc.analyze("不能不说是好事")
        data = nc.json.loads(nc.to_json(rep))
        for key in ("text", "negations", "total_weight", "polarity", "clauses",
                    "ambiguities", "warnings"):
            self.assertIn(key, data)
        self.assertEqual(data["total_weight"], 2)

    def test_cli_ambiguity_mode(self):
        import contextlib
        import io

        with contextlib.redirect_stdout(io.StringIO()) as buf:
            code = nc.main(["--ambiguity", "差点没赶上"])
        self.assertEqual(code, 0)
        self.assertIn("差点没", buf.getvalue())


class FailureCaseTests(unittest.TestCase):
    """failure_cases.md 里已修正的案例，在这里落成回归用例。"""

    def test_fc04_four_layers_flagged(self):
        """FC-04：四层否定必须报警，不能假装可解。"""
        rep = nc.analyze("未必不是不可能不记")
        self.assertTrue(any("超过 3 层" in w for w in rep.warnings))

    def test_fc09_wanquan_flagged(self):
        """FC-09：『不能完全不同意』的『完全』要按全称词降级提示。"""
        rep = nc.analyze("不能完全不同意")
        self.assertTrue(any("特称否定" in a for a in rep.ambiguities))

    def test_fc12_weibi_combo(self):
        """FC-12：『未必』+『不』两层折叠后为肯定，漏掉『未必』就判反。"""
        rep = nc.analyze("他未必不知道")
        self.assertEqual(rep.total_weight, 2)
        self.assertEqual(rep.polarity, "肯定")

    def test_fc15_nanmianbu_flagged(self):
        """FC-15：『难免不』属歧义高频区，只提示不硬判。"""
        rep = nc.analyze("难免不被人说")
        self.assertTrue(any("难免不" in a for a in rep.ambiguities))

    def test_fc16_triple_scope_flagged(self):
        """FC-16：三层否定且作用域交叉，必须报作用域分歧。"""
        rep = nc.analyze("不是不想不再这么下去")
        self.assertEqual(rep.total_weight, 3)
        self.assertTrue(any("作用域可能归属不同" in a for a in rep.ambiguities))


if __name__ == "__main__":
    unittest.main()
