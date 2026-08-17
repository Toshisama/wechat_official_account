"""新闻链接有效性检查：并发 HEAD/GET 验证各源链接，找出失效源。

用法：python scripts/check_links.py [--sample 20]
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "src")

import requests
import sources

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}


def check(url: str, timeout: float = 10.0) -> tuple[str, int | None, str]:
    """HEAD 优先（快），403/405 时降级 GET 只读响应头。返回 (url, status, error)。"""
    last_err = ""
    for method in ("HEAD", "GET"):
        try:
            resp = requests.request(
                method, url, headers=HEADERS, timeout=timeout,
                allow_redirects=True, stream=True,
            )
            if resp.status_code in (403, 405, 404) and method == "HEAD":
                continue  # 403/404 用 GET 复验，排除反爬误判
            return url, resp.status_code, ""
        except requests.RequestException as exc:
            last_err = f"{method} {type(exc).__name__}: {str(exc)[:60]}"
    return url, None, last_err or "both HEAD/GET failed"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=20, help="每源取样条数")
    args = parser.parse_args()

    items: list[sources.NewsItem] = []
    for name, (fetcher, cat) in sources.FETCHERS.items():
        try:
            items.extend(fetcher())
        except Exception as exc:  # noqa: BLE001
            print(f"[跳过] {name}: {exc}")

    # 按源分组，每源取样
    from collections import defaultdict
    by_source: dict[str, list[sources.NewsItem]] = defaultdict(list)
    for it in items:
        by_source[it.source].append(it)

    total_bad = 0
    for source, its in by_source.items():
        sample = its[: args.sample]
        links = [(it.url, it) for it in sample if it.url]
        if not links:
            print(f"[{source}] 无链接（{len(its)} 条）")
            continue
        results: list[tuple[int | None, str]] = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(check, url): url for url, _ in links}
            for f in as_completed(futures):
                _url, status, err = f.result()
                results.append((status, err))
        # 404/410 = 真失效；异常（SSL 断连等）= 可能反爬拦截，用户端可访问
        bad = [r for r in results if r[0] in (404, 410)]
        blocked = [r for r in results if r[0] is None and "SSL" in r[1]]
        total_bad += len(bad)
        ok = len(results) - len(bad) - len(blocked)
        print(f"[{source}] {ok}/{len(results)} 有效" + (f"，{len(blocked)} 条反爬拦截(用户可访问)" if blocked else ""))
        for (status, err), (_url, it) in zip(results, links):
            if status in (404, 410):
                print(f"    ✗ [{status}] {it.title[:30]} -> {it.url[:70]}")
            elif status is None and "SSL" not in (err or ""):
                print(f"    ✗ [{err}] {it.title[:30]} -> {it.url[:70]}")
    print(f"\n总计失效 {total_bad} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
