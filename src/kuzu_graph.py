#!/usr/bin/env python3
"""
Kùzu 知识图谱层 — 概念关系与跨书关联
"""
import kuzu
import os
import shutil
import tempfile


class KnowledgeGraph:
    """知识图谱 — 基于 Kùzu 的概念关系网络"""

    def __init__(self, db_path=None):
        self.db_path = db_path
        self.db = None
        self.conn = None
        self._temp_dir = None

        if db_path:
            self._open_or_create(db_path)

    def _ensure_parent_dir(self, path):
        parent = os.path.dirname(path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)

    def _open_or_create(self, path):
        self._ensure_parent_dir(path)
        
        # Kùzu 需要路径的父目录存在，但路径本身不能是存在的目录
        # 如果已经存在是文件路径或不存在，都行
        self.db = kuzu.Database(str(path))
        self.conn = kuzu.Connection(self.db)
        self._ensure_schema()

    def create_in_memory(self):
        """创建内存数据库（测试用）"""
        self._temp_dir = tempfile.mkdtemp(prefix="kuzu_kg_")
        db_file = os.path.join(self._temp_dir, "knowledge.db")
        self.db = kuzu.Database(db_file)
        self.conn = kuzu.Connection(self.db)
        self._ensure_schema()
        return self

    def _ensure_schema(self):
        """确保所有表和索引存在（幂等）"""
        # Book 节点
        try:
            self.conn.execute(
                "CREATE NODE TABLE IF NOT EXISTS Book ("
                "  book_id STRING, title STRING, author STRING, "
                "  category STRING, year INT64, "
                "  PRIMARY KEY (book_id)"
                ")"
            )
        except RuntimeError:
            pass  # 表可能已存在

        # Concept 节点
        try:
            self.conn.execute(
                "CREATE NODE TABLE IF NOT EXISTS Concept ("
                "  concept_id STRING, name STRING, category STRING, "
                "  PRIMARY KEY (concept_id)"
                ")"
            )
        except RuntimeError:
            pass

        # 关系: 书→概念
        try:
            self.conn.execute(
                "CREATE REL TABLE IF NOT EXISTS COVERS ("
                "  FROM Book TO Concept, depth INT64, relevance DOUBLE, weight INT64"
                ")"
            )
        except RuntimeError:
            pass
    
        # 关系: 概念→概念
        try:
            self.conn.execute(
                "CREATE REL TABLE IF NOT EXISTS RELATED_TO ("
                "  FROM Concept TO Concept, relation STRING, strength DOUBLE, weight INT64"
                ")"
            )
        except RuntimeError:
            pass

        # 关系: 书→书（引用/关联）
        try:
            self.conn.execute(
                "CREATE REL TABLE IF NOT EXISTS REFERENCES_BOOK ("
                "  FROM Book TO Book, relation STRING"
                ")"
            )
        except RuntimeError:
            pass

    def add_book(self, book_id, title, author="", category="", year=0):
        """添加书籍节点"""
        if not self.conn:
            raise RuntimeError("图数据库未初始化")
        
        safe_title = title.replace("'", "''")
        safe_author = author.replace("'", "''")
        safe_category = category.replace("'", "''")
        
        try:
            self.conn.execute(
                f"MERGE (b:Book {{book_id: '{book_id}'}}) "
                f"SET b.title = '{safe_title}', "
                f"b.author = '{safe_author}', "
                f"b.category = '{safe_category}', "
                f"b.year = {year}"
            )
        except RuntimeError as e:
            print(f"  ⚠️ 添加书籍失败 [{book_id}]: {e}")

    def add_concept(self, concept_id, name, category=""):
        """添加概念节点"""
        if not self.conn:
            raise RuntimeError("图数据库未初始化")
        
        safe_name = name.replace("'", "''")
        safe_category = category.replace("'", "''")
        
        try:
            self.conn.execute(
                f"MERGE (c:Concept {{concept_id: '{concept_id}'}}) "
                f"SET c.name = '{safe_name}', "
                f"c.category = '{safe_category}'"
            )
        except RuntimeError as e:
            print(f"  ⚠️ 添加概念失败 [{concept_id}]: {e}")

    def add_covers(self, book_id, concept_id, depth=1, relevance=0.5):
        """添加 书→概念 关系，同关系权重递增（Kremis 风格）"""
        if not self.conn:
            raise RuntimeError("图数据库未初始化")
        try:
            self.conn.execute(
                f"MATCH (b:Book {{book_id: '{book_id}'}}), "
                f"(c:Concept {{concept_id: '{concept_id}'}}) "
                f"MERGE (b)-[r:COVERS]->(c) "
                f"ON CREATE SET r.depth = {depth}, r.relevance = {relevance}, r.weight = 1 "
                f"ON MATCH SET r.weight = r.weight + 1, "
                f"  r.relevance = CAST(r.relevance * 0.9 + {relevance} * 0.1 AS DOUBLE)"
            )
        except RuntimeError as e:
            print(f"  ⚠️ 添加 COVERS 失败: {e}")

    def link_cooccurring_concepts(self, book_id, concept_ids, window_size=20):
        """同书内共现的概念自动建边（关联窗口），Kremis 风格"""
        if not self.conn or len(concept_ids) < 2:
            return
        try:
            for i in range(len(concept_ids) - 1):
                for j in range(i + 1, min(i + window_size + 1, len(concept_ids))):
                    a, b = concept_ids[i], concept_ids[j]
                    if a == b:
                        continue
                    self.conn.execute(
                        f"MATCH (c1:Concept {{concept_id: '{a}'}}), "
                        f"(c2:Concept {{concept_id: '{b}'}}) "
                        f"MERGE (c1)-[r:RELATED_TO]->(c2) "
                        f"ON CREATE SET r.relation = '共现', r.strength = 0.1, r.weight = 1 "
                        f"ON MATCH SET r.weight = r.weight + 1, "
                        f"  r.strength = CAST(0.05 + r.strength AS DOUBLE)"
                    )
        except RuntimeError as e:
            print(f"  ⚠️ 链接共现概念失败: {e}")

    def add_related_concepts(self, concept_id_a, concept_id_b, relation="相关", strength=0.5):
        """添加 概念→概念 关系"""
        if not self.conn:
            raise RuntimeError("图数据库未初始化")
        try:
            self.conn.execute(
                f"MATCH (c1:Concept {{concept_id: '{concept_id_a}'}}), "
                f"(c2:Concept {{concept_id: '{concept_id_b}'}}) "
                f"MERGE (c1)-[:RELATED_TO {{relation: '{relation}', strength: {strength}}}]->(c2)"
            )
        except RuntimeError as e:
            print(f"  ⚠️ 添加概念关系失败: {e}")

    def search_books_by_concept(self, concept_name, limit=10):
        """查询某个概念相关的所有书籍"""
        if not self.conn:
            return []
        try:
            result = self.conn.execute(
                f"MATCH (c:Concept {{name: '{concept_name}'}})<-[:COVERS]-(b:Book) "
                f"RETURN b.book_id, b.title, b.author, b.category LIMIT {limit}"
            )
            books = []
            while result.has_next():
                row = result.get_next()
                books.append({
                    'id': row[0],
                    'title': row[1],
                    'author': row[2],
                    'lang': '',
                    'source': 'kuzu',
                    'score': 1.0,
                })
            return books
        except RuntimeError:
            return []

    def search_books_by_multi_concept(self, concept_names, limit=10):
        """查询同时涉及多个概念的书籍（交集）"""
        if not self.conn or not concept_names:
            return []
        
        # 构建多条件查询
        conditions = ",\n      ".join([
            f"(b)-[:COVERS]->(:Concept {{name: '{n}'}})"
            for n in concept_names
        ])
        
        try:
            query = f"MATCH {conditions} RETURN DISTINCT b.book_id, b.title, b.author, b.category LIMIT {limit}"
            result = self.conn.execute(query)
            books = []
            while result.has_next():
                row = result.get_next()
                books.append({
                    'id': row[0],
                    'title': row[1],
                    'author': row[2],
                    'category': row[3],
                    'lang': '',
                    'source': 'kuzu',
                    'score': 1.0,
                })
            return books
        except RuntimeError:
            return []

    def search_related_concepts(self, concept_name, max_hops=2, limit=20):
        """查询概念的相关概念（图遍历）"""
        if not self.conn:
            return []
        try:
            result = self.conn.execute(
                f"MATCH (c:Concept {{name: '{concept_name}'}})"
                f"-[:RELATED_TO*1..{max_hops}]->(related:Concept) "
                f"RETURN DISTINCT related.name, related.category LIMIT {limit}"
            )
            concepts = []
            while result.has_next():
                row = result.get_next()
                concepts.append({
                    'name': row[0],
                    'category': row[1],
                })
            return concepts
        except RuntimeError:
            return []

    def search_by_category(self, category, limit=20):
        """按类别查询书籍"""
        if not self.conn:
            return []
        try:
            result = self.conn.execute(
                f"MATCH (b:Book) WHERE b.category = '{category}' "
                f"RETURN b.book_id, b.title, b.author ORDER BY b.title LIMIT {limit}"
            )
            books = []
            while result.has_next():
                row = result.get_next()
                books.append({
                    'id': row[0],
                    'title': row[1],
                    'author': row[2],
                    'lang': '',
                    'source': 'kuzu',
                    'score': 1.0,
                })
            return books
        except RuntimeError:
            return []

    def get_concept_path(self, concept_a, concept_b, max_hops=5):
        """查找两个概念之间的路径"""
        if not self.conn:
            return []
        try:
            result = self.conn.execute(
                f"MATCH p = shortestPath("
                f"(c1:Concept {{name: '{concept_a}'}})"
                f"-[:RELATED_TO*..{max_hops}]->"
                f"(c2:Concept {{name: '{concept_b}'}})) "
                f"RETURN [n IN nodes(p) | n.name] AS path, length(p) AS hops"
            )
            paths = []
            while result.has_next():
                row = result.get_next()
                paths.append({'path': row[0], 'hops': row[1]})
            return paths
        except RuntimeError:
            return []

    def close(self):
        """关闭数据库"""
        if self.conn:
            self.conn.close()
            self.conn = None
        if self.db:
            self.db.close()
            self.db = None
        if self._temp_dir:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


