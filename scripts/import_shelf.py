#!/usr/bin/env python3
"""
批量导入读书架书籍 — 预分词 + 批量写入，单writer单commit
支持 --limit 参数限制导入数量
"""
import sys, os, re, time, json, collections
from tqdm import tqdm
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.book_pipeline import BookPipeline, classify_book
from src.tokenizer import tokenize, detect_lang

SHELF = "/mnt/天权智库/天权智库/学习资料/读书架/"
STATUS_FILE = "/tmp/import_status.json"


def extract_title(filename):
    m = re.search(r'《(.+?)》', filename)
    if m:
        return m.group(1).strip()
    m = re.search(r'\d+_(.+?)(?:_part_\d+|$)', filename)
    if m:
        t = m.group(1).replace('_', ' ').strip()
        return t[:80]
    return filename[:60]


def group_books(limit=0):
    files = sorted(os.listdir(SHELF))
    groups = {}
    for f in files:
        if not f.endswith('.md'):
            continue
        key = re.sub(r'_part_\d+_\d+\.md$', '', f)
        groups.setdefault(key, []).append(f)
    items = list(groups.items())
    if limit > 0 and limit < len(items):
        items = items[:limit]
    result = collections.OrderedDict()
    for k, v in items:
        result[k] = v
    return result


def import_books(limit=0):
    """预分词 + 批量写入，单writer单commit"""
    groups = group_books(limit)
    total = len(groups)
    print(f"发现 {total} 本书 / {sum(len(v) for v in groups.values())} 个文件\n")

    t0 = time.time()
    batch = []
    kuzu_ops = []
    manifest = []
    errors = 0

    # Phase 1: 读取 + 分词（仅一次）
    pbar = tqdm(total=total, desc="读取+分词", unit="本", ncols=70)
    for idx, (book_key, files) in enumerate(groups.items()):
        try:
            title = extract_title(book_key)
            body = ''
            for f in sorted(files):
                fp = os.path.join(SHELF, f)
                with open(fp, 'r', encoding='utf-8', errors='replace') as fh:
                    body += fh.read() + '\n'
            body = body[:10000000]
            
            # 写入状态
            elapsed = time.time() - t0
            status = {
                'phase': '读取+分词', 'done': idx + 1, 'total': total,
                'elapsed': round(elapsed, 1), 'speed': round((idx + 1) / max(elapsed, 0.01), 2),
                'eta': round((total - idx - 1) * max(elapsed, 0.01) / max(idx + 1, 1), 0),
                'current_book': title[:60], 'errors': errors,
            }
            with open(STATUS_FILE, 'w') as sf:
                json.dump(status, sf)

            lang = detect_lang(f"{title} {body[:200]}")
            cat, subcat, score = classify_book(title, body)
            bid = f'shelf_{idx}'

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
        except Exception as e:
            errors += 1
            tqdm.write(f"  ❌ [{idx+1}/{total}] {book_key[:40]}: {e}")
        pbar.update(1)
    pbar.close()

    t1 = time.time()
    phase1 = t1 - t0
    print(f"  读取+分词完成: {len(batch)} 本, {phase1:.1f}s ({len(batch)/max(phase1,0.01):.1f}本/秒)\n")

    # Phase 2: Tantivy 批量写入
    if batch:
        print("Tantivy 批量写入...")
        from src.tantivy_index import BookIndex
        from src.config import TANTIVY_INDEX_DIR
        idx = BookIndex(TANTIVY_INDEX_DIR)
        idx.add_books_batch(batch, tokenized=True)
        idx.reload()
    t2 = time.time()
    phase2 = t2 - t1
    with open(STATUS_FILE, 'w') as sf:
        json.dump({'phase': 'Tantivy写入完成', 'done_phases': ['读取+分词','Tantivy写入']}, sf)
    print(f"  Tantivy写入: {phase2:.1f}s ({len(batch)/max(phase2,0.01):.1f}本/秒)\n")

    # Phase 3: Kùzu 批量写入
    if kuzu_ops:
        print("Kùzu 写入...")
        from src.kuzu_graph import KnowledgeGraph
        from src.config import KUZU_DB_PATH
        gr = KnowledgeGraph(KUZU_DB_PATH)
        for bid, title, author, cat in tqdm(kuzu_ops, desc="Kùzu写入", unit="本", ncols=70):
            gr.add_book(bid, title, author, cat)
        gr.close()
    t3 = time.time()
    phase3 = t3 - t2
    print(f"  Kùzu写入: {phase3:.1f}s\n")

    # Phase 4: LSI + 向量索引
    if manifest:
        print("重建LSI+向量索引...")
        pipe = BookPipeline(persistent=True)
        pipe.__enter__()
        pipe.books_cache = [
            {'id': m['id'], 'title': m['title'], 'author': '',
             '_category': m['category'], 'body': '', 'lang': m['lang'], 'summary': ''}
            for m in manifest
        ]
        pipe.rebuild_lsi(n_components=50)
        pipe.__exit__(None, None, None)
    t4 = time.time()

    # 摘要
    elapsed = t4 - t0
    print(f"\n{'='*50}")
    print(f"✅ 导入完成: {len(batch)}/{total}")
    print(f"⏱  总耗时: {elapsed:.1f}s ({len(batch)/max(elapsed,0.01):.1f}本/秒)")
    print(f"  Phase 1 读取分词: {phase1:.1f}s")
    print(f"  Phase 2 Tantivy:   {phase2:.1f}s")
    print(f"  Phase 3 Kùzu:      {phase3:.1f}s")
    print(f"  Phase 4 LSI+向量:  {t4-t3:.1f}s")
    with open('/tmp/import_manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"📄 清单: /tmp/import_manifest.json")


if __name__ == '__main__':
    limit = 0
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
    import_books(limit)
