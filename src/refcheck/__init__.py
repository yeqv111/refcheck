"""RefCheck · 医学信息溯源核查器

用元宝搜索把 AI 说出的每一句医学陈述、每一条参考文献，逐条查出处。
只验证出处，不判断医学结论对错。
"""

__version__ = "1.0.0"

from .check import check_claims, check_references, summarize  # noqa: E402
from .extract import parse_claims, parse_references  # noqa: E402

__all__ = [
    "__version__",
    "check_claims",
    "check_references",
    "summarize",
    "parse_claims",
    "parse_references",
]
