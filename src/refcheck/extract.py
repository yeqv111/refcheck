"""从自由文本里抽取"可核查单元"。

两种输入：
  1. 参考文献列表（AI 帮你写报告时给的那种）
  2. 医学问答正文（AI 给你的用药建议）

没有用分词库（零依赖），走的是「格式规则 + 后缀词表」的路子。

关键区分：对"陈述"类内容，实体（药名/指标/疾病）才是检索与判定的依据，
断言词（建议、慎用、需）只用来判断这句话值不值得查。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------- 参考文献 ----------

REF_LINE = re.compile(r"^\s*(?:\[(\d+)\]\s*)?(.+?)\s*$")

GB_T = re.compile(
    r"^(?P<authors>[^.]*)\.\s*(?P<title>[^[]+?)\s*\[(?P<kind>[A-Z])\]\.\s*"
    r"(?P<journal>[^,，]*)[,，]\s*(?P<year>\d{4})"
    r"(?:[,，]\s*(?P<volume>\d+)\s*(?:\((?P<issue>[^)]*)\))?)?"
    r"(?::\s*(?P<pages>[\d\-–—]+))?"
)

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


@dataclass
class Reference:
    raw: str
    index: int
    title: str
    journal: str = ""
    year: str = ""
    authors: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""

    @property
    def query(self) -> str:
        """只用标题检索。

        实测：把期刊名和年份一起拼进去，会把召回拉低（2001 年的中文文献
        本来就少，多两个限定词直接把知网结果挤掉了）。
        """
        return self.title[:60]

    @property
    def full_query(self) -> str:
        """带期刊与年份的完整检索词，仅在需要收窄时使用。"""
        parts = [self.title, self.journal, self.year]
        return " ".join(p for p in parts if p)

    @property
    def label(self) -> str:
        return self.title if len(self.title) <= 40 else self.title[:40] + "…"


def _clean_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^[\[（(]?\d+[\]）).、]\s*", "", line)
    line = re.sub(r"^[" + CIRCLED + r"]\s*", "", line)
    line = re.sub(r"^[-*•]\s*", "", line)
    return line.strip()


def parse_references(text: str) -> list[Reference]:
    refs: list[Reference] = []
    for raw in text.splitlines():
        line = _clean_line(raw)
        if len(line) < 8 or re.fullmatch(r"参考文献[:：]?", line):
            continue

        m = GB_T.match(line)
        if m:
            refs.append(
                Reference(
                    raw=raw.strip(),
                    index=len(refs) + 1,
                    title=m.group("title").strip(" .。"),
                    journal=(m.group("journal") or "").strip(),
                    year=m.group("year") or "",
                    authors=(m.group("authors") or "").strip(),
                    volume=m.group("volume") or "",
                    issue=m.group("issue") or "",
                    pages=m.group("pages") or "",
                )
            )
            continue

        m2 = re.search(r"(?P<title>[^\[\]。]{6,80})\s*\[(?P<kind>[A-Z])\]", line)
        title = m2.group("title").strip() if m2 else line
        year_m = re.search(r"(19|20)\d{2}", line)
        refs.append(
            Reference(
                raw=raw.strip(),
                index=len(refs) + 1,
                title=re.sub(r"^[^.]*\.\s*", "", title)[:90],
                year=year_m.group(0) if year_m else "",
            )
        )
    return refs


# ---------- 医学陈述 ----------

SENT_SPLIT = re.compile(r"[。！？；\n]+")

DRUG_SUFFIX = (
    "地平", "沙坦", "洛尔", "普利", "嗪", "他汀", "霉素", "西林", "头孢",
    "沙星", "唑", "帕胺", "列汀", "列净", "格列", "胰岛素", "肝素",
    "胶囊", "片剂", "注射液", "缓释片", "喷雾剂",
)

METRIC_WORDS = (
    "血压", "尿酸", "肌酐", "血钾", "血钠", "血糖", "血脂", "心率",
    "蛋白尿", "转氨酶", "白细胞", "肾功能", "肝功能", "肾小球滤过率",
    "eGFR", "GFR", "血红蛋白", "血尿酸", "电解质",
)

# 药物类别：本身也是可检索实体（「噻嗪类利尿剂」比单说「利尿剂」更准）
DRUG_CLASS = (
    "二氢吡啶类钙通道阻滞剂", "钙通道阻滞剂", "血管紧张素Ⅱ受体拮抗剂",
    "血管紧张素转换酶抑制剂", "噻嗪类利尿剂", "噻嗪类", "袢利尿剂", "利尿剂",
    "β受体阻滞剂", "ACEI", "ARB", "CCB", "二氢吡啶类", "保钾利尿剂",
)

DISEASE_WORDS = (
    "高血压", "糖尿病", "肾病", "糖尿病肾病", "冠心病", "心衰", "心力衰竭",
    "痛风", "高尿酸血症", "脑卒中", "动脉粥样硬化", "慢性肾病", "肾病综合征",
)

ASSERT_WORDS = (
    "禁用", "慎用", "不宜", "避免", "推荐", "首选", "建议", "应", "需",
    "必须", "可换用", "相互作用", "不良反应", "禁忌", "监测", "剂量",
    "适应证", "疗效", "优于", "降低", "升高", "导致", "增加", "减少",
)

# 用于 query 的通用词，噪声大，不放进检索词
_SKIP_IN_QUERY = set(ASSERT_WORDS) | {"患者", "医生", "用药", "治疗"}


# 药名前面常粘着动词，切掉它们才拿得到真药名
_DRUG_VERB_PREFIX = (
    "建议", "推荐", "可以", "可", "应该", "应", "需要", "需", "必须", "避免",
    "不宜", "停止", "停用", "使用", "换用", "服用", "加用", "联用", "改用",
    "继续", "长期", "小剂量", "大剂量", "如", "用",
)
_DRUG_SUFFIX_SET = set(DRUG_SUFFIX)


# 药名之间常有连接词，匹配时容易跨词：'沙坦或吲达帕胺' 应切成 '吲达帕胺'
_DRUG_CONJ = ("或者", "或", "和", "与", "及", "、", "加用", "合用", "联用", "，", ",")


def _clean_drug(word: str) -> str:
    for c in _DRUG_CONJ:
        if c in word:
            word = word.split(c)[-1]
    w = word
    changed = True
    while changed:
        changed = False
        for p in _DRUG_VERB_PREFIX:
            if w.startswith(p) and len(w) - len(p) >= 2:
                w = w[len(p):]
                changed = True
    return w


def extract_drugs(text: str) -> list[str]:
    """抽药名。注意「缬沙坦」只有 3 字，所以前缀长度从 1 起步。"""
    found: list[str] = []
    for suf in DRUG_SUFFIX:
        for m in re.finditer(r"[\u4e00-\u9fa5]{1,5}" + re.escape(suf), text):
            w = _clean_drug(m.group(0))
            if w in _DRUG_SUFFIX_SET or len(w) < 3:
                continue
            found.append(w)
    return list(dict.fromkeys(found))


def extract_entities(sentence: str) -> list[str]:
    """只抽实体：药名、指标、疾病。"""
    found: list[str] = []
    found.extend(extract_drugs(sentence))
    for w in METRIC_WORDS + DISEASE_WORDS + DRUG_CLASS:
        if w in sentence:
            found.append(w)
    # 去掉被更长实体包含的短词（"尿酸" vs "血尿酸"）
    uniq = list(dict.fromkeys(found))
    return [w for w in uniq if not any(w != o and w in o for o in uniq)]


@dataclass
class Claim:
    text: str
    index: int
    query: str = ""
    entities: list[str] = field(default_factory=list)
    has_assertion: bool = False

    @property
    def label(self) -> str:
        t = self.text.strip()
        return t if len(t) <= 52 else t[:52] + "…"


def build_query(entities: list[str], sentence: str, fallback_drug: str = "",
                has_drug: bool = True) -> str:
    """检索词 = 实体组合。句子里没有药时，补全文主药名做上下文。"""
    parts = [e for e in entities if e not in _SKIP_IN_QUERY]
    if not has_drug and fallback_drug and fallback_drug not in parts:
        parts.append(fallback_drug)
    if not parts:
        return sentence.strip()[:26]
    return " ".join(parts[:5])


def parse_claims(text: str, min_len: int = 12) -> list[Claim]:
    """把一段医学回答拆成一条条可核查的陈述。"""
    # 全文主药名：给没有主语的句子补上下文
    drugs = extract_drugs(text)
    main_drug = drugs[0] if drugs else ""

    claims: list[Claim] = []
    for chunk in SENT_SPLIT.split(text):
        s = re.sub(r"^\d+[.、)]\s*", "", chunk.strip(" \t　"))
        if len(s) < min_len:
            continue
        entities = extract_entities(s)
        has_assert = any(w in s for w in ASSERT_WORDS)
        if not entities:
            continue
        has_drug = bool(extract_drugs(s)) or any(c in s for c in DRUG_CLASS)
        claims.append(
            Claim(
                text=s,
                index=len(claims) + 1,
                query=build_query(entities, s, main_drug, has_drug),
                entities=entities,
                has_assertion=has_assert,
            )
        )
    return claims
