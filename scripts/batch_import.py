#!/usr/bin/env python3
"""批量导入读书架书籍（带进度条 + 书名清洗 + 去重）"""
import sys, os, glob, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tqdm import tqdm
from src.book_pipeline import BookPipeline
from src.kuzu_graph import KnowledgeGraph


def clean_title(filename):
    """从 MinerU 文件名中提取干净的书名"""
    name = re.sub(r'^MinerU_markdown_\d*_?', '', filename)
    name = re.sub(r'_part_\d+_\d+(\.md)?$', '', name)
    name = re.sub(r'_p\d+$', '', name)
    name = re.sub(r'_\d{8,}', '', name)
    name = re.sub(r'_\(\d+\)$', '', name)
    name = name.rstrip('_').strip()
    name = re.sub(r'\.[扫描清晰中文英文日文原版]+版.*$', '', name)
    name = re.sub(r'\.扫描版.*$', '', name)
    name = re.sub(r'\.清晰版.*$', '', name)
    m = re.search(r'《(.+?)》', name)
    if m:
        name = m.group(1).strip()
    name = re.sub(r'__+', '_', name)
    name = re.sub(r'\s+', ' ', name).strip()
    name = name.strip('_').strip()
    return name


# 收集书籍
shelf = '/mnt/天权智库/天权智库/学习资料/读书架/'
files = sorted(glob.glob(shelf + '*.md'))

groups = {}
for f in files:
    key = re.sub(r'_part_\d+_\d+\.md$', '', os.path.basename(f))
    groups[key] = groups.get(key, []) + [f]

print(f'📚 共 {len(groups)} 本书 / {len(files)} 文件')

# 去重：检查 Kùzu 中已有的书名
try:
    kg = KnowledgeGraph('/root/projects/knowledge-engine/data/kuzu_graph/knowledge.db')
    r = kg.conn.execute('MATCH (b:Book) RETURN b.title')
    existing = set()
    while r.has_next():
        existing.add(r.get_next()[0].strip().lower())
    kg.close()
except:
    existing = set()

# 过滤重复
new_groups = {}
for key, book_files in groups.items():
    title = clean_title(key)
    if title.lower() not in existing:
        new_groups[key] = book_files

if len(new_groups) < len(groups):
    print(f'⏭️  跳过 {len(groups) - len(new_groups)} 本已存在的书')

# 导入
with BookPipeline(persistent=True) as pipe:
    for book_key, book_files in tqdm(sorted(new_groups.items()), desc='导入中', unit='本'):
        title = clean_title(book_key)
        body = ''
        for f in sorted(book_files):
            with open(f, 'r', encoding='utf-8') as fh:
                body += fh.read() + '\n'
        pipe.process_book({
            'id': f'book_{hash(book_key) % 100000}',
            'title': title,
            'author': '',
            'body': body[:300000],
            'tags': '',
        })

# 统计
from src.kuzu_graph import KnowledgeGraph
kg = KnowledgeGraph('/root/projects/knowledge-engine/data/kuzu_graph/knowledge.db')
r = kg.conn.execute('MATCH (b:Book) RETURN count(*)')
total = r.get_next()[0] if r.has_next() else 0
kg.close()

# 分类统计
kg2 = KnowledgeGraph('/root/projects/knowledge-engine/data/kuzu_graph/knowledge.db')
r2 = kg2.conn.execute('MATCH (b:Book) RETURN b.category, count(*) ORDER BY count(*) DESC')
cats = []
while r2.has_next():
    row = r2.get_next()
    cats.append(f'{row[0]}:{row[1]}')
kg2.close()

print(f'\n✅ 导入完成: {total} 本书')
print('  分类:', ' | '.join(cats))
