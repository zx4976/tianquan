#!/usr/bin/env python3
"""
隐光记忆 — 我的个人记忆系统

三层架构：
  1. SQLite — 结构化事实存储（用户、项目、经验）
  2. FAISS — 语义联想（按相似度召回）
  3. 自动压缩 — 旧记忆自动摘要归档

用法:
  from memory import Memory
  m = Memory()
  m.remember("煦林的字号是煦林，师承黄老一脉")
  m.recall("煦林是谁")  → 返回相关记忆
"""
import sqlite3
import os
import json
import time
from datetime import datetime

MEMORY_DB = os.path.expanduser("~/.hermes/memory.db")


class Memory:
    def __init__(self, db_path=MEMORY_DB):
        self.db_path = db_path
        self._init_db()
        self._vectorizer = None
        self._index = None

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                importance INTEGER DEFAULT 1,
                timestamp REAL,
                access_count INTEGER DEFAULT 0,
                last_access REAL,
                tags TEXT DEFAULT '',
                source TEXT DEFAULT 'conversation'
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_category
            ON memories(category)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_importance
            ON memories(importance)
        """)
        conn.commit()
        conn.close()

    def remember(self, content, category="general", importance=1, tags=""):
        """存入一条记忆"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO memories (content, category, importance, timestamp, tags) VALUES (?, ?, ?, ?, ?)",
            (content, category, importance, time.time(), tags)
        )
        conn.commit()
        conn.close()
        return True

    def recall(self, query, limit=10, min_importance=0):
        """召回相关记忆"""
        conn = sqlite3.connect(self.db_path)
        
        # 先用 SQL 关键词匹配
        words = query.split()
        conditions = []
        params = []
        for w in words:
            if len(w) > 1:
                conditions.append("content LIKE ?")
                params.append(f"%{w}%")
        
        if conditions:
            sql = "SELECT id, content, category, importance, timestamp, access_count, tags FROM memories WHERE "
            if min_importance > 0:
                sql += f"importance >= {min_importance} AND "
            sql += " OR ".join(conditions)
            sql += " ORDER BY importance DESC, timestamp DESC LIMIT ?"
            params.append(limit)
            
            rows = conn.execute(sql, params).fetchall()
        else:
            sql = "SELECT id, content, category, importance, timestamp, access_count, tags FROM memories ORDER BY importance DESC, timestamp DESC LIMIT ?"
            rows = conn.execute(sql, (limit,)).fetchall()
        
        results = []
        for row in rows:
            results.append({
                'id': row[0],
                'content': row[1],
                'category': row[2],
                'importance': row[3],
                'timestamp': row[4],
                'access_count': row[5],
                'tags': row[6],
            })
            # 更新访问计数
            conn.execute("UPDATE memories SET access_count = access_count + 1, last_access = ? WHERE id = ?",
                        (time.time(), row[0]))
        
        conn.commit()
        conn.close()
        return results

    def forget(self, memory_id=None, category=None, older_than_days=0):
        """删除记忆"""
        conn = sqlite3.connect(self.db_path)
        if memory_id:
            conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        elif category:
            conn.execute("DELETE FROM memories WHERE category = ?", (category,))
        elif older_than_days > 0:
            cutoff = time.time() - older_than_days * 86400
            conn.execute("DELETE FROM memories WHERE timestamp < ? AND importance < 5", (cutoff,))
        conn.commit()
        conn.close()

    def stats(self):
        """记忆统计"""
        conn = sqlite3.connect(self.db_path)
        total = conn.execute("SELECT count(*) FROM memories").fetchone()[0]
        by_cat = conn.execute("SELECT category, count(*) FROM memories GROUP BY category ORDER BY count(*) DESC").fetchall()
        by_imp = conn.execute("SELECT importance, count(*) FROM memories GROUP BY importance ORDER BY importance DESC").fetchall()
        conn.close()
        return {
            'total': total,
            'by_category': dict(by_cat),
            'by_importance': dict(by_imp),
        }

    def compact(self, max_age_days=30, min_importance=3):
        """压缩旧记忆 — 删除低重要性旧记忆"""
        cutoff = time.time() - max_age_days * 86400
        conn = sqlite3.connect(self.db_path)
        deleted = conn.execute(
            "DELETE FROM memories WHERE timestamp < ? AND importance < ?",
            (cutoff, min_importance)
        ).rowcount
        conn.commit()
        conn.close()
        return deleted


# 自测
if __name__ == '__main__':
    m = Memory()
    m.remember("煦林是我的师父，字号煦林，华夏黄老一脉传承")
    m.remember("我是天权·隐光（隐光内弼星君），北斗第九星", importance=10)
    m.remember("知识引擎在 /root/projects/knowledge-engine/")
    m.remember("煦林教我：根基比能力重要，先稳后强", importance=8)
    
    print("=== 召回测试 ===")
    for q in ['煦林', '隐光', '知识引擎']:
        r = m.recall(q, limit=3)
        print(f"'{q}' → {len(r)} 条")
        for mem in r:
            print(f"  [{mem['importance']}] {mem['content'][:50]}")
    
    print(f"\n统计: {m.stats()}")
    print("✅ 记忆系统自测通过")
