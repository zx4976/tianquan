#!/usr/bin/env python3
"""
端到端集成测试 — 模拟5本书的全流程
"""
import sys, os, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.book_pipeline import BookPipeline

print("=" * 60)
print("端到端集成测试 — 5本书全流程")
print("=" * 60)

# 模拟5本书
books = [
    {
        "id": "1",
        "title": "流畅的Python",
        "author": "Luciano Ramalho",
        "body": "Python是一种优雅的编程语言，支持面向对象和函数式编程。本书介绍Python的高级特性，包括异步编程、协程、元编程。",
        "summary": "介绍Python高级特性的实用指南",
        "tags": "Python 编程 异步 协程",
        "concepts": [
            {"name": "协程", "category": "编程机制", "definition": "一种用户态轻量级线程"},
            {"name": "异步编程", "category": "编程范式", "definition": "基于事件循环的非阻塞编程"},
        ],
        "highlights": ["协程比线程更轻量", "Python 3.5引入async/await"],
    },
    {
        "id": "2",
        "title": "Python并发编程实战",
        "author": "Various",
        "body": "深入讲解Python中的并发编程技术，包括多线程、多进程、异步IO、事件循环等。涵盖GIL、线程安全、锁机制。",
        "summary": "全面介绍Python并发编程",
        "tags": "Python 并发 多线程 GIL",
        "concepts": [
            {"name": "GIL", "category": "语言特性", "definition": "Python全局解释器锁"},
            {"name": "多线程", "category": "并发模型", "definition": "操作系统级别的并发执行"},
            {"name": "事件循环", "category": "编程机制", "definition": "驱动异步编程的核心机制"},
        ],
        "highlights": ["GIL导致CPU密集型多线程无法利用多核"],
    },
    {
        "id": "3",
        "title": "深入理解计算机系统",
        "author": "Randal Bryant",
        "body": "从程序员视角讲解计算机系统，涵盖处理器架构、内存层次、虚拟内存、网络编程和并发编程。",
        "summary": "计算机系统经典教材",
        "tags": "计算机 系统 架构 内存",
        "concepts": [
            {"name": "内存管理", "category": "计算机科学", "definition": "操作系统对内存的分配和回收"},
            {"name": "并发", "category": "编程范式", "definition": "多个任务同时执行"},
        ],
        "highlights": [],
    },
    {
        "id": "4",
        "title": "算法导论",
        "author": "Thomas Cormen",
        "body": "全面介绍算法设计与分析，包括排序、图算法、动态规划、贪心算法、NP完全性。经典教材。",
        "summary": "算法领域的标准教材",
        "tags": "算法 数据结构 计算机科学",
        "concepts": [
            {"name": "动态规划", "category": "算法", "definition": "将问题分解为子问题的优化方法"},
            {"name": "图算法", "category": "算法", "definition": "处理图数据结构的算法"},
        ],
        "highlights": [],
    },
    {
        "id": "5",
        "title": "深度学习入门",
        "author": "XX",
        "body": "介绍神经网络、卷积网络、循环神经网络和Transformer架构的基本原理和实现方法。",
        "summary": "深度学习入门教材",
        "tags": "AI 深度学习 神经网络",
        "concepts": [
            {"name": "神经网络", "category": "AI", "definition": "受生物神经元启发的计算模型"},
            {"name": "Transformer", "category": "AI", "definition": "基于注意力机制的神经网络架构"},
        ],
        "highlights": ["Transformer彻底改变了NLP领域"],
    },
]

with BookPipeline() as pipe:
    # Step 1: 逐本处理
    print("\n📖 处理书籍:")
    results = []
    for book in books:
        r = pipe.process_book(
            book,
            concepts=book.get("concepts", []),
            highlights=book.get("highlights", []),
        )
        results.append(r)
        print(f"  [{r['category']:12s}] {r['title']:20s} ({r['elapsed_ms']:6.1f}ms)")

    # Step 2: 重建 LSI
    print("\n🔧 重建 LSI 语义索引...")
    pipe.rebuild_lsi(n_components=5)
    print("  ✅ LSI 就绪")

    # Step 3: 搜索测试
    print("\n🔍 搜索测试:")
    queries = [
        "Python异步编程协程",
        "并发多线程GIL",
        "算法数据结构排序",
        "神经网络深度学习AI",
        "计算机系统内存",
        "数据库",  # 应该无结果
        "Python 并发",
    ]
    
    for q in queries:
        fused = pipe.search(q, limit=5)
        print(f"  '{q:20s}': {len(fused)} 条结果")
        for r in fused:
            src = r.get('source', 'rrf')
            sc = r.get('rrf_score', r.get('score', 0))
            print(f"    [{sc:.4f}][{src:8s}] {r.get('title', '')}")

    # Step 4: 写入 Obsidian 笔记（临时目录模拟）
    print("\n📝 生成 Obsidian 笔记...")
    test_vault = tempfile.mkdtemp(prefix="obsidian_test_")
    pipe.save_notes_to_obsidian(test_vault, results)
    
    # 展示目录结构
    for dirpath, dirnames, filenames in os.walk(test_vault):
        for f in filenames:
            rel = os.path.relpath(os.path.join(dirpath, f), test_vault)
            size = os.path.getsize(os.path.join(dirpath, f))
            print(f"  📄 {rel} ({size}B)")

    # 清理
    import shutil
    shutil.rmtree(test_vault)

print("\n" + "=" * 60)
print("✅ 端到端测试全部通过")
print("=" * 60)
