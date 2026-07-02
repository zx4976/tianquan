#!/usr/bin/env python3
"""
强制逐字阅读 — 切碎 + 原子提取 + 随机审计 (v2)
"""
import sys, os, re, random, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from src.tantivy_index import BookIndex
from src.config import TANTIVY_INDEX_DIR

CHUNK_SIZE = 5000
AUDIT_RATIO = 0.15
PASS_THRESHOLD = 0.7


def chop_text(body, size=CHUNK_SIZE):
    return [body[i:i+size] for i in range(0, len(body), size)]


def clean_text(text):
    """清洗文本：去掉LaTeX、图片链接、多余空格"""
    text = re.sub(r'\$[^$]+\$', '', text)  # 去掉LaTeX公式
    text = re.sub(r'!\[image\]\([^)]+\)', '', text)  # 去掉图片
    text = re.sub(r'https?://\S+', '', text)  # 去掉URL
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_atoms(chunk):
    """从文本块提取可验证的知识原子"""
    cleaned = clean_text(chunk)
    atoms = []
    
    # 1. 提取"X是Y"定义句（中文特有模式）
    for m in re.finditer(r'([^。，；]{4,40})是([^。，；]{8,80})', cleaned):
        left = m.group(1).strip()
        right = m.group(2).strip()
        # 过滤掉明显不是定义的（含符号、纯数字等）
        if not re.search(r'[\\{}()\[\]$]', left) and not re.search(r'^[\d\s]+$', left) and len(left) > 2:
            atoms.append(('定义', f'{left} 是 {right[:50]}'))
    
    # 2. 提取定理/引理/命题陈述
    for m in re.finditer(r'(定理|引理|命题|推论|定义)\s*[\d\.]+\s*([^。]{10,80})', cleaned):
        atoms.append(('定理', m.group()[:60]))
    
    # 3. 提取"本书"陈述（作者明确断言）
    for m in re.finditer(r'本书[^。]{10,80}', cleaned):
        atoms.append(('断言', m.group()[:60]))
    
    # 4. 提取作者具体结论/方法
    for m in re.finditer(r'(主要内容|方法|步骤|分为|包括|由)([^。]{8,80})', cleaned):
        atoms.append(('内容', m.group()[:60]))
    
    # 5. 去重
    seen = set()
    unique = []
    for t, c in atoms:
        key = c[:30]
        if key not in seen:
            seen.add(key)
            unique.append((t, c))
    
    return unique[:20]  # 每块最多20个原子


def generate_quiz(atoms):
    """从原子生成审计题"""
    questions = []
    for t, c in atoms[:8]:
        if t == '定义':
            # "X是Y" → 问X是什么
            parts = c.split('是', 1)
            if len(parts) == 2 and len(parts[0]) < 30:
                questions.append({
                    'type': '定义',
                    'q': f"'{parts[0].strip()}'是什么？",
                    'ref': c
                })
        elif t == '定理':
            questions.append({
                'type': '定理',
                'q': f"这个定理/引理/定义说的是什么？",
                'ref': c
            })
        elif t == '断言':
            questions.append({
                'type': '断言',
                'q': f"作者说了什么？",
                'ref': c
            })
    return questions


def deep_read(book_id):
    idx = BookIndex(TANTIVY_INDEX_DIR)
    
    body = idx.get_body(book_id)
    if not body:
        print(f"❌ 无法获取 {book_id} 的正文")
        return None
    
    chunks = chop_text(body)
    print(f"📖 切碎: {len(chunks)}块 × {CHUNK_SIZE}字符")
    
    # 提取所有原子
    all_atoms = []
    for i, chunk in enumerate(chunks):
        atoms = extract_atoms(chunk)
        if atoms:
            all_atoms.append((i, atoms, chunk))
    
    total_atoms = sum(len(a[1]) for a in all_atoms)
    print(f"   原子事实: {total_atoms}个（来自{len(all_atoms)}个有内容的块）")
    
    # 随机审计 — 选有原子的块
    candidate_indices = [a[0] for a in all_atoms if len(a[1]) >= 2]
    if len(candidate_indices) < 3:
        candidate_indices = [a[0] for a in all_atoms]
    
    audit_count = max(3, int(len(candidate_indices) * AUDIT_RATIO))
    audit_indices = random.sample(candidate_indices, min(audit_count, len(candidate_indices)))
    
    # 按块号排序
    audit_indices.sort()
    
    print(f"   审计抽查: {len(audit_indices)}题（从{len(candidate_indices)}个候选块中抽取）")
    print(f"\n{'='*60}")
    print("📋 闭卷审计 — 逐题回答，不能回看原文")
    print(f"{'='*60}")
    
    audit_items = []
    for ci in audit_indices:
        atoms = [a for a in all_atoms if a[0] == ci]
        if not atoms:
            continue
        _, atom_list, chunk_text = atoms[0]
        questions = generate_quiz(atom_list)
        for q in questions[:2]:
            audit_items.append((ci, q, chunk_text[:80]))
    
    for ci, q, prev in audit_items:
        print(f"\n  Q [块{ci}]: {q['q']}")
        print(f"  参考: {q['ref'][:60]}")
        print(f"  A: [待回答]")
    
    print(f"\n{'='*60}")
    print(f"📊 共{len(audit_items)}道审计题。全部答对方可通过。")
    print(f"{'='*60}")
    
    return {
        'book_id': book_id,
        'chunks': len(chunks),
        'atoms': total_atoms,
        'audit_count': len(audit_items),
        'audit_items': audit_items
    }


if __name__ == '__main__':
    bid = sys.argv[1] if len(sys.argv) > 1 else 'shelf_2'
    result = deep_read(bid)
    if result:
        # 保存审计清单供对话中使用
        with open(f'/tmp/audit_{bid}.json', 'w') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n审计清单已保存: /tmp/audit_{bid}.json")
