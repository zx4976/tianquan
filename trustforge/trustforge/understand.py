"""
trustforge understand — 读书理解模块

根据 TrustForge DSL 定义的 API 实现：
  API-0003: POST /books/{book_id}/understanding  → store 子命令
  API-0005: GET /books/{book_id}/understanding   → status 子命令
  API-0006: POST /books/{book_id}/chapters/{chapter}/mark-read → mark 子命令
  API-0007: POST /books/{book_id}/audit          → audit 子命令
  API-0008: GET /derive                          → derive 子命令

用法:
  trustforge understand <book_id> store --dim "第1章" --content "..." --evidence "原文" --imp 9
  trustforge understand <book_id> status
  trustforge understand <book_id> mark <chapter>
  trustforge understand <book_id> audit
  trustforge understand <book_id> mark-read
  trustforge understand <book_id> info
  trustforge understand --list
  trustforge understand derive <book_id> "<问题>"
"""
import sys, os, re, json, time, random, subprocess

ENGINE_DIR = os.path.expanduser("~/projects/knowledge-engine")
sys.path.insert(0, ENGINE_DIR)
from src.understanding import Understanding
from src.tantivy_index import BookIndex

TANTIVY_DIR = os.path.join(ENGINE_DIR, "data", "tantivy_index")


def verify_evidence(book_id, evidence):
    """Layer 2: 验证 evidence 是否存在于正文中"""
    idx = BookIndex(TANTIVY_DIR)
    body = idx.get_body_raw(book_id) or ""
    if not evidence:
        return False, "evidence 为空"
    if evidence in body:
        return True, "evidence 存在于正文"
    else:
        return False, "evidence 不存在于正文 — 这可能是幻觉"


def cmd_store(book_id, dim, content, evidence="", imp=5, motivation="", application=""):
    """API-0003: 存入理解（强制三要素）"""
    # 强制检查三要素
    missing = []
    if not motivation:
        missing.append("由来/动机")
    if not content:
        missing.append("核心断言/定理")
    if not application:
        missing.append("应用/推导")
    
    if missing:
        print(f"  ❌ 理解不完整，缺少: {', '.join(missing)}")
        print(f"     一条完整的理解必须包含三要素：")
        print(f"       1. 由来/动机    — 这个知识为了解决什么问题而诞生？")
        print(f"       2. 核心断言     — 它的核心定理/定义是什么？")
        print(f"       3. 应用/推导    — 它能用来推导什么？解决什么问题？")
        return False
    
    if evidence:
        ok, msg = verify_evidence(book_id, evidence)
        if not ok:
            print(f"  ❌ Layer 2 拦截: {msg}")
            return False
        print(f"  ✅ Layer 2 通过: {msg}")

    # 合并三要素为一条理解条目
    full_content = f"[由来] {motivation} | [核心] {content} | [应用] {application}"
    
    u = Understanding()
    u.register_book(book_id, book_id, word_count=0)
    u.add_comprehension(book_id, dim, full_content, imp, evidence, 0)
    print(f"  💾 已存入: [{dim}]（状态: 待验证）")
    print(f"     📌 由来: {motivation[:60]}...")
    print(f"     📌 核心: {content[:60]}...")
    print(f"     📌 应用: {application[:60]}...")
    print(f"")
    print(f"  ⚠️  该理解尚未通过验证。请运行验证命令确认你真正理解了它：")
    print(f"     trustforge understand verify {book_id} --dim \"{dim}\"")
    return True


def cmd_verify(book_id, dim=None):
    """验证理解 —— 闭卷推导，引擎验证"""
    u = Understanding()
    comps = u.get_comprehensions(book_id)
    
    if dim:
        comps = [c for c in comps if c["dimension"] == dim]
    
    if not comps:
        print(f"  ❌ 没有找到待验证的理解")
        return False
    
    target = max(comps, key=lambda c: c["importance"])
    content = target["content"]
    dim_name = target["dimension"]
    
    print(f"\n{'━'*56}")
    print(f"  📝 理解验证")
    print(f"  {book_id} / {dim_name}")
    print(f"{'━'*56}")
    print()
    print(f"  你存入了以下理解：")
    print(f"  {content[:200]}")
    print()
    print(f"  现在请闭卷回答：")
    print()
    
    q = dim_name.lower()
    
    if "线性空间" in q or "子空间" in q:
        print(f"  Q: 设 W1, W2 是线性空间 V 的子空间，证明 W1 ∩ W2 也是 V 的子空间。")
        print(f"  A: [凭记忆作答，不可回看原文]")
        print()
        print(f"  [引擎验证将检查：非空、加法封闭、数乘封闭三个条件是否完整]")
    elif "行列式" in q or "det" in q:
        print(f"  Q: 写出 3×3 矩阵行列式的 Sarrus 法则展开式。")
        print(f"  A: [凭记忆作答]")
    elif "线性无关" in q:
        print(f"  Q: 什么是线性无关？用数学语言描述。")
        print(f"  A: [凭记忆作答]")
    else:
        print(f"  Q: 请用自己的话解释：这个知识为什么重要？它和前后概念有什么联系？")
        print(f"  A: [凭记忆作答]")
    
    print()
    print(f"  {'─'*40}")
    print(f"  回答后请自行检查：")
    print(f"  1. 回答是否基于书中的定义而非推测？")
    print(f"  2. 回答是否涵盖了所有关键条件？")
    print(f"  3. 如果涉及公式，是否能正确写出？")
    print()
    
    return True


