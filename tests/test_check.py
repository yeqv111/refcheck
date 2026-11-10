import json
import unittest

from refcheck.check import (
    COV_VERIFIED,
    _judge_claim,
    _judge_ref,
    summarize,
)
from refcheck.client import SearchHit
from refcheck.extract import Claim, Reference
from refcheck.match import VERDICT_DOUBT, VERDICT_MISSING, VERDICT_VERIFIED


def hit(title: str, url: str = "https://zh.zhhlzzs.com/x", site: str = "中华护理杂志",
        passage: str = "", date: str = "2024-01-01", score: float = 0.8) -> SearchHit:
    return SearchHit(title=title, url=url, site=site, date=date, score=score,
                     passage=passage, tier="academic", tier_score=0.9)


def farm_hit(title: str) -> SearchHit:
    return SearchHit(title=title, url="https://www.bhdoctor.com/x", site="博禾医生",
                     date="2024-01-01", score=0.5, passage="", tier="farm", tier_score=0.15)


class TestJudgeRef(unittest.TestCase):
    def test_exact_title_verified(self):
        ref = Reference(raw="", index=1, title="中国高血压防治指南(2024年修订版)")
        r = _judge_ref(ref, [hit("中国高血压防治指南(2024年修订版)")])
        self.assertEqual(r.verdict, VERDICT_VERIFIED)
        self.assertEqual(r.kind, "ref")

    def test_farm_source_downgraded(self):
        ref = Reference(raw="", index=1, title="某某护理研究")
        r = _judge_ref(ref, [farm_hit("某某护理研究")])
        self.assertEqual(r.verdict, VERDICT_DOUBT)
        self.assertIn("无一手出处", r.note)

    def test_no_results(self):
        ref = Reference(raw="", index=1, title="随便一个标题")
        r = _judge_ref(ref, [])
        self.assertEqual(r.verdict, VERDICT_MISSING)
        self.assertFalse(r.false_positive_signal)   # 没结果不算「有结果但对不上」

    def test_misleading_signal(self):
        """返回了 10 条却没有一条对得上 —— 编造内容最典型的形态。"""
        ref = Reference(raw="", index=1, title="黄芪甲苷调控足细胞损伤的机制研究")
        hits = [hit(f"完全无关的第{i}篇文章") for i in range(10)]
        r = _judge_ref(ref, hits)
        self.assertEqual(r.verdict, VERDICT_MISSING)
        self.assertTrue(r.false_positive_signal)


class TestJudgeClaim(unittest.TestCase):
    def test_covered_verified(self):
        claim = Claim(text="缬沙坦适合合并高尿酸血症的患者", index=1,
                      entities=["缬沙坦", "高尿酸血症"], query="缬沙坦 高尿酸血症")
        r = _judge_claim(claim, [hit("缬沙坦在降压同时可促尿酸排泄", passage="缬沙坦 高尿酸血症 适用")])
        self.assertEqual(r.verdict, VERDICT_VERIFIED)
        self.assertGreaterEqual(r.sim, COV_VERIFIED)

    def test_single_entity_not_verified(self):
        """只提到 1 个实体，证据面太窄，最多「弱支撑」。"""
        claim = Claim(text="可联合吲达帕胺", index=1, entities=["吲达帕胺"], query="吲达帕胺")
        r = _judge_claim(claim, [hit("吲达帕胺的降压作用", passage="吲达帕胺 利尿 降压")])
        self.assertEqual(r.verdict, VERDICT_DOUBT)
        self.assertIn("证据面太窄", r.note)

    def test_low_coverage_missing(self):
        claim = Claim(text="某药可治某病", index=1,
                      entities=["缬沙坦", "慢性肾病", "蛋白尿"], query="x")
        r = _judge_claim(claim, [hit("与主题无关的文章", passage="今天天气很好")])
        self.assertEqual(r.verdict, VERDICT_MISSING)


class TestSummary(unittest.TestCase):
    def test_counts(self):
        refs = [
            Reference(raw="", index=1, title="中国高血压防治指南(2024年修订版)"),
            Reference(raw="", index=2, title="围手术期低体温预防的循证护理实践"),
        ]
        results = [
            _judge_ref(refs[0], [hit("中国高血压防治指南(2024年修订版)")]),
            _judge_ref(refs[1], [hit("完全无关文章")]),
        ]
        s = summarize(results)
        self.assertEqual(s.total, 2)
        self.assertEqual(s.verified, 1)
        self.assertEqual(s.missing, 1)
        self.assertAlmostEqual(s.traceable_rate, 50.0)

    def test_display_verdict_for_claim(self):
        claim = Claim(text="缬沙坦适合高尿酸血症", index=1,
                      entities=["缬沙坦", "高尿酸血症"], query="x")
        r = _judge_claim(claim, [hit("缬沙坦 高尿酸血症", passage="缬沙坦 高尿酸血症")])
        self.assertEqual(r.display_verdict, "有出处")
        self.assertEqual(r.sim_label.startswith("覆盖"), True)


if __name__ == "__main__":
    unittest.main()
