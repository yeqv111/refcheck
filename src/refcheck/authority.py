"""来源权威度判断：自建域名白名单。

为什么不用官方的 authority_level？
—— 该字段只在旗舰版返回，而个人账号的活动免费额度仅覆盖极速版与标准版，
   所以拿不到。只能自己建一套分级。

分四档，返回 0~1 的权威分：
  official 1.0  监管机构 / 政府
  academic 0.9  期刊社 / 文献库 / 高校
  media    0.6  主流媒体 / 科普平台
  farm     0.15 内容聚合站（主题相近但无一手出处，编造文献最喜欢混在这种地方）
  unknown  0.4  未知站点
"""

from __future__ import annotations

import re

# 政府与监管
OFFICIAL_SUFFIXES = (".gov.cn", ".gov", ".gov.hk")
OFFICIAL_HOSTS = (
    "who.int", "nih.gov", "cdc.gov", "nmpa.gov.cn", "nhc.gov.cn",
    "cma.org.cn", "chinacdc.cn", "nccd.org.cn",
)

# 学术：期刊社、文献库、高校
ACADEMIC_SUFFIXES = (".edu.cn", ".edu", ".ac.cn")
ACADEMIC_HOSTS = (
    "cnki.net", "wanfangdata.com.cn", "cqvip.com", "yiigle.com",
    "medlive.cn", "sinomed.ac.cn", "pubmed.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov", "springer.com", "sciencedirect.com",
    "wiley.com", "nature.com", "thelancet.com", "nejm.org", "bmj.com",
    "chinamedjournal.com", "cjnh.org.cn",
    # 各刊官网
    "zhhlzzs.com", "medjournals.cn", "cjournal.hep.com.cn",
    "chinajournal.net.cn", "zhyxzz.com", "cjcp.org.cn",
)
ACADEMIC_KEYWORDS = ("期刊", "杂志社", "学报", "文献", "学术", "知网", "万方", "维普")

# 主流媒体 / 科普
MEDIA_HOSTS = (
    "people.com.cn", "xinhuanet.com", "news.cn", "gmw.cn", "cctv.com",
    "chinanews.com.cn", "thepaper.cn", "kepuchina.cn", "dxy.cn",
    "msdmanuals.cn", "yixue.com",
)

# 百科：人人可编辑，能当线索不能当学术出处
UGC_HOSTS = (
    "baike.baidu.com", "baike.sogou.com", "baike.so.com",
    "zh.wikipedia.org", "wikipedia.org", "wikiwand.com", "baike.com",
)

# 内容聚合站：特征是同题内容被反复改写，没有一手出处
FARM_KEYWORDS = (
    "博禾医生", "妙手医生", "35健康", "民福康", "有问必答", "复禾健康",
    "三知健康", "看病网", "有来医生", "医谷", "快速问医生", "寻医问药",
    "大众养生网", "家庭医生在线", "康爱多", "健客网", "药房网",
    "搜狐", "网易号", "百家号", "头条号", "知乎专栏", "简书",
)

TIER_SCORE = {
    "official": 1.0,
    "academic": 0.9,
    "media": 0.6,
    "ugc": 0.45,
    "farm": 0.15,
    "unknown": 0.4,
}

# 这两档不能作为「已核实」的依据
WEAK_TIERS = ("farm", "ugc")


def _match_host(host: str, hosts: tuple) -> bool:
    """支持子域名：zh.zhhlzzs.com 应命中 zhhlzzs.com。"""
    return any(host == h or host.endswith("." + h) for h in hosts)


def _host(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url or "")
    host = (m.group(1) if m else "").lower()
    return host[4:] if host.startswith("www.") else host


def classify(url: str, site: str = "") -> tuple[str, float]:
    """返回 (档位, 权威分)。"""
    host = _host(url)
    site = site or ""

    if host.endswith(OFFICIAL_SUFFIXES) or _match_host(host, OFFICIAL_HOSTS):
        return "official", TIER_SCORE["official"]
    if host.endswith(ACADEMIC_SUFFIXES) or _match_host(host, ACADEMIC_HOSTS):
        return "academic", TIER_SCORE["academic"]

    haystack = f"{host} {site}"
    if any(k in haystack for k in ACADEMIC_KEYWORDS):
        return "academic", TIER_SCORE["academic"]
    if any(k in haystack for k in FARM_KEYWORDS):
        return "farm", TIER_SCORE["farm"]
    if _match_host(host, UGC_HOSTS):
        return "ugc", TIER_SCORE["ugc"]
    if _match_host(host, MEDIA_HOSTS) or any(k in haystack for k in ("日报", "新闻网", "电视台", "科普中国", "人民网", "新华网")):
        return "media", TIER_SCORE["media"]

    return "unknown", TIER_SCORE["unknown"]


TIER_LABEL = {
    "official": "官方",
    "academic": "学术",
    "media": "媒体",
    "ugc": "百科",
    "farm": "聚合站",
    "unknown": "未知",
}
