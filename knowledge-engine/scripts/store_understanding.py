#!/usr/bin/env python3
"""
理解存储工具 — 在对话中逐段读书，逐段存入理解

用法:
  # 存入一条理解
  python3 scripts/store_understanding.py <book_id> store \
    --dim "第1章" \
    --content "微分与积分是微积分的主要矛盾" \
    --evidence "微分与积分这是一对矛盾" \
    --imp 9

  # 查看本书已存的理解
  python3 scripts/store_understanding.py <book_id> status

  # 标记某章已读
  python3 scripts/store_understanding.py <book_id> mark-chapter "第1章"

  # 最终审计全书（闭卷）
  python3 scripts/store_understanding.py <book_id> audit

  # 审计通过后标记已读
  python3 scripts/store_understanding.py <book_id> mark-read

  # 查看未读书籍列表
  python3 scripts/store_understanding.py --list

  # 查看书籍信息和原文预览
  python3 scripts/store_understanding.py <book_id> info
"""
import sys, os, re, json, time, subprocess, random

if "UV_ACTIVE" not in os.environ and "VIRTUAL_ENV" not in os.environ:
    script_path = os.path.abspath(__file__)
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    subprocess.run(["uv", "run", "python3", script_path] + args)
    sys.exit()

ENGINE_DIR = os.path.expanduser("~/projects/knowledge-engine")
sys.path.insert(0, ENGINE_DIR)
from src.understanding import Understanding
from src.tantivy_index import BookIndex
from src.kuzu_graph import KnowledgeGraph

TANTIVY_DIR = os.path.join(ENGINE_DIR, "data", "tantivy_index")
KUZU_DIR = os.path.join(ENGINE_DIR, "data", "kuzu_graph", "knowledge.db")


# ════════════════════════════════════════════════════════════════
#  工具函数
# ════════════════════════════════════════════════════════════════

def get_book_info(book_id):
    """获取书籍基本信息+原文"""
    idx = BookIndex(TANTIVY_DIR)
    body_raw = idx.get_body_raw(book_id) or ""
    meta = idx.get_book_meta(book_id)

    title, author = book_id, ""
    try:
        kg = KnowledgeGraph(KUZU_DIR)
        r = kg.conn.execute("MATCH (b:Book {book_id: $bid}) RETURN b.title, b.author", {"bid": book_id})
        if r.has_next():
            row = r.get_next()
            if row[0]: title = row[0]
            if row[1]: author = row[1]
        kg.close()
    except: pass

    if meta:
        title = meta.get("title", title)
        author = meta.get("author", author)

    # 提取章节
    chapters = []
    if body_raw:
        for pat in [
            re.compile(r'^#{1,3}\s+(第[一二三四五六七八九十百千]+[章节讲篇部]|[0-9]+[\.\、].*)', re.MULTILINE),
            re.compile(r'^(第[一二三四五六七八九十百千]+[章节讲篇部].*)', re.MULTILINE),
        ]:
            found = pat.findall(body_raw)
            if len(found) >= 2:
                chapters = [c.strip().replace("#","").strip() for c in found[:50]]
                break

    return {
        "id": book_id,
        "title": title,
        "author": author,
        "body_raw": body_raw,
        "wc": len(body_raw),
        "chapters": chapters,
    }


def verify_evidence(book_id, evidence):
    """Layer 2: 验证 evidence 是否存在于正文中"""
    info = get_book_info(book_id)
    body = info["body_raw"]
    if not evidence:
        return False, "evidence 为空"
    if evidence in body:
        return True, "evidence 存在于正文"
    else:
        return False, "evidence 不存在于正文 — 这可能是幻觉"


# ════════════════════════════════════════════════════════════════
#  命令处理
# ════════════════════════════════════════════════════════════════

