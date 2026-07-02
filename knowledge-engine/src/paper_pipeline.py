#!/usr/bin/env python3
"""
文献分析管道 — arXiv 论文导入 + 引用图谱
"""
import os
import sys
import json
import time
import re

# 支持直接运行和模块导入
if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.book_pipeline import BookPipeline
    from src.arxiv_helper import fetch_metadata, download_pdf, extract_references, parse_arxiv_id
    from src.tantivy_index import BookIndex
    from src.kuzu_graph import KnowledgeGraph
    from src.tokenizer import tokenize
else:
    from .book_pipeline import BookPipeline
    from .arxiv_helper import fetch_metadata, download_pdf, extract_references, parse_arxiv_id
    from .tantivy_index import BookIndex
    from .kuzu_graph import KnowledgeGraph
    from .tokenizer import tokenize


class PaperPipeline:
    """文献导入管道 — 专门处理学术论文"""

    def __init__(self, persistent=True):
        self.pipe = BookPipeline(persistent=persistent)
        self.graph = self.pipe.graph

    def import_arxiv(self, arxiv_id_or_url, rebuild_lsi=True):
        """从 arXiv ID 导入一篇论文"""
        arxiv_id = parse_arxiv_id(arxiv_id_or_url)
        
        print(f"📥 获取元数据: {arxiv_id}...")
        meta = fetch_metadata(arxiv_id)
        if 'error' in meta:
            print(f"❌ 元数据获取失败: {meta['error']}")
            return None
        
        title = meta.get('title', '')
        authors = ', '.join(meta.get('authors', []))
        year = meta.get('year', '')
        summary = meta.get('summary', '')
        primary_cat = meta.get('primary_category', '')
        
        # 映射学科分类
        from src.arxiv_helper import classify_arxiv_category
        category = classify_arxiv_category(primary_cat)
        
        print(f"  标题: {title[:60]}...")
        print(f"  作者: {authors[:60]}...")
        print(f"  年份: {year} | 分类: {category}")
        
        # 下载 PDF
        print(f"📥 下载 PDF...")
        pdf_path = download_pdf(arxiv_id)
        if not pdf_path or not os.path.exists(pdf_path):
            print(f"⚠️ PDF 下载失败，使用摘要作为正文")
            body = summary
        else:
            # 提取正文
            from pypdf import PdfReader
            reader = PdfReader(pdf_path)
            body_parts = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    body_parts.append(t)
            body = '\n'.join(body_parts)
            os.remove(pdf_path)
            print(f"  正文: {len(body)} 字符, {len(reader.pages)} 页")
        
        # 提取参考文献
        print(f"📚 解析参考文献...")
        references = extract_references(body)
        print(f"  找到 {len(references)} 条引用")
        
        # 构建书对象
        book_id = f"arxiv_{arxiv_id.replace('.', '_')}"
        book = {
            'id': book_id,
            'title': title,
            'author': authors,
            'body': body,
            'summary': summary,
            'tags': f"arxiv {primary_cat} {year}",
        }
        
        # 提取核心概念（从标题+摘要）
        concepts = []
        kw_text = f"{title} {summary}"
        from src.tokenizer import extract_keywords
        keywords = extract_keywords(kw_text, topK=5)
        for i, kw in enumerate(keywords):
            concepts.append({
                'name': kw,
                'category': category,
                'definition': '',
            })
        
        # 导入到知识库
        print(f"📦 写入知识库...")
        result = self.pipe.process_book(book, concepts=concepts)
        
        # 添加引用关系到 Kùzu
        print(f"🔗 建立引用图谱...")
        ref_count = 0
        for ref in references:
            ref_id = f"ref_{book_id}_{ref['index']}"
            self.graph.add_concept(ref_id, ref['raw'][:100], category='引用文献')
            self.graph.add_covers(book_id, ref_id, depth=1, relevance=0.3)
            ref_count += 1
        
        # 添加 arXiv 元数据到 Kùzu
        self.graph.add_concept(f"cat_{primary_cat}", primary_cat, category='arXiv分类')
        self.graph.add_covers(book_id, f"cat_{primary_cat}", depth=1, relevance=0.5)
        
        if rebuild_lsi:
            print(f"🔧 重建 LSI...")
            self.pipe.rebuild_lsi()
        
        print(f"\n✅ 导入完成:")
        print(f"  论文: {title[:60]}")
        print(f"  分类: {category}")
        print(f"  引用: {ref_count} 条")
        print(f"  耗时: {result.get('elapsed_ms', 0):.0f}ms")
        
        return {
            'book_id': book_id,
            'title': title,
            'category': category,
            'year': year,
            'authors': authors,
            'arxiv_id': arxiv_id,
            'references': ref_count,
        }

    def close(self):
        self.pipe.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python3 src/paper_pipeline.py <arxiv_id>")
        sys.exit(1)
    
    arxiv_id = sys.argv[1]
    with PaperPipeline(persistent=False) as pp:
        result = pp.import_arxiv(arxiv_id)
        if result:
            print(f"\n导入结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