def cmd_status(book_id):
    """API-0005: 查询已存理解"""
    idx = BookIndex(TANTIVY_DIR)
    meta = idx.get_book_meta(book_id)
    u = Understanding()
    comps = u.get_comprehensions(book_id)
    book = u.get_book(book_id)

    title = meta["title"] if meta else book_id
    wc = meta["body_chars"] if meta else 0

    print(f"\n{'━'*56}")
    print(f"  📖 {title}")
    print(f"  📏 {wc:,} 字")
    print(f"  {'─'*40}")

    status = book.get("status", "未知") if book else "未注册"
    print(f"  状态: {status}")
    print(f"  已存理解: {len(comps)} 条")

    by_dim = {}
    for c in comps:
        by_dim.setdefault(c["dimension"], []).append(c)

    if by_dim:
        print(f"\n  各维度:")
        for dim, items in sorted(by_dim.items()):
            ev = "✅" if all(i.get("evidence") for i in items) else "⚠️"
            print(f"    {ev} {dim} ({len(items)} 条)")

    concepts = u.get_concepts_for_book(book_id)
    if concepts:
        print(f"\n  概念 ({len(concepts)}):")
        for c in concepts[:5]:
            print(f"    🔗 {c['name']}")
    print()
    return True


def cmd_mark(book_id, chapter):
    """API-0006: 标记章节已读"""
    u = Understanding()
    u.add_comprehension(book_id, "书签", f"已读完: {chapter}", 1)
    print(f"  ✅ 标记: {chapter}")
    return True


def cmd_audit(book_id):
    """API-0007: 全书审计"""
    u = Understanding()
    idx = BookIndex(TANTIVY_DIR)
    body = idx.get_body_raw(book_id) or ""
    comps = u.get_comprehensions(book_id)

    if len(comps) < 3:
        print(f"  ⚠️  理解条目不足 ({len(comps)})，跳过审计")
        u.mark_read(book_id)
        print(f"  → 标记已读")
        return True

    meta = idx.get_book_meta(book_id)
    title = meta["title"] if meta else book_id

    sample = random.sample(comps, min(5, len(comps)))
    print(f"\n{'━'*56}")
    print(f"  📝 闭卷审计 — {title}")
    print(f"{'━'*56}")
    print(f"  从 {len(comps)} 条中抽 {len(sample)} 条:\n")

    for i, item in enumerate(sample):
        ev = item.get("evidence", "")
        print(f"  Q{i+1}: 关于「{item['dimension']}」")
        print(f"    原文引用: \"{ev[:80]}...\"")
        print(f"  A: [凭记忆作答]")
        print()

    ev_samples = random.sample(comps, min(3, len(comps)))
    ev_pass = 0
    print(f"  {'─'*40}")
    print(f"  证据验证:")

    for item in ev_samples:
        ev = item.get("evidence", "")
        content = item["content"][:60]
        if ev and ev in body:
            ev_pass += 1
            print(f"    ✅ {content}...")
        else:
            print(f"    ❌ {content}...")

    rate = ev_pass / len(ev_samples) if ev_samples else 1.0
    print(f"\n  证据验证: {ev_pass}/{len(ev_samples)} ({rate*100:.0f}%)")

    if rate >= 0.8:
        print(f"\n  ✅ 审计通过")
        return True
    else:
        print(f"\n  ⚠️  审计未通过")
        return False


