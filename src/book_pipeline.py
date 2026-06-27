#!/usr/bin/env python3
"""
书籍导入管道 — 自动分类 + 写入三层索引 + 生成 Obsidian 笔记
支持内存模式（测试）和持久化模式（生产）
"""
import os
import re
import json
import time
import sys
from datetime import datetime

# 支持作为脚本直接运行和作为模块导入
if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src import rrf
    from src.tantivy_index import BookIndex
    from src.kuzu_graph import KnowledgeGraph
    from src.lsi_semantic import SemanticIndex, extract_keywords
    from src.config import TANTIVY_INDEX_DIR, KUZU_DB_PATH, LSI_MODEL_PATH
else:
    from . import rrf
    from .tantivy_index import BookIndex
    from .kuzu_graph import KnowledgeGraph
    from .lsi_semantic import SemanticIndex, extract_keywords
    from .config import TANTIVY_INDEX_DIR, KUZU_DB_PATH, LSI_MODEL_PATH


# 一级学科关键词库（纯规则，零 LLM）
CATEGORY_KEYWORDS = {
    "编程语言": ["Python", "Java", "C++", "Rust", "Go", "JavaScript", "TypeScript", 
                 "编程", "程序", "语法", "编译器", "面向对象", "函数式"],
    "计算机科学": ["计算机", "算法", "数据结构", "操作系统", "网络", "体系结构",
                  "编译原理", "图论", "计算理论"],
    "数据处理": ["数据库", "大数据", "数据挖掘", "数据分析", "SQL", "NoSQL",
                "数据仓库", "ETL", "数据工程"],
    "AI机器学习": ["神经网络", "深度学习", "机器学习", "强化学习", "Transformer",
                  "自然语言", "计算机视觉", "智能"],
    "分布式系统": ["分布式", "微服务", "容器", "Kubernetes", "云原生", "高并发",
                  "可扩展", "一致性", "共识"],
    "软件工程": ["软件工程", "设计模式", "重构", "测试", "DevOps", "敏捷",
                "CI/CD", "架构"],
    "数学": ["线性代数", "概率论", "统计学", "微积分", "离散数学", "矩阵",
             "优化", "数值分析"],
    "物理科学": ["物理", "量子", "力学", "电磁", "热力学", "相对论"],
    "认知神经科学": ["神经科学", "认知", "大脑", "神经元", "脑", "心智", "意识",
                    "突触", "海马体"],
    "金融": ["金融", "量化", "交易", "投资", "股票", "期权", "风险管理", "经济"],
    "项目管理": ["项目管理", "PMP", "敏捷", "Scrum", "风险管理", "进度"],
    "文学": ["小说", "文学", "诗歌", "散文", "故事", "历史"],
}


def classify_book(title, body, tags=""):
    """根据书名+目录+标签自动分类（纯规则，零 LLM）
    
    标题中的关键词权重是正文的 3 倍，防止正文干扰。
    
    返回: (一级分类, 二级分类, 匹配得分)
    """
    title_lower = title.lower()
    body_lower = f"{tags} {body[:2000]}".lower()
    
    best_cat = "未分类"
    best_score = 0
    
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        for kw in keywords:
            kw_lower = kw.lower()
            # 标题匹配权重 3
            if kw_lower in title_lower:
                score += 3
            # 正文匹配权重 1
            elif kw_lower in body_lower:
                score += 1
        if score > best_score:
            best_score = score
            best_cat = category
    
    # 排他性修正：如果"计算机"在标题中但"编程语言"匹配数没有明显优势
    if best_cat == "编程语言":
        # 检查是否更可能是计算机科学
        cs_score = 0
        for kw in CATEGORY_KEYWORDS["计算机科学"]:
            if kw.lower() in title_lower:
                cs_score += 3
            elif kw.lower() in body_lower:
                cs_score += 1
        # 如果计算机科学得分相近，选计算机科学
        if cs_score > 0 and cs_score >= best_score * 0.7:
            # 除非标题明确包含编程语言特有词
            prog_specific = ["python", "java", "c++", "javascript", "编程语言"]
            has_prog_title = any(p in title_lower for p in prog_specific)
            if not has_prog_title:
                best_cat = "计算机科学"
                best_score = max(best_score, cs_score)
    
    # 二级分类
    subcat = ""
    if best_cat == "编程语言":
        for lang in ["Python", "Java", "C++", "Rust", "Go", "JavaScript"]:
            if lang.lower() in title_lower:
                subcat = lang
                break
    
    return best_cat, subcat, best_score


