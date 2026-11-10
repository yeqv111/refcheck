"""核查流程：把抽取出来的单元逐条送去检索，产出带判定的结果。

两类单元用两套判据，因为它们的"像"不是一回事：

  参考文献 → 比标题。要找的是"这一篇"，标题对得上才算数。
  医学陈述 → 比实体覆盖。句子永远不可能和文章标题相似，要看的是
             "有没有资料同时讲到这些药、这些指标"。

后者比前者弱：覆盖到实体只说明"有资料讨论这些事"，不等于"这份资料支持这个结论"。
报告里必须写清这条边界。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .authority import TIER_LABEL
from .client import SearchHit, Searcher
from .extract import Claim, Reference
from .match import (
    VERDICT_DOUBT,
    VERDICT_MISSING,
    VERDICT_VERIFIED,
    best_match,
    normalize,
    verdict_for,
)

# 能单独支撑"已核实"的来源档位
STRONG_TIERS = ("official", "academic", "media")

COV_VERIFIED = 0.72
COV_DOUBT = 0.45


@dataclass
class Result:
    kind: str  # "ref" | "claim"
    index: int
    label: str
    raw_text: str
    query: str
    verdict: str
    sim: float
    tier: str
    candidates: int = 0
    best: SearchHit | None = None
    note: str = ""
    entities: list[str] = field(default_factory=list)
    covered: list[str] = field(default_factory=list)

    @property
    def tier_label(self) -> str:
        return TIER_LABEL.get(self.tier, "未知")

    @property
    def display_verdict(self) -> str:
        """陈述类用更克制的说法：覆盖到实体 ≠ 结论被证实。"""
        if self.kind == "claim":
            return {
                VERDICT_VERIFIED: "有出处",
                VERDICT_DOUBT: "弱支撑",
                VERDICT_MISSING: "未找到",
            }[self.verdict]
        return self.verdict

    @property
    def sim_label(self) -> str:
        return f"覆盖 {self.sim:.0%}" if self.kind == "claim" else f"匹配 {self.sim:.0%}"

    @property
    def false_positive_signal(self) -> bool:
        """返回了结果，但没有一条对得上 —— 编造内容最典型的样子。"""
        return self.verdict == VERDICT_MISSING and self.candidates > 0


def _as_dict(h: SearchHit) -> dict:
    return {
        "title": h.title,
        "url": h.url,
        "site": h.site,
        "date": h.date,
        "score": h.score,
        "passage": h.passage,
    }


def _judge_ref(ref: Reference, hits: list[SearchHit]) -> Result:
    best = best_match(ref.title, [_as_dict(h) for h in hits])
    if not best:
        return Result("ref", ref.index, ref.title, ref.raw, ref.query,
                      VERDICT_MISSING, 0.0, "unknown", candidates=len(hits),
                      note="没有检索到任何结果")

    sim = float(best.get("_sim", 0.0))
    hit = next((h for h in hits if h.url == best.get("url")), None) or SearchHit.from_raw(best)
    verdict = verdict_for(sim, hit.tier)
    ev = "正文命中标题原文" if best.get("_ev") == "passage" else "标题比对"
    if verdict == VERDICT_VERIFIED:
        note = f"{ev}，匹配度 {sim:.0%}，来源属于{TIER_LABEL.get(hit.tier, '未知')}"
    elif verdict == VERDICT_DOUBT and hit.tier == "ugc":
        note = f"{ev}，匹配度 {sim:.0%}；内容确实存在，但来源是百科，建议改引原始出处"
    elif verdict == VERDICT_DOUBT and hit.tier == "farm":
        note = f"{ev}，匹配度 {sim:.0%}；来源是内容聚合站，无一手出处"
    elif verdict == VERDICT_DOUBT:
        note = f"{ev}，匹配度 {sim:.0%}，找到相近内容但不足以确认"
    else:
        note = f"{ev}，匹配度仅 {sim:.0%}，返回的多为主题相近的无关内容"

    return Result("ref", ref.index, ref.title, ref.raw, ref.query, verdict, sim,
                  hit.tier, candidates=len(hits), best=hit, note=note)


def _coverage(entities: list[str], hit: SearchHit) -> tuple[float, list[str]]:
    text = normalize(f"{hit.title} {hit.passage}")
    covered = [e for e in entities if normalize(e) in text]
    return (len(covered) / len(entities) if entities else 0.0), covered


def _judge_claim(claim: Claim, hits: list[SearchHit]) -> Result:
    if not hits:
        return Result("claim", claim.index, claim.label, claim.text, claim.query,
                      VERDICT_MISSING, 0.0, "unknown", candidates=0,
                      entities=claim.entities, note="没有检索到任何结果")

    scored = []
    for h in hits:
        cov, covered = _coverage(claim.entities, h)
        scored.append((cov, covered, h))
    scored.sort(key=lambda x: (x[0], x[2].tier_score, x[2].score), reverse=True)
    cov, covered, hit = scored[0]

    n_ent = len(claim.entities)
    if cov >= COV_VERIFIED and hit.tier in STRONG_TIERS and n_ent >= 2:
        verdict = VERDICT_VERIFIED
        note = f"关键实体覆盖 {cov:.0%}（{'、'.join(covered)}），来源属于{TIER_LABEL.get(hit.tier)}"
    elif cov >= COV_VERIFIED and n_ent < 2:
        verdict = VERDICT_DOUBT
        note = f"只提到 1 个关键实体（{'、'.join(covered)}），证据面太窄"
    elif cov >= COV_DOUBT:
        verdict = VERDICT_DOUBT
        if hit.tier not in STRONG_TIERS:
            note = f"实体覆盖 {cov:.0%}，但来源是{TIER_LABEL.get(hit.tier)}，不足以支撑"
        else:
            note = f"实体覆盖 {cov:.0%}，有相关讨论但未找到直接支撑"
    else:
        verdict = VERDICT_MISSING
        note = f"实体覆盖仅 {cov:.0%}，返回的多为主题相近但无关的内容"

    return Result("claim", claim.index, claim.label, claim.text, claim.query, verdict,
                  cov, hit.tier, candidates=len(hits), best=hit, note=note,
                  entities=claim.entities, covered=covered)


def check_references(refs: list[Reference], searcher: Searcher, progress=None) -> list[Result]:
    results: list[Result] = []
    for r in refs:
        hits = searcher.search(r.query) if r.query else []
        results.append(_judge_ref(r, hits))
        if progress:
            progress(results[-1], len(refs))
    return results


def check_claims(claims: list[Claim], searcher: Searcher, progress=None) -> list[Result]:
    results: list[Result] = []
    for c in claims:
        hits = searcher.search(c.query) if c.query else []
        results.append(_judge_claim(c, hits))
        if progress:
            progress(results[-1], len(claims))
    return results


VERDICT_SETS = {
    "ref": {"verified": "已核实", "doubt": "存疑", "missing": "查无出处"},
    "claim": {"verified": "有出处", "doubt": "弱支撑", "missing": "未找到"},
}


@dataclass
class Summary:
    total: int = 0
    verified: int = 0
    doubt: int = 0
    missing: int = 0
    empty_result: int = 0
    misleading: int = 0
    tier_counts: dict = field(default_factory=dict)
    version: str = ""
    calls: int = 0

    @property
    def traceable_rate(self) -> float:
        return self.verified / self.total * 100 if self.total else 0.0

    @property
    def doubt_rate(self) -> float:
        return self.doubt / self.total * 100 if self.total else 0.0

    @property
    def missing_rate(self) -> float:
        return self.missing / self.total * 100 if self.total else 0.0


def summarize(results: list[Result], searcher: Searcher | None = None) -> Summary:
    s = Summary(total=len(results))
    for r in results:
        if r.verdict == VERDICT_VERIFIED:
            s.verified += 1
        elif r.verdict == VERDICT_DOUBT:
            s.doubt += 1
        else:
            s.missing += 1
        if r.candidates == 0:
            s.empty_result += 1
        if r.false_positive_signal:
            s.misleading += 1
        s.tier_counts[r.tier] = s.tier_counts.get(r.tier, 0) + 1
    if searcher:
        s.version = searcher.version
        s.calls = searcher.calls
    return s
