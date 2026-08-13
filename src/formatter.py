"""早报排版：昨日 00:00（北京时间）至今晨的新闻，按类别生成微信文本（每条 ≤600 字符）。

实测微信客服消息文本限制为 600 字符（45002），600 全中文仅 1800 字节，按字符截断
同时满足字节约束。每条消息一个类别，共 4 条。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sources import CATEGORY_LABELS, NewsItem

CN_TZ = ZoneInfo("Asia/Shanghai")
MAX_CHARS = 600  # 微信客服消息文本字符上限

# 主源优先：每类主源条目排前面，备选源只在主源条数不足时补位。
# 备选源（环球网/澎湃）是全站内容、类别不纯，避免挤掉纯类别的核心新闻。
SOURCE_PRIORITY = {
    "IT之家": 0, "东方财富": 0, "中新网": 0, "百度热搜": 0,
    "少数派": 1, "环球网": 1, "澎湃": 1,
}


def filter_recent(items: list[NewsItem], now_utc: datetime | None = None) -> list[NewsItem]:
    """早报模式过滤：保留 pub_time >= 昨天 00:00（北京时区）的条目；无时间信息（热搜）保留。"""
    now = now_utc or datetime.now(timezone.utc)
    cutoff = (
        now.astimezone(CN_TZ).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    ).astimezone(timezone.utc).replace(tzinfo=None)  # naive UTC
    return [it for it in items if it.pub_time is None or it.pub_time >= cutoff]


def _dedupe(items: list[NewsItem]) -> list[NewsItem]:
    """URL 去重 + 标题完全一致去重，保留先出现的。"""
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    out: list[NewsItem] = []
    for it in items:
        if it.url and it.url in seen_urls:
            continue
        if it.title in seen_titles:
            continue
        if it.url:
            seen_urls.add(it.url)
        seen_titles.add(it.title)
        out.append(it)
    return out


def _category_items(items: list[NewsItem], cat: str, now: datetime) -> list[NewsItem]:
    """单个类别的条目：去重、时间倒序（无时间视为最新）、主源置前备选补位。"""
    now_naive = now.replace(tzinfo=None)
    grouped = [it for it in _dedupe(filter_recent(items, now)) if it.category == cat]
    grouped.sort(key=lambda x: x.pub_time or now_naive, reverse=True)
    grouped.sort(key=lambda x: SOURCE_PRIORITY.get(x.source, 1))
    return grouped


def format_category_report(
    items: list[NewsItem],
    cat: str,
    per_category: int,
    now_utc: datetime | None = None,
) -> str:
    """生成单个类别的早报文本（≤600 字符）。

    微信客服消息 48h 窗口最多下发 5 条，因此每类固定 1 条消息（4 类共 4 条），
    600 字符装不下时从尾部删条目，宁缺毋滥。
    """
    now = now_utc or datetime.now(timezone.utc)
    today_cn = now.astimezone(CN_TZ)

    lines = [f"【{CATEGORY_LABELS[cat]}】{today_cn.month}月{today_cn.day}日早报"]
    for i, it in enumerate(_category_items(items, cat, now)[:per_category], 1):
        # 标题 26 字截断：600 字符/条装 8 条带链接新闻，标题过长会挤掉尾部条目
        title = it.title if len(it.title) <= 26 else it.title[:25] + "…"
        line = f"{i}. {title}（{it.source}）"
        if it.url:
            line += f"\n   {it.url}"
        lines.append(line)

    text = "\n".join(lines)
    while len(text) > MAX_CHARS and len(lines) > 1:
        lines.pop()
        text = "\n".join(lines)
    return text


def format_all_reports(
    items: list[NewsItem],
    category_order: list[str],
    per_category: int,
    now_utc: datetime | None = None,
) -> dict[str, str]:
    """生成全部类别的早报文本，返回 {类别: 文本}。"""
    return {
        cat: format_category_report(items, cat, per_category, now_utc)
        for cat in category_order
    }