def cmd_store(book_id, dim, content, evidence="", imp=5):
    """存入一条理解（带 evidence 验证）"""
    # Layer 2 验证
    if evidence:
        ok, msg = verify_evidence(book_id, evidence)
        if not ok:
            print(f"  ❌ Layer 2 拦截: {msg}")
            print(f"  🚫 理解未存入")
            return False
        print(f"  ✅ Layer 2 通过: {msg}")

    u = Understanding()
    u.register_book(book_id, book_id, word_count=0)
    u.add_comprehension(book_id, dim, content, imp, evidence, 0)
    print(f"  💾 已存入: [{dim}] {content[:80]}...")
    return True


def cmd_status(book_id):
    """查看本书已存的理解和章节进度"""
    info = get_book_info(book_id)
    u = Understanding()
    comps = u.get_comprehensions(book_id)
    book = u.get_book(book_id)

    print(f"\n{'━'*56}")
    print(f"  📖 {info['title']}  {info['author']}")
    print(f"  📏 {info['wc']:,} 字  |  章节 {len(info['chapters'])}")
    print(f"  {'─'*40}")

    if book:
        print(f"  状态: {book.get('status','未知')}")
    print(f"  已存理解: {len(comps)} 条")

    # 按维度分组显示
    by_dim = {}
    for c in comps:
        by_dim.setdefault(c['dimension'], []).append(c)

    print(f"\n  各维度进度:")
    for dim, items in sorted(by_dim.items()):
        ev = "✅" if all(i.get('evidence') for i in items) else "⚠️"
        print(f"    {ev} {dim} ({len(items)} 条)")

    # 未存入的章节
    if info['chapters']:
        stored_dims = set(by_dim.keys())
        unread_chs = [ch for ch in info['chapters'] if ch not in stored_dims
                      and not any(ch in sd for sd in stored_dims)]
        if unread_chs:
            print(f"\n  未读章节:")
            for ch in unread_chs[:10]:
                print(f"    📄 {ch}")
            if len(unread_chs) > 10:
                print(f"    ... 还有 {len(unread_chs)-10} 章")

    # 概念
    concepts = u.get_concepts_for_book(book_id)
    if concepts:
        print(f"\n  概念 ({len(concepts)}):")
        for c in concepts[:5]:
            print(f"    🔗 {c['name']}")
    print()


def cmd_mark_chapter(book_id, chapter):
    """标记某章已读"""
    u = Understanding()
    u.add_comprehension(book_id, "书签", f"已读完: {chapter}", 1)
    print(f"  ✅ 标记已读: {chapter}")


def cmd_audit(book_id):
    """Layer 3: 闭卷审计"""
    u = Understanding()
    comps = u.get_comprehensions(book_id)

    if len(comps) < 3:
        print(f"  ⚠️  理解条目不足 ({len(comps)})，需要至少 3 条才能审计")
        return False

    sample = random.sample(comps, min(5, len(comps)))
    print(f"\n{'━'*56}")
    print(f"  📝 Layer 3: 闭卷审计")
    print(f"  {'━'*30}")
    info = get_book_info(book_id)
    print(f"  📖 {info['title']}")
    print(f"  从 {len(comps)} 条理解中抽 {len(sample)} 条")
    print()

    for i, item in enumerate(sample):
        ev = item.get("evidence", "")
        dim = item["dimension"]
        content = item["content"][:100]
        print(f"  Q{i+1}: 关于「{dim}」— {content}...")
        print(f"    原文引用: \"{ev[:60]}...\"")
        print(f"  A: [凭记忆作答，不可回看原文]")
        print()

    # 证据验证
    ev_samples = random.sample(comps, min(3, len(comps)))
    ev_pass = 0
    body = get_book_info(book_id)["body_raw"]

    print(f"  {'─'*40}")
    print(f"  证据验证 ({len(ev_samples)} 条):")
    for item in ev_samples:
        ev = item.get("evidence", "")
        content = item["content"][:60]
        if ev and ev in body:
            ev_pass += 1
            print(f"    ✅ {content}... → evidence 在正文中存在")
        else:
            print(f"    ❌ {content}... → evidence 不存在!")

    ev_rate = ev_pass / len(ev_samples) if ev_samples else 1.0
    print(f"\n  证据验证: {ev_pass}/{len(ev_samples)} ({ev_rate*100:.0f}%)")

    if ev_rate >= 0.8:
        print(f"\n  ✅ 双重审计通过! (闭卷 + 证据验证)")
        return True
    else:
        print(f"\n  ⚠️  审计未通过 — evidence 验证失败 ({ev_rate*100:.0f}% < 80%)")
        return False


