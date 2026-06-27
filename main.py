#!/usr/bin/env python3
"""
知识引擎 — 命令行入口
"""
import os
import sys
import argparse
import json

# 确保能找到 src 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.book_pipeline import BookPipeline


def cmd_import(args):
    """从文件导入一本书（PDF/TXT/MD）"""
    filepath = args.file
    if not os.path.exists(filepath):
        print(f"❌ 文件不存在: {filepath}")
        return
    
    # 读取正文
    body = ""
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(filepath)
        body = '\n'.join(p.extract_text() or '' for p in reader.pages)
        print(f"  PDF: {len(reader.pages)} 页, {len(body)} 字符")
    elif ext in ('.txt', '.md'):
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            body = f.read()
        print(f"  文本: {len(body)} 字符")
    else:
        print(f"❌ 不支持的文件格式: {ext}")
        return
    
    if not body.strip():
        print("❌ 文件内容为空")
        return
    
    # 用文件名作为默认标题
    title = args.title or os.path.splitext(os.path.basename(filepath))[0]
    
    book = {
        "id": args.id or f"import_{int(time.time())}",
        "title": title,
        "author": args.author or "未知",
        "body": body[:args.max_body or 50000],
        "summary": args.summary or body[:200],
        "tags": args.tags or "",
    }
    
    with BookPipeline(persistent=True) as pipe:
        result = pipe.process_book(book)
        print(f"\n✅ 导入完成")
        print(f"  书名: {result['title']}")
        print(f"  分类: {result['category']} > {result['subcat']}")
        print(f"  字符数: {len(body)}")
        print(f"  耗时: {result['elapsed_ms']}ms")
        
        if args.vault:
            pipe.save_notes_to_obsidian(args.vault, [result])
            print(f"  笔记已同步到 Obsidian: {args.vault}")
        
        if args.rebuild_lsi:
            pipe.rebuild_lsi()
            print(f"  LSI 已重建")


def cmd_process(args):
    """处理一本书（从命令行参数）"""
    book = {
        "id": args.id,
        "title": args.title,
        "author": args.author,
        "body": args.body,
        "summary": args.summary or "",
        "tags": args.tags or "",
    }
    
    concepts = []
    if args.concepts:
        for c in args.concepts.split(";"):
            parts = c.strip().split(",")
            if len(parts) >= 1:
                concepts.append({
                    "name": parts[0],
                    "category": parts[1] if len(parts) > 1 else "",
                    "definition": parts[2] if len(parts) > 2 else "",
                })
    
    highlights = args.highlights.split(";") if args.highlights else []
    
    persistent = getattr(args, 'persistent', True)
    
    with BookPipeline(persistent=persistent) as pipe:
        result = pipe.process_book(book, concepts, highlights)
        
        print(f"书名: {result['title']}")
        print(f"分类: {result['category']} > {result['subcat']}")
        print(f"耗时: {result['elapsed_ms']}ms")
        
        if args.output_note:
            os.makedirs(os.path.dirname(args.output_note) if os.path.dirname(args.output_note) else '.', exist_ok=True)
            with open(args.output_note, 'w', encoding='utf-8') as f:
                f.write(result['note'])
            print(f"笔记已写入: {args.output_note}")
        
        if args.vault:
            pipe.save_notes_to_obsidian(args.vault, [result])
            print(f"笔记已同步到 Obsidian vault: {args.vault}")
        
        if args.rebuild_lsi:
            pipe.rebuild_lsi()
            print("LSI 语义索引已重建")


def cmd_search(args):
    """搜索"""
    persistent = getattr(args, 'persistent', True)
    with BookPipeline(persistent=persistent) as pipe:
        results = pipe.search(args.query, limit=args.limit)
        print(f"搜索 '{args.query}':")
        for r in results:
            src = r.get('source', 'rrf')
            score = r.get('rrf_score', r.get('score', 0))
            title = r.get('title', '')
            print(f"  [{score:.4f}][{src}] {title}")


def cmd_batch(args):
    """批量处理书籍（从 JSON 文件读取）"""
    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    books = data if isinstance(data, list) else [data]
    results = []
    
    with BookPipeline() as pipe:
        for book in books:
            concepts = book.get('concepts', [])
            highlights = book.get('highlights', [])
            result = pipe.process_book(book, concepts, highlights)
            results.append(result)
            print(f"  [{result['category']}] {result['title']} ({result['elapsed_ms']}ms)")
        
        if args.rebuild_lsi:
            pipe.rebuild_lsi()
            print(f"LSI 语义索引已重建")
        
        if args.vault:
            pipe.save_notes_to_obsidian(args.vault, results)
            print(f"笔记已同步到 Obsidian vault: {args.vault}")


def main():
    parser = argparse.ArgumentParser(description="天权知识引擎")
    subparsers = parser.add_subparsers(dest="cmd", help="子命令")
    
    # process
    p = subparsers.add_parser("process", help="处理一本书")
    p.add_argument("--id", required=True, help="书籍 ID")
    p.add_argument("--title", required=True, help="书名")
    p.add_argument("--author", default="", help="作者")
    p.add_argument("--body", required=True, help="书籍正文")
    p.add_argument("--summary", default="", help="内容概要")
    p.add_argument("--tags", default="", help="标签（空格分隔）")
    p.add_argument("--concepts", default="", help="核心概念（格式: 名称,类别,定义;名称2,...）")
    p.add_argument("--highlights", default="", help="摘录（用;分隔）")
    p.add_argument("--output-note", default="", help="笔记输出路径")
    p.add_argument("--vault", default="", help="Obsidian vault 路径")
    p.add_argument("--rebuild-lsi", action="store_true", help="重建 LSI 索引")
    
    # search
    p = subparsers.add_parser("search", help="搜索")
    p.add_argument("query", help="搜索关键词")
    p.add_argument("--limit", type=int, default=10, help="返回条数")
    
    # batch
    p = subparsers.add_parser("batch", help="批量处理（JSON 文件）")
    p.add_argument("input", help="JSON 文件路径")
    p.add_argument("--vault", default="", help="Obsidian vault 路径")
    p.add_argument("--rebuild-lsi", action="store_true", help="重建 LSI 索引")
    
    # import
    p = subparsers.add_parser("import", help="从文件导入（PDF/TXT/MD）")
    p.add_argument("--file", required=True, help="文件路径")
    p.add_argument("--id", default="", help="书籍 ID")
    p.add_argument("--title", default="", help="书名（默认用文件名）")
    p.add_argument("--author", default="", help="作者")
    p.add_argument("--tags", default="", help="标签")
    p.add_argument("--summary", default="", help="内容概要")
    p.add_argument("--max-body", type=int, default=50000, help="最大导入字符数")
    p.add_argument("--vault", default="", help="Obsidian vault 路径")
    p.add_argument("--rebuild-lsi", action="store_true", help="重建 LSI")
    
    args = parser.parse_args()
    
    if args.cmd == "process":
        cmd_process(args)
    elif args.cmd == "search":
        cmd_search(args)
    elif args.cmd == "batch":
        cmd_batch(args)
    elif args.cmd == "import":
        cmd_import(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
