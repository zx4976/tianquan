#!/usr/bin/env python3
"""Kùzu 多概念检索调试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.kuzu_graph import KnowledgeGraph

with KnowledgeGraph().create_in_memory() as kg:
    kg.add_book("1", "流畅的Python", "LR", "编程语言", 2015)
    kg.add_book("2", "Python并发编程", "V", "编程语言", 2020)

    kg.add_concept("py", "Python", "编程语言")
    kg.add_concept("async", "异步编程", "编程范式")
    kg.add_concept("concur", "并发", "编程范式")

    kg.add_covers("1", "py", 3, 0.9)
    kg.add_covers("1", "async", 2, 0.8)
    kg.add_covers("2", "py", 1, 0.5)
    kg.add_covers("2", "async", 3, 0.9)
    kg.add_covers("2", "concur", 3, 0.9)

    # 测试单概念
    print("单概念 'Python':")
    for b in kg.search_books_by_concept("Python"):
        print(f"  {b['title']}")
    
    # 测试多概念
    print("多概念 ['Python', '异步编程']:")
    for b in kg.search_books_by_multi_concept(["Python", "异步编程"]):
        print(f"  {b['title']}")

    # 直接 Cypher 查询看看
    print("直接查询:")
    r = kg.conn.execute(
        "MATCH (b:Book)-[:COVERS]->(c1:Concept {name: 'Python'}), "
        "(b)-[:COVERS]->(c2:Concept {name: '异步编程'}) "
        "RETURN b.title, b.book_id"
    )
    while r.has_next():
        print(f"  {r.get_next()}")