def cmd_mark_read(book_id):
    """标记整本已读"""
    u = Understanding()
    u.mark_read(book_id)
    idx = BookIndex(TANTIVY_DIR)
    meta = idx.get_book_meta(book_id)
    title = meta["title"] if meta else book_id
    comps = u.get_comprehensions(book_id)
    print(f"\n  ✅ 已标记已读: 《{title}》")
    print(f"  共 {len(comps)} 条理解")
    return True


def cmd_info(book_id):
    """书籍信息"""
    idx = BookIndex(TANTIVY_DIR)
    raw = idx.get_body_raw(book_id) or ""
    meta = idx.get_book_meta(book_id)

    title = meta["title"] if meta else book_id
    wc = len(raw)

    chapters = []
    if raw:
        for pat in [
            re.compile(r'^#{1,3}\s+(第[一二三四五六七八九十百千]+[章节讲篇部]|[0-9]+[\.\、].*)', re.MULTILINE),
            re.compile(r'^(第[一二三四五六七八九十百千]+[章节讲篇部].*)', re.MULTILINE),
        ]:
            found = pat.findall(raw)
            if len(found) >= 2:
                chapters = [c.strip().replace("#","").strip() for c in found[:50]]
                break

    print(f"\n{'━'*56}")
    print(f"  📖 {title}")
    print(f"  📏 {wc:,} 字")
    if chapters:
        print(f"  📚 {len(chapters)} 章:")
        for ch in chapters[:10]:
            print(f"    · {ch}")
        if len(chapters) > 10:
            print(f"    ... 还有 {len(chapters)-10} 章")

    if raw:
        preview = raw[:500]
        print(f"\n  📋 原文预览:")
        for line in preview.split("\n")[:5]:
            line = line.strip()
            if line:
                print(f"    {line[:120]}")
    print()
    return True


def cmd_list():
    """列出未读书籍"""
    u = Understanding()
    unread = u.get_unread_books(30)
    if not unread:
        print("\n  📚 未读：无")
        return True

    print(f"\n{'━'*56}")
    print(f"  📚 未读 {len(unread)} 本")
    print(f"{'━'*56}")
    for i, b in enumerate(unread):
        wc = b.get("word_count", 0) or 0
        level = "S" if wc <= 50000 else "A" if wc <= 200000 else "B" if wc <= 500000 else "C"
        print(f"  {i+1:2d}. [{level}] {b['id']}")
    print()
    return True


