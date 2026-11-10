"""RefCheck 命令行入口。

用法：
    python3 -m refcheck refs   --input refs.txt   --report out/
    python3 -m refcheck claims --input answer.txt --report out/

凭据从环境变量读取：
    TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .check import check_claims, check_references, summarize
from .client import QuotaError, Searcher
from .extract import parse_claims, parse_references
from .report import render_html
from .render import render
from .tc3 import APIError


def _credentials(args) -> tuple[str, str]:
    sid = args.secret_id or os.environ.get("TENCENTCLOUD_SECRET_ID", "")
    skey = args.secret_key or os.environ.get("TENCENTCLOUD_SECRET_KEY", "")
    if not sid or not skey:
        sys.exit(
            "缺少凭据。请先设置环境变量：\n"
            "  export TENCENTCLOUD_SECRET_ID=你的SecretId\n"
            "  export TENCENTCLOUD_SECRET_KEY=你的SecretKey\n"
            "或在命令后加 --secret-id / --secret-key。"
        )
    return sid, skey


def _progress(result, total: int) -> None:
    mark = {"已核实": "✓", "存疑": "?", "查无出处": "×"}.get(result.verdict, "·")
    sys.stderr.write(f"\r  核查中 {result.index}/{total}  {mark} {result.label[:40]:<40}")
    sys.stderr.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="refcheck",
        description="RefCheck · 医学信息溯源核查器（元宝搜索）",
    )
    parser.add_argument("mode", choices=["refs", "claims"], help="refs=核查参考文献；claims=核查医学陈述")
    parser.add_argument("--input", "-i", required=True, help="待核查文本文件（UTF-8）")
    parser.add_argument("--report", "-r", default="out", help="报告输出目录（默认 out/）")
    parser.add_argument("--cnt", type=int, default=10, choices=[10, 20, 30, 40, 50],
                        help="每条检索返回条数（默认 10）")
    parser.add_argument("--industry", default=None,
                        choices=["acad", "news", "gov", "finance", "none"],
                        help="垂直领域。默认：refs 模式不限定（acad 会过滤掉知网），claims 模式用 acad")
    parser.add_argument("--limit", type=int, default=0, help="只核查前 N 条（调试用）")
    parser.add_argument("--delay", type=float, default=0.25,
                        help="每次调用之间的间隔秒数（默认 0.25，遇到限流可调大）")
    parser.add_argument("--secret-id", default="", help="腾讯云 SecretId（或用环境变量）")
    parser.add_argument("--secret-key", default="", help="腾讯云 SecretKey（或用环境变量）")
    parser.add_argument("--no-color", action="store_true", help="终端输出不带颜色")
    parser.add_argument("--quiet", action="store_true", help="不打印进度")
    args = parser.parse_args(argv)

    src = Path(args.input)
    if not src.exists():
        sys.exit(f"找不到输入文件：{src}")
    text = src.read_text(encoding="utf-8")

    if args.mode == "refs":
        refs = parse_references(text)
        if args.limit:
            refs = refs[: args.limit]
        if not refs:
            sys.exit("没有从文件里解析出参考文献，检查一下格式（每行一条，或 GB/T 7714 格式）。")
        units = refs
        title = "参考文献溯源核查"
    else:
        claims = parse_claims(text)
        if args.limit:
            claims = claims[: args.limit]
        if not claims:
            sys.exit("没有从文件里抽取出可核查的医学陈述。")
        units = claims
        title = "医学陈述溯源核查"

    sid, skey = _credentials(args)
    industry = args.industry
    if industry is None:
        industry = "none" if args.mode == "refs" else "acad"
    searcher = Searcher(
        sid, skey, industry=None if industry == "none" else industry,
        cnt=args.cnt, pause=args.delay,
    )

    print(f"\n  RefCheck · {title}")
    print(f"  待核查 {len(units)} 条 · 领域 {industry} · 每条取 {args.cnt} 个结果\n")

    cb = None if args.quiet else _progress
    try:
        if args.mode == "refs":
            results = check_references(units, searcher, progress=cb)
        else:
            results = check_claims(units, searcher, progress=cb)
    except QuotaError as exc:
        print(f"\n  [额度/权限] {exc}", file=sys.stderr)
        return 2
    except APIError as exc:
        print(f"\n  [接口错误] {exc}", file=sys.stderr)
        return 3

    if not args.quiet:
        sys.stderr.write("\r" + " " * 78 + "\r")

    summary = summarize(results, searcher)
    kind = "ref" if args.mode == "refs" else "claim"
    print(render(results, summary, title, color=not args.no_color, kind=kind))

    out_dir = Path(args.report)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = "references" if args.mode == "refs" else "claims"
    html_path = out_dir / f"{stem}_report.html"
    html_path.write_text(
        render_html(
            results,
            summary,
            f"RefCheck · {title}",
            f"{src.name} · {summary.total} 条",
            kind=kind,
        ),
        encoding="utf-8",
    )

    json_path = out_dir / f"{stem}_result.json"
    json_path.write_text(
        json.dumps(
            {
                "title": title,
                "version": summary.version,
                "calls": summary.calls,
                "total": summary.total,
                "verified": summary.verified,
                "doubt": summary.doubt,
                "missing": summary.missing,
                "misleading": summary.misleading,
                "empty_result": summary.empty_result,
                "tier_counts": summary.tier_counts,
                "items": [
                    {
                        "index": r.index,
                        "label": r.label,
                        "query": r.query,
                        "verdict": r.verdict,
                        "verdict_label": r.display_verdict,
                        "similarity": round(r.sim, 4),
                        "tier": r.tier,
                        "candidates": r.candidates,
                        "source": {
                            "title": r.best.title if r.best else "",
                            "url": r.best.url if r.best else "",
                            "site": r.best.site if r.best else "",
                            "date": r.best.date if r.best else "",
                        },
                    }
                    for r in results
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"  HTML 报告 → {html_path}")
    print(f"  结构化结果 → {json_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
