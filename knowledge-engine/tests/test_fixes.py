#!/usr/bin/env python3
"""
限制修复验证 — 分类修正 + PDF导入 + LSI持久化
"""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.book_pipeline import classify_book, BookPipeline
from src.config import get_stats

print("=" * 60)
print("限制修复验证")
print("=" * 60)

# 1️⃣ 分类修正验证
print("\n1️⃣ 分类修正验证:")
tests = [
    ("深入理解计算机系统", "从程序员视角讲解计算机系统，涵盖处理器架构、内存层次", "",
     "计算机科学"),
    ("流畅的Python", "Python是一种优雅的编程语言，支持异步编程", "",
     "编程语言"),
    ("算法导论", "介绍排序、图算法、动态规划等经典算法", "",
     "计算机科学"),
    ("Python并发编程实战", "深入讲解多线程多进程异步IO等并发技术", "",
     "编程语言"),
    ("深度学习入门", "介绍神经网络、卷积网络、Transformer", "",
     "AI机器学习"),
]

for title, body, tags, expected in tests:
    cat, sub, score = classify_book(title, body, tags)
    status = "✅" if cat == expected else "❌"
    print(f"  {status} 《{title[:15]:15s}》 → {cat:12s} (期望:{expected})  sub={sub}")

# 2️⃣ PDF 导入测试
print("\n2️⃣ PDF 导入测试:")
# 验证 pypdf 可导入
from pypdf import PdfWriter
print(f"  pypdf {__import__('pypdf').__version__} 已就绪 ✅")
print(f"  使用方式: from pypdf import PdfReader; reader = PdfReader('file.pdf'); text = ''.join(p.extract_text() for p in reader.pages)")

# 3️⃣ LSI 持久化验证
print("\n3️⃣ LSI 持久化验证:")
with BookPipeline(persistent=True) as pipe:
    pipe.process_book({
        "id": "lsi_test",
        "title": "LSI持久化测试",
        "author": "test",
        "body": "测试语义索引的持久化功能是否正常工作",
        "tags": "测试 LSI",
    })
    pipe.rebuild_lsi(n_components=2)
    print(f"  写入后 LSI 可搜索:", end="")
    r = pipe.lsi.search("语义索引持久化", top_k=3)
    for rr in r:
        print(f" [{rr['score']:.4f}]{rr['title']}", end="")
    print()

# 关闭后重新打开，验证 LSI 是否还在
print("  关闭后重开...", end="")
with BookPipeline(persistent=True) as pipe2:
    if pipe2.lsi and pipe2.lsi.is_built:
        r = pipe2.lsi.search("语义索引持久化", top_k=3)
        if r:
            print(f" ✅ LSI 持久化有效 [{r[0]['score']:.4f}]{r[0]['title']}")
        else:
            print(" ⚠️ LSI 加载了但搜索无结果")
    else:
        print(" ❌ LSI 未加载")

# 统计
print(f"\n📊 数据统计: {get_stats()}")

print("\n" + "=" * 60)
print("验证完成")
print("=" * 60)
