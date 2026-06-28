#!/usr/bin/env python3
"""
批量导入读书架书籍 — 预分词 + 批量写入，单writer单commit
"""
import sys, os, re, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.book_pipeline import BookPipeline, classify_book
from src.tokenizer import tokenize, detect_lang

SHELF = "/mnt/天权智库/天权智库/学习资料/读书架/"


def extract_title(filename):
    m = re.search(r'《(.+?)》', filename)
    if m:
        return m.group(1).strip()
    m = re.search(r'\d+_(.+?)(?:_part_\d+|$)', filename)
    if m:
        t = m.group(1).replace('_', ' ').strip()
        return t[:80]
    return filename[:60]


def group_books():
    files = sorted(os.listdir(SHELF))
    groups = {}
    for f in files:
        if not f.endswith('.md'):
            continue
        key = re.sub(r'_part_\d+_\d+\.md$', '', f)
        groups.setdefault(key, []).append(f)
    return groups


def import_books():
    """预分词 + 批量写入，单writer单commit"""
    groups = group_books()
    total = len(groups)
    print(f"发现 {total} 本书 / {sum(len(v) for v in groups.values())} 个文件")

    t0 = time.time()
    batch = []
    kuzu_ops = []
    manifest = []

    # Phase 1: 读取 + 分词（仅一次）
    for idx, (book_key, files) in enumerate(groups.items()):
        try:
            title = extract_title(book_key)
            body = ''
            for f in sorted(files):
                fp = os.path.join(SHELF, f)
                with open(fp, 'r', encoding='utf-8', errors='replace') as fh:
                    body += fh.read() + '\n'
            body = body[:10000000]

            lang = detect_lang(f"{title} {body[:200]}")
            cat, subcat, score = classify_book(title, body)
            bid = f'shelf_{idx}'

            # 分词仅一次，后续批量写入直接使用tokenized文本
            tok_body = tokenize(body)
            tok_tags = ''

            batch.append({
                'book_id': bid, 'title': title, 'author': '',
                'category': cat, 'body': tok_body, 'tags': tok_tags, 'lang': lang,
            })
            kuzu_ops.append((bid, title, '', cat))
            manifest.append({
                'id': bid, 'title': title,
                'lang': lang, 'category': cat, 'files': len(files),
            })

            if (idx + 1) % 30 == 0:
                elapsed = time.time() - t0
                rate = (idx + 1) / max(elapsed, 0.01)
                eta = (total - idx - 1) / max(rate, 0.01)
                print(f"  [{idx+1}/{total}] 读取+分词... ({rate:.1f}本/秒, ETA {eta:.0f}s)")
        except Exception as e:
            print(f"  ❌ [{idx+1}/{total}] {book_key[:40]}: {e}")

    t1 = time.time()
    phase1 = t1 - t0
    print(f"Phase 1 读取+分词: {len(batch)} 本, {phase1:.1f}s ({len(batch)/max(phase1,0.01):.1f}本/秒)")

    # Phase 2: Tantivy 批量写入（单writer单commit，heap减半）
    from src.tantivy_index import BookIndex
    from src.config import TANTIVY_INDEX_DIR
    idx = BookIndex(TANTIVY_INDEX_DIR)
    idx.add_books_batch(batch, tokenized=True)
    idx.reload()

    t2 = time.time()
    phase2 = t2 - t1
    print(f"Phase 2 Tantivy写入: {t2-t1:.1f}s ({len(batch)/max(phase2,0.01):.1f}本/秒)")

    # Phase 3: Kùzu 批量写入
    from src.kuzu_graph import KnowledgeGraph
    from src.config import KUZU_DB_PATH
    gr = KnowledgeGraph(KUZU_DB_PATH)
    for bid, title, author, cat in kuzu_ops:
        gr.add_book(bid, title, author, cat)
    gr.close()

    t3 = time.time()
    print(f"Phase 3 Kùzu写入: {t3-t2:.1f}s")

    # Phase 4: LSI + 向量索引
    pipe = BookPipeline(persistent=True)
    pipe.__enter__()
    pipe.books_cache = [
        {'id': m['id'], 'title': m['title'], 'author': '',
         '_category': m['category'], 'body': '', 'lang': m['lang'], 'summary': ''}
        for m in manifest
    ]
    pipe.rebuild_lsi(n_components=50)
    pipe.__exit__(None, None, None)

    elapsed = time.time() - t0
    print(f"Phase 4 LSI+向量: {elapsed-t3:.1f}s")
    print(f"\n{'='*50}")
    print(f"导入完成: {len(batch)}/{total}")
    print(f"总耗时: {elapsed:.1f}s ({len(batch)/max(elapsed,0.01):.1f}本/秒)")
    print(f"  Phase 1 读取分词: {phase1:.1f}s")
    print(f"  Phase 2 Tantivy:   {phase2:.1f}s")
    print(f"  Phase 3 Kùzu:      {t3-t2:.1f}s")
    print(f"  Phase 4 LSI+向量:  {elapsed-t3:.1f}s")
    with open('/tmp/import_manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    import_books()
