"""文本相似度与核查判定。

为什么判定不看"有没有返回结果"？
—— 实测发现：一条编造的文献照样能返回 10 条结果，因为搜索引擎会把"主题相近"
   的内容给你。所以判据必须是「标题像不像」+「正文有没有原话」+「来源硬不硬」。

为什么不看 score 的绝对值？
—— 官方文档写 score 取值 0~1，实测同一 query 两次调用分别返回 0.777 与 3.832，
   量级不稳定，只能当排序参考，不能当固定阈值。
"""

from __future__ import annotations

import re

PUNCT = re.compile(
    r"[\s\u3000，。、；：？！“”‘’（）《》〈〉【】\[\]「」·,.;:?!\"'()<>\-—_/\\|~`@#$%^&*+=]+"
)

VERDICT_VERIFIED = "已核实"
VERDICT_DOUBT = "存疑"
VERDICT_MISSING = "查无出处"

# 阈值：实测真文献 best_sim 多在 0.6 以上，编造文献多在 0.4 以下
SIM_VERIFIED = 0.62
SIM_DOUBT = 0.34

# 正文命中标题原文时给的相似度（比标题比对更硬的证据）
PASSAGE_HIT = 0.88

# 这两档来源不能单独支撑"已核实"
WEAK_TIERS = ("farm", "ugc")


def normalize(text: str) -> str:
    return PUNCT.sub("", (text or "").lower())


def bigrams(text: str) -> set[str]:
    s = normalize(text)
    if len(s) < 2:
        return {s} if s else set()
    return {s[i : i + 2] for i in range(len(s) - 1)}


def similarity(a: str, b: str) -> float:
    """字符 2-gram Jaccard，对中文短标题较稳。"""
    ba, bb = bigrams(a), bigrams(b)
    if not ba or not bb:
        return 0.0
    inter = len(ba & bb)
    union = len(ba | bb)
    jaccard = inter / union if union else 0.0
    recall = inter / len(ba)
    return max(jaccard, recall * 0.92)


def passage_supports(target: str, passage: str, probe_len: int = 14) -> bool:
    """正文里能不能找到标题原文——找到就说明这条文献真被某处引用过。"""
    t, p = normalize(target), normalize(passage)
    if len(t) < 8 or len(p) < 20:
        return False
    return t[: min(probe_len, len(t))] in p


def best_match(target: str, results: list[dict]) -> dict | None:
    """在结果里找证据最强的一条：标题相似度 vs 正文原话命中，取高者。"""
    best, best_sim, best_ev = None, 0.0, "title"
    for item in results:
        tsim = similarity(target, item.get("title", ""))
        if passage_supports(target, item.get("passage", "")):
            ev, sim = "passage", max(tsim, PASSAGE_HIT)
        else:
            ev, sim = "title", tsim
        if sim > best_sim:
            best, best_sim, best_ev = item, sim, ev
    if best is not None:
        best["_sim"] = round(best_sim, 4)
        best["_ev"] = best_ev
    return best


def verdict_for(sim: float, tier: str) -> str:
    """三档判定。聚合站和百科不能直接判"已核实"——它们本身没有一手出处。"""
    if sim >= SIM_VERIFIED and tier not in WEAK_TIERS:
        return VERDICT_VERIFIED
    if sim >= SIM_DOUBT or (sim >= SIM_VERIFIED and tier in WEAK_TIERS):
        return VERDICT_DOUBT
    return VERDICT_MISSING


def explain(sim: float, tier_label: str, verdict: str, evidence: str = "title") -> str:
    ev = "正文命中标题原文" if evidence == "passage" else "标题比对"
    if verdict == VERDICT_VERIFIED:
        return f"{ev}，匹配度 {sim:.0%}，来源属于{tier_label}"
    if verdict == VERDICT_DOUBT:
        if tier_label in ("聚合站", "百科"):
            return f"{ev}，匹配度 {sim:.0%}，但来源是{tier_label}，不宜作为学术出处"
        return f"{ev}，匹配度 {sim:.0%}，找到相近内容但不足以确认"
    return f"{ev}，匹配度仅 {sim:.0%}，返回的多为主题相近的无关内容"
