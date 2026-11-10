import unittest

from refcheck.extract import (
    build_query,
    extract_drugs,
    extract_entities,
    parse_claims,
    parse_references,
)


class TestParseReferences(unittest.TestCase):
    def test_gbt_format(self):
        text = "[1] 中华医学会心血管病学分会. 中国高血压防治指南(2024年修订版)[J]. 中华心血管病杂志, 2024, 52(3): 195-258."
        refs = parse_references(text)
        self.assertEqual(len(refs), 1)
        r = refs[0]
        self.assertEqual(r.title, "中国高血压防治指南(2024年修订版)")
        self.assertEqual(r.journal, "中华心血管病杂志")
        self.assertEqual(r.year, "2024")
        self.assertEqual(r.volume, "52")
        self.assertEqual(r.issue, "3")
        self.assertEqual(r.pages, "195-258")

    def test_skip_header(self):
        refs = parse_references("参考文献：\n张三. 某研究[J]. 某刊, 2023, 1(2): 3-4.")
        self.assertEqual(len(refs), 1)

    def test_bullet_and_circled(self):
        text = "① 张三. 甲研究[J]. 护理杂志, 2022, 10(1): 1-2.\n- 李四. 乙研究[J]. 医学杂志, 2021, 5(2): 3-4."
        refs = parse_references(text)
        self.assertEqual(len(refs), 2)
        self.assertEqual(refs[0].title, "甲研究")
        self.assertEqual(refs[1].title, "乙研究")

    def test_query_is_title_only(self):
        """检索只用标题：带上期刊和年份会稀释召回（实测）。"""
        r = parse_references("张三. 甲研究[J]. 护理杂志, 2022, 10(1): 1-2.")[0]
        self.assertEqual(r.query, "甲研究")
        self.assertIn("护理杂志", r.full_query)


class TestDrugExtraction(unittest.TestCase):
    def test_three_char_drug(self):
        # 缬沙坦只有 3 个字，早期实现会漏
        self.assertIn("缬沙坦", extract_drugs("可用缬沙坦降压"))

    def test_strip_verb_prefix(self):
        # 不能把「建议停用地平」当成药名
        drugs = extract_drugs("建议停用地平类药物")
        self.assertNotIn("建议停用地平", drugs)
        self.assertNotIn("地平", drugs)

    def test_multiple_drugs(self):
        drugs = extract_drugs("可用缬沙坦或吲达帕胺")
        self.assertIn("缬沙坦", drugs)
        self.assertIn("吲达帕胺", drugs)


class TestEntities(unittest.TestCase):
    def test_metric_and_disease(self):
        ents = extract_entities("高血压患者血尿酸升高")
        self.assertIn("高血压", ents)
        self.assertIn("血尿酸", ents)

    def test_drug_class(self):
        ents = extract_entities("避免使用噻嗪类利尿剂")
        self.assertIn("噻嗪类利尿剂", ents)


class TestBuildQuery(unittest.TestCase):
    def test_adds_context_drug_when_missing(self):
        q = build_query(["血钾", "肾功能"], "需要监测血钾和肾功能", "缬沙坦", has_drug=False)
        self.assertIn("血钾", q)
        self.assertIn("缬沙坦", q)

    def test_no_context_when_drug_present(self):
        q = build_query(["血尿酸", "噻嗪类利尿剂"], "噻嗪类利尿剂升高血尿酸", "缬沙坦", has_drug=True)
        self.assertNotIn("缬沙坦", q)


class TestParseClaims(unittest.TestCase):
    def test_split_and_filter(self):
        text = (
            "患者对地平类过敏，可换用缬沙坦。"
            "注意休息。"
            "用药期间需监测血钾和肾功能。"
        )
        claims = parse_claims(text)
        self.assertEqual(len(claims), 2)          # "注意休息" 没有实体，应被过滤
        self.assertIn("缬沙坦", claims[0].entities)
        self.assertIn("血钾", claims[1].entities)

    def test_index_continuous(self):
        claims = parse_claims("缬沙坦在降压的同时可以促进尿酸排泄。吲达帕胺属于利尿剂，会升高血尿酸。")
        self.assertEqual([c.index for c in claims], [1, 2])


if __name__ == "__main__":
    unittest.main()
