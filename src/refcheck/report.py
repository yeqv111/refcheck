"""单文件 HTML 核查报告：零外部资源，直接双击打开或截图。"""

from __future__ import annotations

import html
from datetime import datetime

from .check import VERDICT_SETS, Result, Summary
from .match import VERDICT_DOUBT, VERDICT_MISSING, VERDICT_VERIFIED

COLOR = {
    VERDICT_VERIFIED: ("#1D9E75", "#E8F6F0"),
    VERDICT_DOUBT: ("#BA7517", "#FCF3E2"),
    VERDICT_MISSING: ("#E24B4A", "#FCEDEC"),
}


def _e(s: str) -> str:
    return html.escape(str(s or ""))


def _row(r: Result) -> str:
    fg, bg = COLOR.get(r.verdict, ("#5F5E5A", "#F1EFE8"))
    name = r.display_verdict
    src = ""
    if r.best and r.best.url:
        src = f"""
      <div class="src">
        <span class="dot"></span>
        <span class="sitename">{_e(r.best.site or "未知站点")}</span>
        <span class="date">{_e(r.best.date)}</span>
        <a href="{_e(r.best.url)}" target="_blank">{_e(r.best.title[:70])}</a>
      </div>"""
    query = ""
    if r.query and r.query != r.label:
        query = f'<div class="query">检索词　{_e(r.query)}</div>'
    return f"""
    <div class="item">
      <div class="bar" style="background:{fg}"></div>
      <div class="body">
        <div class="head">
          <span class="idx">{r.index:02d}</span>
          <span class="badge" style="color:{fg};background:{bg}">{name}</span>
          <span class="meta">{r.sim_label} · 来源{r.tier_label} · 返回 {r.candidates} 条</span>
        </div>
        <div class="text">{_e(r.label)}</div>
        {query}
        {src}
        <div class="note">{_e(r.note)}</div>
      </div>
    </div>"""


def render_html(results: list[Result], summary: Summary, title: str, subtitle: str = "",
                kind: str = "ref") -> str:
    total = max(summary.total, 1)
    labels = VERDICT_SETS.get(kind, VERDICT_SETS["ref"])
    blocks = []
    for name, count, verdict in [
        (labels["verified"], summary.verified, VERDICT_VERIFIED),
        (labels["doubt"], summary.doubt, VERDICT_DOUBT),
        (labels["missing"], summary.missing, VERDICT_MISSING),
    ]:
        fg, bg = COLOR[verdict]
        pct = count / total * 100
        blocks.append(
            f"""
      <div class="stat">
        <div class="stat-num" style="color:{fg}">{count}</div>
        <div class="stat-name">{name} · {pct:.0f}%</div>
        <div class="track"><div class="fill" style="width:{pct:.1f}%;background:{fg}"></div></div>
      </div>"""
        )

    rows = "".join(_row(r) for r in results)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    limit_text = (
        "「查无出处」只说明本次检索未找到可靠出处，不等于该结论在医学上错误；「存疑」同理。"
        if kind == "ref"
        else "「未找到」只说明本次检索没有找到覆盖这些实体的权威资料，不等于该结论在医学上错误；「弱支撑」同理。"
    )
    method = (
        "取标题相似度最高的一条，正文命中标题原文时加分"
        if kind == "ref"
        else "取关键实体覆盖比例最高的一条（药名、指标、疾病、药物类别）"
    )
    warn = ""
    if summary.misleading:
        warn = f"""
  <div class="warn">
    <strong>{summary.misleading} 条「有结果、但对不上」</strong>
    搜索引擎返回了内容，却没有一条是它 —— 这是编造内容最典型的形态。
  </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB",
                 "Microsoft YaHei", sans-serif;
    background: #F5F4F0; color: #1F1F1D; line-height: 1.6;
    padding: 32px 20px 40px; -webkit-font-smoothing: antialiased;
  }}
  .wrap {{ max-width: 760px; margin: 0 auto; }}
  .card {{
    background: #fff; border-radius: 16px; padding: 28px 28px 8px;
    box-shadow: 0 1px 2px rgba(0,0,0,.04), 0 8px 28px rgba(0,0,0,.05);
  }}
  h1 {{ font-size: 24px; font-weight: 600; letter-spacing: -.3px; }}
  .sub {{ color: #86847C; font-size: 13px; margin-top: 6px; }}
  .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin: 26px 0 8px; }}
  .stat {{ background: #FAFAF7; border-radius: 12px; padding: 16px 16px 14px; }}
  .stat-num {{ font-size: 30px; font-weight: 600; line-height: 1.1; }}
  .stat-name {{ font-size: 12px; color: #6B6A64; margin: 4px 0 10px; }}
  .track {{ height: 5px; background: #E8E6DF; border-radius: 3px; overflow: hidden; }}
  .fill {{ height: 100%; border-radius: 3px; }}
  .warn {{
    background: #FCF3E2; color: #7A4E0C; border-radius: 10px;
    padding: 12px 14px; font-size: 13px; margin: 18px 0 4px; line-height: 1.55;
  }}
  .warn strong {{ font-weight: 600; }}
  .sec {{ font-size: 13px; color: #86847C; margin: 26px 0 10px; letter-spacing: .5px; }}
  .item {{
    display: flex; gap: 14px; padding: 14px 0; border-top: 1px solid #EFEDE6;
  }}
  .bar {{ width: 3px; border-radius: 2px; flex: none; }}
  .body {{ flex: 1; min-width: 0; }}
  .head {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
  .idx {{ font-size: 12px; color: #A8A69E; font-variant-numeric: tabular-nums; }}
  .badge {{ font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 5px; }}
  .meta {{ font-size: 12px; color: #9A9890; }}
  .text {{ font-size: 14px; margin-top: 6px; word-break: break-word; }}
  .query {{ font-size: 12px; color: #9A9890; margin-top: 5px; font-family: ui-monospace, monospace; }}
  .src {{
    display: flex; align-items: baseline; gap: 7px; margin-top: 7px;
    font-size: 12px; flex-wrap: wrap;
  }}
  .dot {{ width: 5px; height: 5px; border-radius: 50%; background: #C9C7BE; flex: none; }}
  .sitename {{ color: #4A4944; font-weight: 500; }}
  .date {{ color: #A8A69E; }}
  .src a {{ color: #185FA5; text-decoration: none; overflow: hidden; text-overflow: ellipsis;
            white-space: nowrap; max-width: 480px; }}
  .note {{ font-size: 12px; color: #9A9890; margin-top: 5px; }}
  .foot {{
    margin-top: 26px; padding: 16px 0 20px; border-top: 1px solid #EFEDE6;
    font-size: 12px; color: #9A9890; line-height: 1.7;
  }}
  .foot b {{ color: #6B6A64; font-weight: 600; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <h1>{_e(title)}</h1>
    <div class="sub">{_e(subtitle)}　·　{stamp}　·　元宝搜索 {_e(summary.version or "-")}　·　调用 {summary.calls} 次</div>

    <div class="stats">{''.join(blocks)}</div>
    {warn}

    <div class="sec">核查明细</div>
    {rows}

    <div class="foot">
      <b>方法</b>　每条内容单独检索，{method}，结合来源分级（官方 / 学术 / 媒体 / 百科 / 聚合站）给出判定。<br>
      <b>限制</b>　{limit_text}<br>
      <b>声明</b>　本工具只验证出处，不提供任何医疗建议，不构成诊断依据。身体不适请前往正规医疗机构就诊。
    </div>
  </div>
</div>
</body>
</html>"""