def generate_note(book, category, subcat, concepts, highlights=None):
    """生成 Obsidian 格式的读书笔记 Markdown"""
    title = book.get('title', '未知书名')
    author = book.get('author', '未知')
    cat_path = f"{category}" + (f" > {subcat}" if subcat else "")
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    # 标签
    tags_list = [category]
    if subcat:
        tags_list.append(subcat)
    
    lines = [
        f"# 《{title}》",
        "",
        f"**作者：** {author}",
        f"**读完日期：** {date_str}",
        f"**分类：** {cat_path}",
        f"**标签：** {' '.join(f'#{t}' for t in tags_list)}",
        "",
        "## 内容概要",
        book.get('summary', '（待补充）'),
        "",
        "## 核心概念",
    ]
    
    if concepts:
        for c in concepts:
            lines.append(f"- **{c['name']}**: {c.get('definition', '')}")
    else:
        lines.append("（待补充）")
    
    lines.append("")
    lines.append("## 与其他书的关联")
    lines.append("")
    lines.append("## 与我有关")
    lines.append("")
    if highlights:
        lines.append("## 摘录")
        for h in highlights:
            lines.append(f"> {h}")
            lines.append("")
    
    return '\n'.join(lines)


def note_filename(title):
    """从书名生成安全的文件名"""
    safe = re.sub(r'[\\/:*?"<>|]', '', title)
    return f"《{safe}》.md"


