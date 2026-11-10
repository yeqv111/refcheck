import unittest

from refcheck.authority import classify
from refcheck.match import (
    VERDICT_DOUBT,
    VERDICT_MISSING,
    VERDICT_VERIFIED,
    best_match,
    normalize,
    passage_supports,
    similarity,
    verdict_for,
)


class TestSimilarity(unittest.TestCase):
    def test_identical(self):
        self.assertAlmostEqual(similarity("中国高血压防治指南", "中国高血压防治指南"), 1.0)

    def test_partial(self):
        s = similarity(
            "中国高血压防治指南(2024年修订版)",
            "《中国高血压防治指南(2024年修订版)》正式发布",
        )
        self.assertGreater(s, 0.7)

    def test_unrelated(self):
        s = similarity(
            "黄芪甲苷调控足细胞损伤的机制研究",
            "高血压患者的日常饮食建议",
        )
        self.assertLess(s, 0.3)

    def test_normalize_strips_punct(self):
        self.assertEqual(normalize("《指南》，2024"), "指南2024")


class TestPassageSupports(unittest.TestCase):
    def test_hit(self):
        self.assertTrue(
            passage_supports(
                "中国高血压防治指南(2024年修订版)",
                "近日，《中国高血压防治指南(2024年修订版)》正式发布……",
            )
        )

    def test_miss(self):
        self.assertFalse(passage_supports("完全不存在的一篇文献标题", "本文讨论高血压的用药"))

    def test_short_target_rejected(self):
        self.assertFalse(passage_supports("短标题", "短标题出现在正文里"))


class TestVerdict(unittest.TestCase):
    def test_verified_needs_strong_source(self):
        self.assertEqual(verdict_for(0.9, "academic"), VERDICT_VERIFIED)
        self.assertEqual(verdict_for(0.9, "official"), VERDICT_VERIFIED)

    def test_farm_never_verified(self):
        # 内容聚合站即使标题完全一致，也不能判「已核实」
        self.assertEqual(verdict_for(1.0, "farm"), VERDICT_DOUBT)

    def test_baike_never_verified(self):
        self.assertEqual(verdict_for(1.0, "ugc"), VERDICT_DOUBT)

    def test_low_sim_missing(self):
        self.assertEqual(verdict_for(0.2, "academic"), VERDICT_MISSING)


class TestBestMatch(unittest.TestCase):
    def test_picks_highest(self):
        results = [
            {"title": "完全无关的文章", "url": "https://a.com", "passage": ""},
            {"title": "中国高血压防治指南(2024年修订版)", "url": "https://b.com", "passage": ""},
        ]
        best = best_match("中国高血压防治指南(2024年修订版)", results)
        self.assertEqual(best["url"], "https://b.com")
        self.assertGreater(best["_sim"], 0.9)

    def test_passage_evidence_marks(self):
        results = [
            {"title": "一篇标题不像的文章", "url": "https://c.com",
             "passage": "《中国高血压防治指南(2024年修订版)》正式发布，提出新的降压目标"},
        ]
        best = best_match("中国高血压防治指南(2024年修订版)", results)
        self.assertEqual(best["_ev"], "passage")
        self.assertGreaterEqual(best["_sim"], 0.85)

    def test_empty(self):
        self.assertIsNone(best_match("x", []))


class TestAuthority(unittest.TestCase):
    def test_gov(self):
        self.assertEqual(classify("https://www.nhc.gov.cn/a", "国家卫健委")[0], "official")

    def test_academic_subdomain(self):
        # zh.zhhlzzs.com 是中华护理杂志官网，早期实现漏了子域名
        tier, _ = classify("https://zh.zhhlzzs.com/CN/10.3761/x", "中华护理杂志")
        self.assertEqual(tier, "academic")

    def test_baike(self):
        self.assertEqual(classify("https://baike.baidu.com/item/x", "百度百科")[0], "ugc")

    def test_farm(self):
        self.assertEqual(classify("https://www.bhdoctor.com/x", "博禾医生")[0], "farm")

    def test_edu(self):
        self.assertEqual(classify("http://jnmu.njmu.edu.cn/zr/x", "南医大")[0], "academic")


if __name__ == "__main__":
    unittest.main()
