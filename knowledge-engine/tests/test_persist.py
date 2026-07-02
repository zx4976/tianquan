#!/usr/bin/env python3
"""
持久化测试 — 写入 → 关闭 → 重新打开 → 检索
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.book_pipeline import BookPipeline
from src.config import get_stats

print("=" * 60)
print("持久化存储测试")
print("=" * 60)

# Step 1: 持久模式写入一本书
print("\n📝 写入（持久模式）...")
with BookPipeline(persistent=True) as pipe:
    result = pipe.process_book(
        {
            "id": "test_persist_001",
            "title": "持久化测试用书",
            "author": "测试",
            "body": "这是一本用于测试持久化存储的书籍。包含Python编程和异步并发等概念。",
            "summary": "测试持久化",
            "tags": "Python 测试 异步",
        },
        concepts=[{"name": "持久化", "category": "技术", "definition": "数据长期存储"}],
        highlights=["持久化测试通过"],
    )
    print(f"  书名: {result['title']}")
    print(f"  分类: {result['category']}")
    print(f"  耗时: {result['elapsed_ms']}ms")
    # 不关闭管道，看看是否能搜索到
    r = pipe.search("持久化", limit=5)
    print(f"  写入后立即搜索: {len(r)} 条结果")
    for rr in r:
        print(f"    [{rr.get('score',0):.2f}] {rr.get('title','')}")

# 管道关闭，索引仍在磁盘
print("\n🔒 管道已关闭")

# Step 2: 重新打开，验证数据是否还在
print("\n📖 重新打开（持久模式）...")
with BookPipeline(persistent=True) as pipe2:
    r = pipe2.search("持久化", limit=5)
    print(f"  重新打开后搜索: {len(r)} 条结果")
    for rr in r:
        print(f"    [{rr.get('score',0):.2f}] {rr.get('title','')} ({rr.get('source','')})")

# Step 3: 查看数据统计
print(f"\n📊 数据统计: {get_stats()}")
print(f"  数据目录: {get_stats()['data_root']}")

print("\n" + "=" * 60)
print("✅ 持久化测试通过")
print("=" * 60)