if __name__ == '__main__':
    print("Kùzu 图谱层自测...")
    with KnowledgeGraph().create_in_memory() as kg:
        # 添加书籍
        kg.add_book("1", "流畅的Python", "Luciano Ramalho", "编程语言", 2015)
        kg.add_book("2", "Python并发编程实战", "Various", "编程语言", 2020)
        kg.add_book("3", "计算机系统", "Randal Bryant", "计算机科学", 2015)

        # 添加概念
        kg.add_concept("py", "Python", "编程语言")
        kg.add_concept("async", "异步编程", "编程范式")
        kg.add_concept("concur", "并发", "编程范式")
        kg.add_concept("event_loop", "事件循环", "编程机制")
        kg.add_concept("gil", "GIL", "语言特性")

        # 添加关系
        kg.add_covers("1", "py", 3, 0.9)
        kg.add_covers("1", "async", 2, 0.8)
        kg.add_covers("2", "async", 3, 0.9)
        kg.add_covers("2", "concur", 3, 0.9)
        kg.add_covers("2", "gil", 2, 0.8)
        kg.add_covers("3", "concur", 1, 0.5)

        kg.add_related_concepts("async", "event_loop", "实现方式", 0.9)
        kg.add_related_concepts("concur", "async", "包含", 0.9)

        # 测试查询
        print("  按概念查书 (异步):")
        for b in kg.search_books_by_concept("异步编程"):
            print(f"    {b['title']}")

        print("  多概念交集 (Python + 并发):")
        for b in kg.search_books_by_multi_concept(["Python", "并发"]):
            print(f"    {b['title']}")

        print("  概念关联 (异步):")
        for c in kg.search_related_concepts("异步编程", max_hops=2):
            print(f"    {c['name']} ({c['category']})")

        print("  按类别查询 (编程语言):")
        for b in kg.search_by_category("编程语言"):
            print(f"    {b['title']}")

    print("✅ Kùzu 图谱层自测通过")
