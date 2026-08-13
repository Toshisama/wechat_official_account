"""运行配置：环境变量读取 + 类别元数据。"""
from __future__ import annotations

import os


def _env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"缺少环境变量 {name}，请检查 .env 或 GitHub Secrets 配置")
    return value


def get_app_id() -> str:
    return _env("WECHAT_APP_ID")


def get_app_secret() -> str:
    return _env("WECHAT_APP_SECRET")


def get_openids() -> list[str]:
    return [x.strip() for x in _env("WECHAT_OPENIDS").split(",") if x.strip()]


def news_per_category() -> int:
    """每类条数默认 8（单条消息 600 字符上限内可放约 8 条带链接新闻，超限自动删尾部条目）。"""
    try:
        return max(1, int(os.getenv("NEWS_PER_CATEGORY", "8")))
    except ValueError:
        return 8