def cmd_mark_read(book_id):
    """标记整本书已读"""
    u = Understanding()
    u.mark_read(book_id)
    info = get_book_info(book_id)
    comps = u.get_comprehensions(book_id)
    concepts = u.get_concepts_for_book(book_id)
    print(f"\n  ✅ 已标记已读: 《{info['title']}》")
    print(f"  共 {len(comps)} 条理解, {len(concepts)} 个概念")
    print()


def cmd_info(book_id):
    """显示书籍信息和原文预览"""
    info = get_book_info(book_id)
    print(f"\n{'━'*56}")
    print(f"  📖 {info['title']}  {info['author']}")
    print(f"{'━'*56}")
    print(f"  📏 {info['wc']:,} 字")
    if info['chapters']:
        print(f"  📚 {len(info['chapters'])} 章:")
        for ch in info['chapters'][:15]:
            print(f"    · {ch}")
        if len(info['chapters']) > 15:
            print(f"    ... 还有 {len(info['chapters'])-15} 章")

    # 原文预览（前500字）
    if info['body_raw']:
        preview = info['body_raw'][:500]
        print(f"\n  📋 原文预览 (前500字符):")
        for line in preview.split("\n")[:8]:
            line = line.strip()
            if line:
                print(f"    {line[:120]}")
    print()


def cmd_list():
    """列出未读书籍"""
    u = Understanding()
    unread = u.get_unread_books(30)
    if not unread:
        print("\n  📚 未读：无")
        return
    print(f"\n{'━'*56}")
    print(f"  📚 未读 {len(unread)} 本")
    print(f"{'━'*56}")
    for i, b in enumerate(unread):
        wc = b.get("word_count", 0) or 0
        level = "S" if wc <= 50000 else "A" if wc <= 200000 else "B" if wc <= 500000 else "C"
        print(f"  {i+1:2d}. [{level}] {b['id']}")
    print(f"\n  用 info 查看详情: python3 scripts/store_understanding.py <id> info")


# ════════════════════════════════════════════════════════════════
#  主入口
# ════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    book_id = sys.argv[1]

    if book_id == "--list":
        cmd_list()
        return

    if len(sys.argv) < 3:
        # 没有子命令 -> 显示 info
        cmd_info(book_id)
        return

    cmd = sys.argv[2]

    if cmd == "store":
        # store <book_id> store --dim "..." --content "..." --evidence "..." --imp N
        dim = ""
        content = ""
        evidence = ""
        imp = 5
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--dim" and i+1 < len(sys.argv):
                dim = sys.argv[i+1]; i += 2
            elif sys.argv[i] == "--content" and i+1 < len(sys.argv):
                content = sys.argv[i+1]; i += 2
            elif sys.argv[i] == "--evidence" and i+1 < len(sys.argv):
                evidence = sys.argv[i+1]; i += 2
            elif sys.argv[i] == "--imp" and i+1 < len(sys.argv):
                imp = int(sys.argv[i+1]); i += 2
            else:
                i += 1
        if not dim or not content:
            print("❌ 需要 --dim 和 --content")
            return
        cmd_store(book_id, dim, content, evidence, imp)

    elif cmd == "status":
        cmd_status(book_id)

    elif cmd == "mark-chapter" and len(sys.argv) >= 4:
        chapter = sys.argv[3]
        cmd_mark_chapter(book_id, chapter)

    elif cmd == "audit":
        passed = cmd_audit(book_id)
        if passed:
            print()
            print(f"  💡 审计通过后运行: store_understanding.py {book_id} mark-read")
        print()

    elif cmd == "mark-read":
        cmd_mark_read(book_id)

    elif cmd == "info":
        cmd_info(book_id)

    else:
        print(f"❌ 未知命令: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
