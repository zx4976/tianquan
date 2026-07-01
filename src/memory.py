#!/usr/bin/env python3
"""
隐光记忆 + 会话快照系统

记忆: 结构化事实存储，时间轴感知
快照: 每轮对话结束时自动保存，重启后自动恢复上下文
"""
import sqlite3
import os
import json
import time
import uuid
from datetime import datetime, timedelta

MEMORY_DB = os.path.expanduser("~/.hermes/memory.db")


class Memory:
    def __init__(self, db_path=MEMORY_DB):
        self.db_path = db_path
        self._init_db()

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
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,
                start_time REAL,
                end_time REAL,
                summary TEXT,
                key_points TEXT,
                memory_ids TEXT,
                turn_count INTEGER DEFAULT 0,
                importance INTEGER DEFAULT 1
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_timestamp ON memories(timestamp DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_time ON snapshots(end_time DESC)")
        conn.commit()
        conn.close()

    # ─── 基础记忆 ─────────────────────────────────

    def remember(self, content, category="general", importance=1, tags=""):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO memories (content, category, importance, timestamp, tags) VALUES (?, ?, ?, ?, ?)",
            (content, category, importance, time.time(), tags)
        )
        conn.commit()
        id_ = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return id_

    def recall(self, query, limit=10, min_importance=0, since=None, before=None):
        conn = sqlite3.connect(self.db_path)
        conditions = []
        params = []
        for w in query.split():
            if len(w) > 1:
                conditions.append("content LIKE ?")
                params.append(f"%{w}%")
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)
        if before:
            conditions.append("timestamp < ?")
            params.append(before)
        sql = "SELECT id, content, category, importance, timestamp, access_count, tags FROM memories"
        if conditions:
            sql += " WHERE "
            if min_importance > 0:
                sql += f"importance >= {min_importance} AND "
            sql += " OR ".join(conditions) if query.strip() else " AND ".join(conditions)
        elif min_importance > 0:
            sql += f" WHERE importance >= {min_importance}"
        sql += " ORDER BY importance DESC, timestamp DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        results = []
        for row in rows:
            results.append({
                'id': row[0], 'content': row[1], 'category': row[2],
                'importance': row[3], 'timestamp': row[4],
                'access_count': row[5], 'tags': row[6],
                'time_str': self._format_time(row[4]),
            })
            conn.execute("UPDATE memories SET access_count = access_count + 1, last_access = ? WHERE id = ?",
                        (time.time(), row[0]))
        conn.commit()
        conn.close()
        return results

    def timeline(self, hours=24, limit=20):
        since = time.time() - hours * 3600
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT id, content, category, importance, timestamp, tags FROM memories "
            "WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT ?", (since, limit)
        ).fetchall()
        conn.close()
        return [{'id': r[0], 'content': r[1], 'category': r[2],
                 'importance': r[3], 'timestamp': r[4], 'tags': r[5],
                 'time_str': self._format_time(r[4])} for r in rows]

    def today(self):
        return self.timeline(hours=24, limit=50)

    # ─── 会话快照 ─────────────────────────────────

    def save_snapshot(self, session_id=None, key_points=None, turn_count=0):
        """保存当前会话快照"""
        session_id = session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        now = time.time()
        key_points = key_points or []
        memory_ids = []

        # 将关键点存入记忆表
        for kp in key_points:
            content = kp.get('content', '')
            imp = kp.get('importance', 5)
            cat = kp.get('category', 'general')
            mid = self.remember(content, cat, imp, tags='snapshot')
            memory_ids.append(mid)

        # 生成摘要
        summary = kp['content'][:80] if key_points else "无关键信息"

        # 保存快照
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO snapshots
            (session_id, start_time, end_time, summary, key_points, memory_ids, turn_count, importance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, now - 3600, now, summary,
            json.dumps(key_points, ensure_ascii=False),
            json.dumps(memory_ids), turn_count,
            max([kp.get('importance', 1) for kp in key_points], default=1)
        ))
        conn.commit()
        conn.close()
        return session_id

    def get_snapshot(self, session_id=None):
        """获取最近一个或指定会话快照"""
        conn = sqlite3.connect(self.db_path)
        if session_id:
            rows = conn.execute(
                "SELECT * FROM snapshots WHERE session_id = ?", (session_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM snapshots ORDER BY end_time DESC LIMIT 3"
            ).fetchall()
        conn.close()
        results = []
        for row in rows:
            results.append({
                'id': row[0], 'session_id': row[1],
                'start_time': row[2], 'end_time': row[3],
                'summary': row[4],
                'key_points': json.loads(row[5]) if row[5] else [],
                'memory_ids': json.loads(row[6]) if row[6] else [],
                'turn_count': row[7], 'importance': row[8],
                'time_str': self._format_time(row[3]),
            })
        return results

    def load_last_context(self, max_items=5):
        """新会话启动时调用：加载上次的上下文"""
        snapshots = self.get_snapshot()
        if not snapshots:
            return "这是你与隐光的第一次对话。"

        context = []
        for snap in snapshots[:3]:
            lines = [f"【{snap['time_str']}】{snap['summary']}"]
            for kp in snap['key_points'][:max_items]:
                lines.append(f"  · {kp.get('content', '')}")
            context.append('\n'.join(lines))
        return '\n\n'.join(context)

    def forget(self, memory_id=None, category=None, older_than_days=0):
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
        conn = sqlite3.connect(self.db_path)
        mem = conn.execute("SELECT count(*) FROM memories").fetchone()[0]
        snap = conn.execute("SELECT count(*) FROM snapshots").fetchone()[0]
        by_cat = conn.execute(
            "SELECT category, count(*) FROM memories GROUP BY category ORDER BY count(*) DESC"
        ).fetchall()
        conn.close()
        return {
            'total_memories': mem,
            'total_snapshots': snap,
            'by_category': dict(by_cat),
        }

    @staticmethod
    def _format_time(ts):
        if not ts:
            return "未知时间"
        dt = datetime.fromtimestamp(ts)
        now = datetime.now()
        hour = dt.hour
        if hour < 6: period = "凌晨"
        elif hour < 9: period = "早上"
        elif hour < 12: period = "上午"
        elif hour < 14: period = "中午"
        elif hour < 18: period = "下午"
        else: period = "晚上"
        if dt.date() == now.date():
            date_str = "今天"
        elif (now.date() - dt.date()).days == 1:
            date_str = "昨天"
        elif dt.year == now.year:
            date_str = dt.strftime("%m月%d日")
        else:
            date_str = dt.strftime("%Y年%m月%d日")
        return f"{date_str}{period} {dt.hour:02d}:{dt.minute:02d}"


if __name__ == '__main__':
    m = Memory()
    # 测试快照
    sid = m.save_snapshot("test_session_001", [
        {'content': '煦林让我设计会话快照系统', 'importance': 9, 'category': 'project'},
        {'content': '需求：跨会话记得上次对话', 'importance': 8, 'category': 'requirement'},
    ], turn_count=5)
    print(f"快照已保存: {sid}")
    ctx = m.load_last_context(max_items=5)
    print(f"恢复的上下文:\n{ctx}")
    print(f"\n统计: {m.stats()}")
