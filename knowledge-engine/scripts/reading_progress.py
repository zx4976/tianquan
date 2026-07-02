#!/usr/bin/env python3
"""
读书进度查询 — 可视化进度条

用法:
  python3 scripts/reading_progress.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.understanding import Understanding

u = Understanding()
stats = u.reading_stats()

total = stats['总']
read = stats['已读']
unread = stats['未读']
pct = read / total * 100 if total > 0 else 0

bar_len = 30
filled = max(1, int(bar_len * pct / 100)) if read > 0 else 0
bar = '█' * filled + '░' * (bar_len - filled)

print(f"\n📚 隐光读书进度")
print(f"  ┌{'─' * (bar_len + 2)}┐")
print(f"  │ {bar} │")
print(f"  └{'─' * (bar_len + 2)}┘")
print(f"  {read}/{total} 本 ({pct:.1f}%)")
print(f"  {'─' * 20}")
print(f"  已读: {read} 本")
print(f"  未读: {unread} 本")

# 当前在读（如果有）
if unread > 0:
    print(f"\n  下一本: {u.get_unread_books(1)[0]['title'][:50]}")

# 已读清单（最近5本）
if read > 0:
    recent = u.get_read_books(5)
    print(f"\n  最近已读:")
    for b in recent:
        print(f"    ✅ {b['title'][:55]}")