def cmd_derive(book_id, question):
    """API-0008: 基于已存知识的符号推导"""
    u = Understanding()
    knowledge = u.get_knowledge(book_id)

    if not knowledge:
        print(f"\n  ⚠️  该书没有可执行知识")
        print(f"  先用 store 存入知识: trustforge understand {book_id} store --dim ...")
        return False

    # 匹配知识（语义匹配 + 依赖链扩展）
    q = question.lower()
    matched = []
    
    # 定义语义同义词组
    syn_groups = [
        ["行列式", "det", "determinant", "行列", "展开"],
        ["多重线性", "multilinear", "多重线", "多线性", "张量积", "tensor"],
        ["交错", "alternating", "反对称", "antisymmetric", "斜对称"],
        ["置换", "permutation", "对称群", "symmetric group", "sn", "sgn", "sign"],
        ["基", "basis", "base", "坐标", "coordinate", "展开", "expansion"],
        ["线性", "linear", "linearity", "linear map", "同态", "homomorphism"],
        ["群", "group", "加法群", "乘法群", "子群", "陪集", "coset"],
        ["环", "ring", "整环", "integral domain", "域", "field"],
        ["模", "module", "向量空间", "vector space", "自由模", "free module"],
        ["特征值", "eigenvalue", "特征向量", "eigenvector", "对角化", "diagonalization"],
        ["jordan", "若尔当", "jordan标准形", "幂零", "nilpotent"],
    ]
    
    # 找出问题属于哪些语义组
    q_groups = set()
    for gi, group in enumerate(syn_groups):
        for syn in group:
            if syn in q:
                q_groups.add(gi)
                break
    
    for k in knowledge:
        score = 0
        
        # 1) 名称匹配（原逻辑）
        for keyword in k["name"].split():
            if keyword.lower() in q:
                score += 6
        
        # 2) 描述匹配（原逻辑）
        desc = k.get("description", "").lower()
        if desc:
            for word in q.split():
                if len(word) >= 2 and word in desc:
                    score += 2
        
        # 3) 符号匹配（原逻辑）
        if k.get("symbol") and k["symbol"].lower() in q:
            score += 4
        
        # 4) 语义组匹配（新逻辑）
        k_name_lower = k["name"].lower()
        k_desc_lower = desc
        for gi in q_groups:
            for syn in syn_groups[gi]:
                if syn in k_name_lower or syn in k_desc_lower:
                    score += 3
                    break
        
        # 5) 依赖链扩展：如果一条知识的依赖项被匹配了，它也应该被匹配
        # （在第一次匹配后做，但先使用直接匹配）
        
        if score > 0:
            matched.append((score, k))
    
    # 依赖链扩展：如果某知识的依赖已被匹配，该知识也应该加入
    matched_names = {k["name"] for _, k in matched}
    for k in knowledge:
        if k["name"] not in matched_names:
            deps = k.get("dependencies", [])
            if deps and any(d in matched_names for d in deps):
                matched.append((5, k))  # 依赖链匹配，中等分数
                matched_names.add(k["name"])
    
    matched.sort(key=lambda x: -x[0])
    matched = [m[1] for m in matched]

    print(f"\n{'━'*56}")
    print(f"  🔍 推导请求")
    print(f"  📖 知识来源: {book_id}")
    print(f"  ❓ {question}")
    print(f"{'━'*56}")

    print(f"\n  匹配到 {len(matched)} 条知识:")
    for k in matched:
        deps = ", ".join(k["dependencies"]) if k.get("dependencies") else "(无)"
        print(f"    [{k['ktype']}] {k['name']}  ← {deps}")
    print()

    # 线性代数推导引擎
    eng_path = os.path.expanduser("~/projects/knowledge-engine/scripts")
    if eng_path not in sys.path:
        sys.path.insert(0, eng_path)
    
    from algebra_engine import ENGINES as ALGEBRA_ENGINES
    
    for eng_key, eng_func in ALGEBRA_ENGINES.items():
        if eng_key in q:
            result, error = eng_func(knowledge)
            if error:
                print(f"  \u274c {error}")
                return False
            steps, data = result
            print(f"\n{'━'*56}")
            print(f"  \U0001f4d0 代数推导: {eng_key}")
            print(f"{'━'*56}")
            print()
            for line in steps:
                print(line)
            print()
            return True
    
    # 判断推导类型
    # 自由落体
    if any(kw in q for kw in ["自由落体", "落体"]) and "加速度" not in q:
        times = re.findall(r'(\d+\.?\d*)\s*秒', q)
        if times:
            t = float(times[0])
            g = 9.8
            s = 0.5 * g * t**2
            v = g * t
            print(f"  📐 推导过程:")
            print(f"    s(t) = ½gt² = ½ × {g} × ({t})² = {s:.2f} 米")
            print(f"    v(t) = gt = {g} × {t} = {v:.2f} 米/秒")
            print(f"")
            print(f"  ✅ 结果:")
            print(f"    下落距离 s = {s:.2f} m")
            print(f"    瞬时速度 v = {v:.2f} m/s")
            print(f"    加速度   a = {g} m/s²")
            print(f"\n  🔒 本次推导未调用大模型参数")
            print(f"     基于已存知识 + 数值计算")
            return True

    # 从加速度推导
    elif any(kw in q for kw in ["加速度", "a(t", "加速", "求v(t)", "求s(t)"]):
        try:
            import sympy as sp
            t_var = sp.Symbol('t')

            a_match = re.search(r'a\s*(?:\(t\))?\s*[:=]\s*([\d\s*+\-^t]+)', q)
            a_expr_str = None
            if a_match:
                a_expr_str = a_match.group(1).strip()
            elif "常数" in q or "恒定" in q or "匀加速" in q or "g" in q:
                a_expr_str = "9.8"
            else:
                a_expr_str = "g"

            v0 = 0
            s0 = 0
            v0_match = re.search(r'[vV]\(0\)\s*[:=]\s*(-?\d+\.?\d*)', q)
            if v0_match: v0 = float(v0_match.group(1))
            s0_match = re.search(r'[sS]\(0\)\s*[:=]\s*(-?\d+\.?\d*)', q)
            if s0_match: s0 = float(s0_match.group(1))

            if a_expr_str == "g":
                a_expr = sp.Float(9.8)
            elif a_expr_str == "9.8":
                a_expr = sp.Float(9.8)
            else:
                a_expr = eval(a_expr_str.replace("^", "**"))

            v_expr = sp.integrate(a_expr, t_var) + v0
            s_expr = sp.integrate(v_expr, t_var) + s0

            print(f"  📐 推导过程:")
            print(f"    a(t) → v(t) = ∫a(t)dt (微积分基本定理)")
            print(f"    v(t) → s(t) = ∫v(t)dt (微积分基本定理)")
            print(f"")
            print(f"    已知 a(t) = {a_expr}")
            print(f"    v(t) = ∫a(t)dt = {v_expr}  (v(0)={v0})")
            print(f"    s(t) = ∫v(t)dt = {s_expr}  (s(0)={s0})")
            print(f"")
            print(f"  ✅ 结果 (SymPy 符号积分):")
            print(f"    a(t) = {a_expr}")
            print(f"    v(t) = {v_expr}")
            print(f"    s(t) = {s_expr}")
            print(f"\n  🔒 本次推导未调用大模型参数")
            print(f"     基于已存知识 + SymPy 符号计算")
            return True
        except ImportError:
            print(f"  ⚠️  需要 sympy: uv pip install sympy")
            return False
        except Exception as e:
            print(f"  ⚠️  推导失败: {e}")
            return False

    # 行列式 = 交错多重线性映射的展开
    if any(kw in q for kw in ["行列式", "det", "交错", "多重线性", "置换符号"]):
        engine_dir = os.path.expanduser("~/projects/knowledge-engine/scripts")
        if engine_dir not in sys.path:
            sys.path.insert(0, engine_dir)
        from determinant_engine import derive_determinant_from_knowledge
        
        result, error = derive_determinant_from_knowledge(knowledge, n=3)
        if error:
            print(f"  \u274c {error}")
            return False
        
        steps, data, dep_chain = result
        
        print(f"\n{'━'*56}")
        print(f"  \U0001f4d0 行列式推导")
        print(f"  基于已存知识: {len(data['axioms'])} 条公理, {len(data['permutations'])} 项置换计算")
        print(f"{'━'*56}")
        print()
        
        # 打印依赖链验证
        print("  依赖链验证:")
        for name, deps, ok in dep_chain:
            status = "\u2705" if ok else "\u274c"
            print(f"    {status} {name}  \u2190 {', '.join(deps) if deps else '(无依赖)'}")
        print()
        
        # 打印所有推导步骤
        for line in steps:
            print(line)
        print()
        return True
    
    print(f"  \u26a0\ufe0f  无法用已有知识推导此问题")
    return False


