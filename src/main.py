"""每日早报入口：抓取 → 早报过滤 → 排版 → 微信推送。

用法（本地）：python src/main.py
环境变量：WECHAT_APP_ID / WECHAT_APP_SECRET / WECHAT_OPENIDS（.env 或系统环境）
          WECHAT_TEMPLATE_ID（可选，客服消息失败时的兜底通道）
"""
from __future__ import annotations

import logging
import os
import sys

# Windows 控制台默认 GBK，强制 UTF-8 以支持 emoji 输出
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 本地开发：加载项目根目录 .env（GitHub Actions 中用 Secrets 注入，自动跳过）
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import config
import sources
from formatter import format_all_reports
from wechat import get_access_token, send_custom_text, send_template_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("daily-news")

CATEGORY_ORDER = [sources.CAT_TECH, sources.CAT_FINANCE, sources.CAT_WORLD, sources.CAT_CHINA]


def fetch_all() -> list[sources.NewsItem]:
    """抓取所有已启用源，单源失败仅告警不中断。"""
    all_items: list[sources.NewsItem] = []
    for name, (fetcher, _cat) in sources.FETCHERS.items():
        try:
            items = fetcher()
            log.info("源 %s: %d 条", name, len(items))
            all_items.extend(items)
        except Exception as exc:  # noqa: BLE001 单源失败不阻塞整体
            log.warning("源 %s 抓取失败: %s", name, exc)
    return all_items


def send(token: str, openid: str, report: str) -> None:
    """推送单条：客服消息为主，模板消息兜底。"""
    resp = send_custom_text(token, openid, report)
    errcode = resp.get("errcode", 0)
    if errcode != 0:
        log.warning("客服消息失败(errcode=%s %s)，尝试模板消息兜底", errcode, resp.get("errmsg"))
        template_id = os.getenv("WECHAT_TEMPLATE_ID", "").strip()
        if not template_id:
            raise RuntimeError(f"客服消息失败且未配置 WECHAT_TEMPLATE_ID: {resp}")
        resp2 = send_template_text(token, openid, template_id, report)
        if resp2.get("errcode", 0) != 0:
            raise RuntimeError(f"模板消息兜底也失败: {resp2}")
        log.info("模板消息兜底成功")
    else:
        log.info("客服消息推送成功")


def main() -> int:
    try:
        app_id = config.get_app_id()
        app_secret = config.get_app_secret()
        openids = config.get_openids()
        per_category = config.news_per_category()
    except RuntimeError as exc:
        log.error("%s", exc)
        return 2

    if not openids:
        log.error("WECHAT_OPENIDS 为空")
        return 2

    all_items = fetch_all()
    if not all_items:
        log.error("所有新闻源均无内容")
        return 3

    # 每个类别一条或多条消息（单条限 600 字符，超长自动拆分）
    reports = format_all_reports(all_items, CATEGORY_ORDER, per_category)
    total_msgs = sum(len(texts) for texts in reports.values())
    for cat, texts in reports.items():
        for i, text in enumerate(texts, 1):
            log.info("早报[%s] 第%d条 %d 字符（%d 字节）",
                     cat, i, len(text), len(text.encode("utf-8")))

    token = get_access_token(app_id, app_secret)
    failed = 0
    for openid in openids:
        for texts in reports.values():
            for text in texts:
                try:
                    send(token, openid, text)
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    log.error("推送给 %s 失败: %s", openid, exc)

    log.info("推送完成: %d/%d 成功", len(openids) * total_msgs - failed, len(openids) * total_msgs)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
