"""新闻源连通性探测：逐个源拉取并打印条目数、时间范围、前 3 条标题。

用法：python scripts/probe_sources.py
目的：实施时实测各源，失效源在 src/sources.py 的 FETCHERS 中替换。
"""
from __future__ import annotations

import os
import sys

# Windows 控制台默认 GBK，强制 UTF-8 以支持 emoji 输出
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import sources
from formatter import filter_recent


def main() -> int:
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    print(f"当前 UTC 时间: {now:%Y-%m-%d %H:%M}")
    all_ok = True
    for name, (fetcher, cat) in sources.FETCHERS.items():
        label = sources.CATEGORY_LABELS[cat]
        try:
            items = fetcher()
            if not items:
                print(f"[❌] {name}（{label}）: 0 条")
                all_ok = False
                continue
            recent = filter_recent(items, now)
            times = [it.pub_time for it in items if it.pub_time]
            t_range = (
                f"{min(times):%m-%d %H:%M} ~ {max(times):%m-%d %H:%M} UTC" if times else "无时间字段"
            )
            print(f"[✅] {name}（{label}）: {len(items)} 条，近 24h 内 {len(recent)} 条，时间 {t_range}")
            for it in items[:3]:
                print(f"     - {it.title[:40]}（{it.source}）")
        except Exception as exc:  # noqa: BLE001
            print(f"[❌] {name}（{label}）: {type(exc).__name__}: {exc}")
            all_ok = False
    print("\n结论: 全部可用" if all_ok else "\n结论: 存在失效源，需在 sources.py 中替换")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
