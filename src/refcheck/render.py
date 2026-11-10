"""终端报告。"""

from __future__ import annotations

import shutil

from .check import VERDICT_SETS, Result, Summary
from .match import VERDICT_DOUBT, VERDICT_MISSING, VERDICT_VERIFIED

C = {
    "reset": "\033[0m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "cyan": "\033[36m",
}

MARK = {VERDICT_VERIFIED: "✓", VERDICT_DOUBT: "?", VERDICT_MISSING: "×"}
COLOR_OF = {VERDICT_VERIFIED: "green", VERDICT_DOUBT: "yellow", VERDICT_MISSING: "red"}


def _c(text: str, color: str, enabled: bool = True) -> str:
    return f"{C[color]}{text}{C['reset']}" if enabled else text


def _width() -> int:
    return min(shutil.get_terminal_size((88, 20)).columns, 100)


def _bar(ratio: float, width: int = 26) -> str:
    filled = int(round(ratio * width))
    return "█" * filled + "░" * (width - filled)


def render(results: list[Result], summary: Summary, title: str, color: bool = True,
           kind: str = "ref") -> str:
    w = _width()
    labels = VERDICT_SETS.get(kind, VERDICT_SETS["ref"])
    out: list[str] = [""]
    out.append(_c(f"  {title}", "bold", color))
    out.append(_c("  " + "─" * (w - 4), "dim", color))
    out.append("")

    total = max(summary.total, 1)
    for label, count, verdict in (
        (labels["verified"], summary.verified, VERDICT_VERIFIED),
        (labels["doubt"], summary.doubt, VERDICT_DOUBT),
        (labels["missing"], summary.missing, VERDICT_MISSING),
    ):
        ratio = count / total
        ck = COLOR_OF[verdict]
        out.append(
            f"  {_c(f'{label:>5}', ck, color)}  {count:>3}  {ratio*100:5.1f}%  "
            + _c(_bar(ratio), ck, color)
        )

    out.append("")
    out.append(_c(f"  共 {summary.total} 条 · 调用 {summary.calls} 次 · 版本 {summary.version or '-'}",
                  "dim", color))
    if summary.misleading:
        out.append(_c(f"  其中 {summary.misleading} 条「有结果、但对不上」——这是编造内容最典型的形态",
                      "yellow", color))
    out.append("")

    for r in results:
        ck = COLOR_OF.get(r.verdict, "dim")
        badge = f"{MARK.get(r.verdict, '·')} {r.display_verdict}"
        out.append(_c(f"  [{r.index:02d}] {badge:<10}", ck, color)
                   + _c(f"{r.sim_label} · {r.tier_label}", "dim", color))
        out.append(f"       {r.label}")
        if r.query and r.query != r.label:
            out.append(_c(f"       检索词：{r.query}", "dim", color))
        if r.best and r.best.url:
            out.append(_c(f"       出处：{r.best.site or '未知站点'} · {r.best.date or '无日期'}", "cyan", color))
            url = r.best.url
            out.append(_c("       " + (url if len(url) <= w - 12 else url[: w - 15] + "…"), "dim", color))
        out.append(_c(f"       {r.note}", "dim", color))
        out.append("")

    out.append(_c("  " + "─" * (w - 4), "dim", color))
    tail = (
        "  只验证出处，不判断医学结论对错，不构成任何医疗建议。"
        if kind == "ref"
        else "  有出处只说明找到覆盖这些实体的权威资料，不代表该结论一定正确。不构成任何医疗建议。"
    )
    out.append(_c(tail, "dim", color))
    out.append("")
    return "\n".join(out)