class BookPipeline:
    """书籍全流程处理管道 — 支持内存模式（默认）和持久化模式"""

    def __init__(self, index_path=None, graph_path=None, lsi_path=None, persistent=False):
        if persistent:
            from .config import ensure_dirs
            ensure_dirs()
            index_path = index_path or TANTIVY_INDEX_DIR
            graph_path = graph_path or KUZU_DB_PATH
            lsi_path = lsi_path or LSI_MODEL_PATH
        
        self.tantivy = BookIndex(index_path) if index_path else BookIndex().create_in_memory()
        self.graph = KnowledgeGraph(graph_path) if graph_path else KnowledgeGraph().create_in_memory()
        self.lsi = None
        self.lsi_path = lsi_path
        self.books_cache = []  # 用于重建 LSI
        self.persistent = persistent
        
        # 如果有持久化 LSI，自动加载
        if persistent and lsi_path and os.path.exists(lsi_path):
            try:
                self.lsi = SemanticIndex()
                self.lsi.load(lsi_path)
            except Exception:
                self.lsi = None

    def process_book(self, book, concepts=None, highlights=None):
        """处理一本书的全流程
        
        参数:
            book: dict, 包含 id, title, author, body, summary, tags(可选)
            concepts: list[dict], 包含 name, definition, category(可选)
            highlights: list[str], 摘录
        
        返回: dict, 处理结果
        """
        t0 = time.time()
        book_id = book.get('id', str(len(self.books_cache) + 1))
        title = book.get('title', '')
        author = book.get('author', '')
        body = book.get('body', '')
        tags = book.get('tags', '')
        summary = book.get('summary', '')
        concepts = concepts or []
        highlights = highlights or []

        # Step 1: 自动分类
        category, subcat, score = classify_book(title, body, tags)
        
        # Step 2: 写入 Tantivy 索引
        self.tantivy.add_book(
            book_id=book_id,
            title=title,
            author=author,
            category=category,
            body=body,
            tags=tags,
        )
        
        # Step 3: 写入 Kùzu 图谱
        self.graph.add_book(book_id, title, author, category)
        for c in concepts:
            cid = c.get('id', c['name'].replace(' ', '_'))
            self.graph.add_concept(cid, c['name'], c.get('category', ''))
            self.graph.add_covers(book_id, cid, depth=2, relevance=0.8)
        
        # Step 4: 生成 Obsidian 笔记
        note = generate_note(book, category, subcat, concepts, highlights)
        
        # 缓存书籍（用于后续重建 LSI）
        self.books_cache.append(book)
        
        elapsed = time.time() - t0
        return {
            'book_id': book_id,
            'title': title,
            'category': category,
            'subcat': subcat,
            'classification_score': score,
            'note': note,
            'elapsed_ms': round(elapsed * 1000, 1),
        }

    def rebuild_lsi(self, n_components=100):
        """重建 LSI 语义索引"""
        if not self.books_cache:
            return False
        self.lsi = SemanticIndex(n_components=n_components)
        self.lsi.build(self.books_cache)
        if self.lsi_path:
            self.lsi.save(self.lsi_path)
        return True

    def search(self, query, limit=10):
        """全引擎搜索（三路并行 + RRF 融合）"""
        results = []
        
        # 1. Tantivy 精确检索
        tantivy_results = self.tantivy.search(query, "body", limit=limit * 2)
        results.append(tantivy_results)
        
        # 2. Kùzu 图检索（通过概念查书）
        kuzu_results = self.graph.search_books_by_concept(query, limit=limit)
        results.append(kuzu_results)
        
        # 3. LSI 语义检索
        lsi_results = []
        if self.lsi and self.lsi.is_built:
            lsi_results = self.lsi.search(query, top_k=limit * 2)
        results.append(lsi_results)
        
        # 4. RRF 融合
        fused = rrf.rrf_fusion(results, k=60)
        return fused[:limit]

    def save_notes_to_obsidian(self, vault_base, results):
        """将笔记写入 Obsidian vault"""
        for r in results:
            note = r.get('note', '')
            if not note:
                continue
            
            cat = r.get('category', '未分类')
            subcat = r.get('subcat', '')
            
            # 自动创建分类目录
            dir_path = os.path.join(vault_base, cat)
            if subcat:
                dir_path = os.path.join(dir_path, subcat)
            os.makedirs(dir_path, exist_ok=True)
            
            # 写入文件
            fname = note_filename(r['title'])
            filepath = os.path.join(dir_path, fname)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(note)

    def close(self):
        self.tantivy.close()
        self.graph.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


if __name__ == '__main__':
    print("书籍导入管道自测...")
    
    with BookPipeline() as pipe:
        # 模拟处理一本书
        book = {
            "id": "test_001",
            "title": "Python并发编程实战",
            "author": "Various",
            "body": "本书深入讲解Python中的并发编程技术，包括多线程、多进程、异步IO、事件循环等。涵盖GIL、线程安全、锁机制。",
            "summary": "一本全面介绍Python并发编程的实用书籍",
            "tags": "Python 并发 多线程 异步",
        }
        concepts = [
            {"name": "多线程", "category": "并发模型", "definition": "一种并发执行方式"},
            {"name": "异步编程", "category": "编程范式", "definition": "基于事件循环的非阻塞编程"},
            {"name": "GIL", "category": "语言特性", "definition": "Python全局解释器锁"},
        ]
        highlights = [
            "GIL导致多线程在CPU密集型场景下无法利用多核",
            "异步编程适用于IO密集型场景",
        ]
        
        result = pipe.process_book(book, concepts, highlights)
        print(f"  分类: {result['category']} > {result['subcat']}")
        print(f"  得分: {result['classification_score']}")
        print(f"  耗时: {result['elapsed_ms']}ms")
        
        # 重建 LSI
        pipe.rebuild_lsi()
        
        # 搜索测试
        print("\n  搜索 'Python 并发':")
        for r in pipe.search("Python 并发", limit=5):
            print(f"    [{r.get('rrf_score', r.get('score', 0)):.4f}] {r.get('title', '')} ({r.get('source', '')})")
        
        # 展示笔记
        print(f"\n  生成笔记预览:\n{result['note'][:300]}...")

    print("✅ 书籍导入管道自测通过")
