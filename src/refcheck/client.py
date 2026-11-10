"""SearchPro 调用封装：解析 Pages、去重、计数、友好的错误提示。"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from . import tc3
from .authority import classify


class QuotaError(RuntimeError):
    pass


@dataclass
class SearchHit:
    title: str
    url: str
    site: str
    date: str
    score: float
    passage: str
    tier: str
    tier_score: float

    @classmethod
    def from_raw(cls, raw: dict) -> "SearchHit":
        tier, tscore = classify(raw.get("url", ""), raw.get("site", ""))
        return cls(
            title=(raw.get("title") or "").strip(),
            url=raw.get("url") or "",
            site=raw.get("site") or "",
            date=(raw.get("date") or "").split(" ")[0],
            score=float(raw.get("score") or 0),
            passage=(raw.get("passage") or "").strip(),
            tier=tier,
            tier_score=tscore,
        )


class Searcher:
    """包一层元宝搜索，负责解析、缓存与错误翻译。"""

    def __init__(
        self,
        secret_id: str,
        secret_key: str,
        industry: str | None = "acad",
        cnt: int = 10,
        pause: float = 0.25,
    ) -> None:
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.industry = industry
        self.cnt = cnt
        self.pause = pause
        self.calls = 0
        self.cache: dict[str, list[SearchHit]] = {}
        self.version = ""

    def search(self, query: str) -> list[SearchHit]:
        key = f"{self.industry}|{self.cnt}|{query}"
        if key in self.cache:
            return self.cache[key]

        params = {"Query": query, "Mode": 2, "Cnt": self.cnt}
        if self.industry:
            params["Industry"] = self.industry

        try:
            resp = tc3.call(self.secret_id, self.secret_key, params)
        except tc3.APIError as exc:
            if exc.code in ("ResourceNotFound", "ResourceUnavailable"):
                raise QuotaError(
                    "元宝搜索服务未开通，或当前版本不支持该参数。"
                    "请先在控制台开通服务并核销活动邀请码。"
                ) from None
            if exc.code == "RequestLimitExceeded":
                raise QuotaError("调用频率超限，稍等几秒再跑。") from None
            raise

        self.calls += 1
        self.version = resp.get("Version", "")

        hits: list[SearchHit] = []
        for page in resp.get("Pages") or []:
            try:
                raw = json.loads(page)
            except (TypeError, ValueError):
                continue
            hit = SearchHit.from_raw(raw)
            if hit.title or hit.url:
                hits.append(hit)

        self.cache[key] = hits
        if self.pause:
            time.sleep(self.pause)
        return hits
