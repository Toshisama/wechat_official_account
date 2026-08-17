"""新闻源抓取模块。

每个 fetch_* 函数返回 list[NewsItem]，实现独立、互不影响（单源失败不影响其他源）。

时间约定：NewsItem.pub_time 统一为 naive UTC（feedparser 的 published_parsed 天然是 UTC，
东方财富的 showTime 是北京时间，抓取时减 8 小时归一）。None 表示无时间信息（如热搜榜），
格式化时视为最新。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import feedparser
import requests

# 类别常量
CAT_TECH = "tech"
CAT_FINANCE = "finance"
CAT_WORLD = "world"
CAT_CHINA = "china"

CATEGORY_LABELS = {
    CAT_TECH: "科技",
    CAT_FINANCE: "财经",
    CAT_WORLD: "国际",
    CAT_CHINA: "国内/社会",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}

_session = requests.Session()
_session.headers.update(HEADERS)


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    category: str
    pub_time: Optional[datetime] = None


def _rss(url: str, source: str, category: str, timeout: float = 15.0, limit: int = 30) -> list[NewsItem]:
    """通用 RSS 抓取：feedparser 解析，统一为 NewsItem。"""
    resp = _session.get(url, timeout=timeout)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    items: list[NewsItem] = []
    for entry in feed.entries[:limit]:
        title = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", "").strip()
        if not title or not link:
            continue
        pub = None
        if getattr(entry, "published_parsed", None):
            pub = datetime(*entry.published_parsed[:6])
        items.append(NewsItem(title=title, url=link, source=source, category=category, pub_time=pub))
    return items


# ---------- 科技 ----------

def fetch_ithome() -> list[NewsItem]:
    """IT之家全站 RSS（科技数码）。"""
    return _rss("https://www.ithome.com/rss/", "IT之家", CAT_TECH)


def fetch_sspai() -> list[NewsItem]:
    """少数派（科技数码效率）。作科技备选。"""
    return _rss("https://sspai.com/feed", "少数派", CAT_TECH)


# ---------- 财经 ----------

def fetch_eastmoney() -> list[NewsItem]:
    """东方财富 7x24 全球快讯公开接口（无鉴权）。showTime 为北京时间，转 UTC 归一。"""
    import uuid

    url = (
        "https://np-listapi.eastmoney.com/comm/web/getFastNewsList"
        f"?client=web&biz=web_724&fastColumn=102&sortEnd=&pageSize=30&req_trace={uuid.uuid4()}"
    )
    resp = _session.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    items: list[NewsItem] = []
    now = datetime.now(timezone.utc)
    for item in data.get("data", {}).get("fastNewsList", []):
        title = (item.get("title") or item.get("summary") or "").strip()
        if not title:
            continue
        link = item.get("url") or ""
        if not link.startswith("http"):
            # 东财文章 URL 格式：https://finance.eastmoney.com/a/{code}.html（缺 .html 会 404）
            link = "https://finance.eastmoney.com/a/" + (item.get("code") or "") + ".html"
        pub = None
        show_time = item.get("showTime") or ""
        m = re.match(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})", show_time)
        if not m:
            m = re.match(r"(\d{2})-(\d{2}) (\d{2}):(\d{2})", show_time)
            if m:
                # 缺年份：若月份大于当前月份则视为去年
                month = int(m.group(1))
                year = now.year if month <= now.month else now.year - 1
                show_time = f"{year}-{show_time}"
                m = re.match(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})", show_time)
        if m:
            local = datetime(*[int(x) for x in m.groups()])
            pub = (local - timedelta(hours=8)).replace(tzinfo=None)  # 北京 -> UTC
        items.append(NewsItem(title=title, url=link, source="东方财富", category=CAT_FINANCE, pub_time=pub))
    return items


# ---------- 国际 ----------

def fetch_chinanews_world() -> list[NewsItem]:
    """中国新闻网国际频道官方 RSS（实时更新）。"""
    return _rss("http://www.chinanews.com.cn/rss/world.xml", "中新网", CAT_WORLD)


def fetch_huanqiu_news() -> list[NewsItem]:
    """环球网 via RSSHub 镜像（内容含国内，作国际备选）。"""
    return _rss("https://rss.injahow.cn/huanqiu/news", "环球网", CAT_WORLD)


# ---------- 国内/社会 ----------

def fetch_baidu_hot() -> list[NewsItem]:
    """百度实时热搜榜：页面内嵌 JSON，取前 20 条。无发布时间，pub_time=None。

    不带链接：热搜词本身的搜索链接是 URL 编码长串（每条 130+ 字符），
    600 字符/条的消息装不下几条，且用户看热搜词即可自行搜索。
    """
    url = "https://top.baidu.com/board?tab=realtime"
    resp = _session.get(url, timeout=15)
    resp.raise_for_status()
    text = resp.text
    m = re.search(r"<!--s-data:(\{.*?\})-->", text, re.DOTALL)
    if not m:
        raise RuntimeError("百度热搜页面未找到内嵌 JSON")
    data = json.loads(m.group(1))
    items: list[NewsItem] = []
    for item in data.get("data", {}).get("cards", [])[:1]:
        for entry in item.get("content", [])[:20]:
            query = (entry.get("query") or "").strip()
            if not query:
                continue
            items.append(NewsItem(title=query, url="", source="百度热搜", category=CAT_CHINA, pub_time=None))
    return items


def fetch_pengpai_featured() -> list[NewsItem]:
    """澎湃头条 via RSSHub 镜像。作国内/社会备选。"""
    return _rss("https://rss.injahow.cn/thepaper/featured", "澎湃", CAT_CHINA)


# 所有抓取函数（probe 脚本遍历用）
FETCHERS = {
    "ithome": (fetch_ithome, CAT_TECH),
    "sspai": (fetch_sspai, CAT_TECH),
    "eastmoney": (fetch_eastmoney, CAT_FINANCE),
    "chinanews_world": (fetch_chinanews_world, CAT_WORLD),
    "huanqiu_news": (fetch_huanqiu_news, CAT_WORLD),
    "baidu_hot": (fetch_baidu_hot, CAT_CHINA),
    "pengpai_featured": (fetch_pengpai_featured, CAT_CHINA),
}