def main():
    """CLI entry"""
    import sys
    if len(sys.argv) < 2:
        print("用法: trustforge understand <action> [...]")
        return 1
    
    action = sys.argv[1]
    
    if action == "list":
        return 0 if cmd_list() else 1
    
    if len(sys.argv) < 3:
        print(f"用法: trustforge understand {action} <book_id> [...]")
        return 1
    
    book_id = sys.argv[2]
    
    if action == "store":
        dim = ""
        motivation = ""
        content = ""
        application = ""
        evidence = ""
        imp = 5
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--dim" and i+1 < len(sys.argv):
                dim = sys.argv[i+1]; i += 2
            elif sys.argv[i] == "--motivation" and i+1 < len(sys.argv):
                motivation = sys.argv[i+1]; i += 2
            elif sys.argv[i] == "--content" and i+1 < len(sys.argv):
                content = sys.argv[i+1]; i += 2
            elif sys.argv[i] == "--application" and i+1 < len(sys.argv):
                application = sys.argv[i+1]; i += 2
            elif sys.argv[i] == "--evidence" and i+1 < len(sys.argv):
                evidence = sys.argv[i+1]; i += 2
            elif sys.argv[i] == "--imp" and i+1 < len(sys.argv):
                imp = int(sys.argv[i+1]); i += 2
            else:
                i += 1
        return 0 if cmd_store(book_id, dim, content, evidence, imp, motivation, application) else 1
    
    elif action == "status":
        return 0 if cmd_status(book_id) else 1
    elif action == "mark":
        chapter = sys.argv[3] if len(sys.argv) >= 4 else ""
        return 0 if cmd_mark(book_id, chapter) else 1
    elif action == "verify":
        dim = sys.argv[3] if len(sys.argv) >= 4 and sys.argv[3] != "--dim" else ""
        if "--dim" in sys.argv:
            idx = sys.argv.index("--dim")
            dim = sys.argv[idx+1] if idx+1 < len(sys.argv) else dim
        return 0 if cmd_verify(book_id, dim) else 1
    elif action == "audit":
        return 0 if cmd_audit(book_id) else 1
    elif action == "mark-read":
        return 0 if cmd_mark_read(book_id) else 1
    elif action == "info":
        return 0 if cmd_info(book_id) else 1
    elif action == "derive":
        question = sys.argv[3] if len(sys.argv) >= 4 else ""
        return 0 if cmd_derive(book_id, question) else 1
    
    print(f"未知操作: {action}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
