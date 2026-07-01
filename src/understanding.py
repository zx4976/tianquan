#!/usr/bin/env python3
"""
书籍理解存储模块 — 第3层：读进去的理解

与对话记忆分离，专门存储：
  - 书的基本信息（标题/作者/篇幅）
  - 结构（章节目录）
  - 核心概念（概念名 + 我的理解）
  - 跨书关联（同一概念在不同书中的不同阐述）
  - 我的读后感/理解摘要
"""
import sqlite3
import os
import json
import time
from datetime import datetime

UNDERSTANDING_DB = os.path.expanduser("~/.hermes/understanding.db")


class Understanding:
    def __init__(self, db_path=UNDERSTANDING_DB):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        # 书籍主表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT DEFAULT '',
                language TEXT DEFAULT 'zh',
                word_count INTEGER DEFAULT 0,
                read_at REAL,
                status TEXT DEFAULT '未读'
            )
        """)
        # 理解记录
        conn.execute("""
            CREATE TABLE IF NOT EXISTS comprehensions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id TEXT,
                dimension TEXT,
                content TEXT,
                importance INTEGER DEFAULT 5,
                created_at REAL,
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
        """)
        # 概念提取
        conn.execute("""
            CREATE TABLE IF NOT EXISTS concepts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                first_seen_in TEXT DEFAULT '',
                created_at REAL
            )
        """)
        # 概念→书籍关联（同一概念出现在哪些书里）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS book_concepts (
                concept_id INTEGER,
                book_id TEXT,
                context TEXT DEFAULT '',
                depth TEXT DEFAULT '提及',
                PRIMARY KEY (concept_id, book_id),
                FOREIGN KEY (concept_id) REFERENCES concepts(id),
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
        """)
        # 跨书关联（同一概念在不同书中的不同说法）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cross_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                concept TEXT,
                book_a TEXT,
                book_b TEXT,
                insight TEXT,
                created_at REAL
            )
        """)
        conn.commit()
        conn.close()

    def register_book(self, book_id, title, author="", language="zh", word_count=0):
        """登记一本书"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO books (id, title, author, language, word_count, read_at, status)
            VALUES (?, ?, ?, ?, ?, ?, '已索引')
        """, (book_id, title, author, language, word_count, time.time()))
        conn.commit()
        conn.close()

    def mark_read(self, book_id):
        """标记为已读"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE books SET status='已读', read_at=? WHERE id=?", (time.time(), book_id))
        conn.commit()
        conn.close()

    def add_comprehension(self, book_id, dimension, content, importance=5):
        """添加一条理解记录"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO comprehensions (book_id, dimension, content, importance, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (book_id, dimension, content, importance, time.time()))
        conn.commit()
        conn.close()

    def add_concept(self, name, category="", summary="", first_book=""):
        """添加一个从书中学到的概念"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR IGNORE INTO concepts (name, category, summary, first_seen_in, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (name, category, summary, first_book, time.time()))
        conn.commit()
        r = conn.execute("SELECT id FROM concepts WHERE name=?", (name,)).fetchone()
        conn.close()
        return r[0] if r else None

    def link_concept_to_book(self, concept_id, book_id, context="", depth="提及"):
        """链接概念到书籍"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO book_concepts (concept_id, book_id, context, depth)
            VALUES (?, ?, ?, ?)
        """, (concept_id, book_id, context, depth))
        conn.commit()
        conn.close()

    def add_cross_link(self, concept, book_a, book_b, insight):
        """记录跨书关联发现"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO cross_links (concept, book_a, book_b, insight, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (concept, book_a, book_b, insight, time.time()))
        conn.commit()
        conn.close()

    def get_book(self, book_id):
        """获取一本书的信息"""
        conn = sqlite3.connect(self.db_path)
        r = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
        conn.close()
        if r:
            return {'id': r[0], 'title': r[1], 'author': r[2],
                    'language': r[3], 'word_count': r[4], 'status': r[6]}
        return None

    def get_comprehensions(self, book_id):
        """获取一本书的理解记录"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT dimension, content, importance FROM comprehensions WHERE book_id=? ORDER BY importance DESC",
            (book_id,)
        ).fetchall()
        conn.close()
        return [{'dimension': r[0], 'content': r[1], 'importance': r[2]} for r in rows]

    def get_concepts_for_book(self, book_id):
        """获取一本书涉及的概念"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT c.name, bc.context, bc.depth
            FROM book_concepts bc JOIN concepts c ON bc.concept_id = c.id
            WHERE bc.book_id=? ORDER BY bc.depth
        """, (book_id,)).fetchall()
        conn.close()
        return [{'name': r[0], 'context': r[1], 'depth': r[2]} for r in rows]

    def stats(self):
        """统计"""
        conn = sqlite3.connect(self.db_path)
        books = conn.execute("SELECT count(*) FROM books").fetchone()[0]
        read = conn.execute("SELECT count(*) FROM books WHERE status='已读'").fetchone()[0]
        comps = conn.execute("SELECT count(*) FROM comprehensions").fetchone()[0]
        concs = conn.execute("SELECT count(*) FROM concepts").fetchone()[0]
        links = conn.execute("SELECT count(*) FROM cross_links").fetchone()[0]
        conn.close()
        return {
            'books': books, '已读': read, '理解条目': comps,
            '概念': concs, '跨书关联': links,
        }


if __name__ == '__main__':
    u = Understanding()
    # 演示：为微积分五讲建立理解记录
    u.register_book('shelf_18', '微积分五讲', '龚昇', 'zh', 161411)
    u.add_comprehension('shelf_18', '主旨', '用矛盾论观点重新审视微积分，微分与积分是主要矛盾', 9)
    u.add_comprehension('shelf_18', '核心定理', 'Stokes公式(*)统一格林/高斯/斯托克斯三定理，揭示高维空间微积分矛盾', 9)
    u.add_comprehension('shelf_18', '结构', '5讲:回顾→三组成部分→各种矛盾→发展阶段→严格化之后', 8)
    u.add_comprehension('shelf_18', '独特维度', '用列宁毛泽东矛盾论阐释微积分基本定理', 7)
    
    # 添加概念
    c1 = u.add_concept('Stokes公式', '微积分', '统一格林高斯斯托克斯的核心定理', '微积分五讲')
    c2 = u.add_concept('外微分形式', '微积分', '理解高维空间微积分的关键工具', '微积分五讲')
    c3 = u.add_concept('微分与积分矛盾', '微积分', '微积分学科的主要矛盾', '微积分五讲')
    u.link_concept_to_book(c1, 'shelf_18', 'Stokes公式(*)是微积分基本定理的高维推广', '核心')
    u.link_concept_to_book(c2, 'shelf_18', '外微分形式说清楚高维空间微分与积分如何成为一对矛盾', '核心')
    u.link_concept_to_book(c3, 'shelf_18', '全书主线：微分与积分是主要矛盾', '主线')
    
    print(f"📊 理解系统测试:")
    print(f"  {u.stats()}")
    print(f"\n📖 微积分五讲的理解:")
    for c in u.get_comprehensions('shelf_18'):
        print(f"  [{c['importance']}] {c['dimension']}: {c['content']}")
    print(f"\n🔗 涉及概念:")
    for c in u.get_concepts_for_book('shelf_18'):
        print(f"  {c['name']} ({c['depth']})")
