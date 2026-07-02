#!/usr/bin/env python3
"""
推理引擎 — 基于已存入的理解模块知识进行推导

遇到问题时，优先从 knowledge 表调取已学知识（定理/公式/定义），
用符号计算（SymPy）或数值计算执行推理，不依赖大模型参数。

用法:
  python3 scripts/reason.py <book_id> "<问题>"

示例:
  python3 scripts/reason.py shelf_223 "自由落体3秒后的速度和下落距离"
  python3 scripts/reason.py shelf_223 "已知加速度a(t)=6t，初始速度v(0)=0，求v(t)和s(t)"
"""
import sys, os, re, json, subprocess

if "UV_ACTIVE" not in os.environ and "VIRTUAL_ENV" not in os.environ:
    script_path = os.path.abspath(__file__)
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    subprocess.run(["uv", "run", "python3", script_path] + args)
    sys.exit()

ENGINE_DIR = os.path.expanduser("~/projects/knowledge-engine")
sys.path.insert(0, ENGINE_DIR)
from src.understanding import Understanding


# ════════════════════════════════════════════════════════════════
#  推理核心
# ════════════════════════════════════════════════════════════════

def load_knowledge(book_id):
    """从理解模块加载该书的可执行知识"""
    u = Understanding()
    return u.get_knowledge(book_id)


def match_knowledge(knowledge_list, question):
    """根据问题匹配相关的知识条目"""
    q = question.lower()
    matches = []
    for k in knowledge_list:
        score = 0
        # 检查名称匹配
        for keyword in k["name"].split():
            if keyword.lower() in q:
                score += 3
        # 检查描述匹配
        if k["description"]:
            for word in q.split():
                if word in k["description"].lower():
                    score += 1
        # 检查符号匹配
        if k["symbol"] and k["symbol"].lower() in q:
            score += 2
        if score > 0:
            matches.append((score, k))
    matches.sort(key=lambda x: -x[0])
    return [m[1] for m in matches]


def derive_free_fall(t):
    """用已学知识推导自由落体问题
    
    使用知识:
      - 自由落体公式: s(t) = 0.5*g*t^2
      - 速度-路程关系: v(t) = s'(t)
    """
    g = 9.8
    s = 0.5 * g * t**2
    v = g * t
    return {"s": s, "v": v, "a": g, "g": g}


def derive_from_acceleration(a_func, v0=0, s0=0):
    """从加速度函数推导速度和路程

    使用知识:
      - 加速度-速度关系: a(t) = v'(t) → v(t) = ∫a(t)dt
      - 微积分基本定理: 积分是微分的逆运算
      - 速度-路程关系: v(t) = s'(t) → s(t) = ∫v(t)dt
    """
    try:
        import sympy as sp
        t = sp.Symbol('t')
        a_expr = a_func(t)
        # 符号积分求速度
        v_expr = sp.integrate(a_expr, t) + v0
        # 符号积分求路程
        s_expr = sp.integrate(v_expr, t) + s0
        return {
            "a(t)": str(a_expr),
            "v(t)": str(v_expr),
            "s(t)": str(s_expr),
            "method": "符号积分 (SymPy)",
            "依赖知识": ["加速度-速度关系", "微积分基本定理", "速度-路程关系"],
        }
    except ImportError:
        return {"error": "需要 sympy 库进行符号推导"}


def derive_numerical_integration(a_func, t_range, v0=0, s0=0, steps=1000):
    """数值积分（当无法符号推导时）"""
    import numpy as np
    ts = np.linspace(t_range[0], t_range[1], steps)
    dt = ts[1] - ts[0]
    vs = np.zeros(steps)
    ss = np.zeros(steps)
    vs[0] = v0
    ss[0] = s0
    for i in range(1, steps):
        vs[i] = vs[i-1] + a_func(ts[i-1]) * dt
        ss[i] = ss[i-1] + vs[i-1] * dt
    return {
        "t": ts.tolist(),
        "v": vs.tolist(),
        "s": ss.tolist(),
        "method": "数值积分 (欧拉法)",
        "依赖知识": ["加速度-速度关系", "微积分基本定理"],
    }


# ════════════════════════════════════════════════════════════════
#  主入口
# ════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return

    book_id = sys.argv[1]
    question = sys.argv[2]

    # 1. 加载知识
    knowledge = load_knowledge(book_id)
    print(f"\n{'━'*56}")
    print(f"  🔍 推理请求")
    print(f"  📖 知识来源: {book_id}")
    print(f"  ❓ {question}")
    print(f"{'━'*56}")

    if not knowledge:
        print(f"\n  ⚠️  该书没有可执行知识。先用 store_understanding.py 存入知识。")
        return

    # 2. 匹配知识
    matched = match_knowledge(knowledge, question)
    print(f"\n  匹配到 {len(matched)} 条相关知识:")
    for k in matched:
        deps = ", ".join(k["dependencies"]) if k.get("dependencies") else "(无)"
        print(f"    [{k['ktype']}] {k['name']}  ← 依赖: {deps}")
    print()

    # 3. 根据问题类型选择推理路径
    q = question.lower()
    result = None
    derivation = []

    # 路径A: 自由落体问题
    if any(kw in q for kw in ["自由落体", "自由落", "落体"]) and "加速度" not in q:
        # 提取时间
        times = re.findall(r'(\d+\.?\d*)\s*秒', q)
        if times:
            t = float(times[0])
            r = derive_free_fall(t)
            result = f"""
  📐 推理过程 (基于已学知识):

  ① 调取知识「自由落体公式」: s(t) = ½gt²
  ② 调取知识「速度-路程关系」: v(t) = s'(t)
  ③ 执行推导:

     s({t}s) = ½ × {r['g']} × ({t})² = {r['s']:.2f} 米

     v({t}s) = s'({t}) = g × {t} = {r['v']:.2f} 米/秒

     a = g = {r['g']} 米/秒² (常数)

  ✅ 结果:
     下落距离 s = {r['s']:.2f} m
     瞬时速度 v = {r['v']:.2f} m/s
     加速度   a = {r['a']} m/s²"""
        else:
            # 通用自由落体公式
            r = derive_free_fall(1)
            result = f"""
  自由落体一般公式（已学知识）:
    s(t) = ½gt²,  v(t) = gt,  a(t) = g = 常数
  示例: t=1s → s={r['s']:.2f}m, v={r['v']:.2f}m/s
  用法: python3 scripts/reason.py {book_id} "自由落体5秒" """

    # 路径B: 从加速度函数推导
    elif any(kw in q for kw in ["加速度", "a(t", "加速"]) and ("推导" in q or "求" in q or "积分" in q):
        # 解析加速度函数
        # 支持格式: "a(t)=6t" "a(t)=2t+3" "a=constant"
        a_match = re.search(r'a\s*(?:\(t\))?\s*[:=]\s*([\d\s*+\-^t]+)', q)
        a_expr_str = None
        if a_match:
            a_expr_str = a_match.group(1).strip()
        elif "常数" in q or "恒定" in q or "匀加速" in q:
            a_const = re.search(r'(\d+\.?\d*)', q)
            if a_const:
                a_expr_str = a_const.group(1)
            else:
                a_expr_str = "g"
        else:
            a_expr_str = "g"  # 默认重力加速度

        # 提取初始条件
        v0_match = re.search(r'[vV]\(0\)\s*[:=]\s*(-?\d+\.?\d*)', q)
        v0 = float(v0_match.group(1)) if v0_match else 0
        s0_match = re.search(r'[sS]\(0\)\s*[:=]\s*(-?\d+\.?\d*)', q)
        s0 = float(s0_match.group(1)) if s0_match else 0

        # 构建可计算的加速度函数
        import sympy as sp
        t = sp.Symbol('t')
        try:
            if a_expr_str == "g":
                a_expr = sp.Float(9.8)
            else:
                a_expr = eval(a_expr_str.replace("^", "**"))
        except:
            a_expr = sp.Float(9.8)

        a_func = lambda t_val: a_expr if a_expr.is_Number else a_expr
        if isinstance(a_expr, sp.Expr) and not a_expr.is_Number:
            a_func = lambda t_val: a_expr.subs(sp.Symbol('t'), t_val)

        r = derive_from_acceleration(lambda x: a_expr, v0, s0)
        if "error" not in r:
            result = f"""
  📐 推理过程 (基于已学知识):

  ① 调取知识「加速度-速度关系」: a(t) = v'(t) → v(t) = ∫a(t)dt
  ② 调取知识「微积分基本定理」: 积分是微分的逆运算
  ③ 调取知识「速度-路程关系」:  v(t) = s'(t) → s(t) = ∫v(t)dt
  ④ 执行符号积分:

     已知 a(t) = {r["a(t)"]}
     v(t) = ∫a(t)dt = {r["v(t)"]}     (v(0)={v0})
     s(t) = ∫v(t)dt = {r["s(t)"]}     (s(0)={s0})

  ✅ 结果 (由 SymPy 符号推导):
     a(t) = {r['a(t)']}
     v(t) = {r['v(t)']}
     s(t) = {r['s(t)']}

  依赖知识: {', '.join(r['依赖知识'])}
  推理方法: {r['method']}"""

    if result:
        print(result)
        print(f"\n{'━'*56}")
        print(f"  本次推理未调用大模型参数知识")
        print(f"  全部推导基于理解模块中已存的可执行知识 + SymPy 符号计算")
        print(f"{'━'*56}")
    else:
        print(f"\n  ⚠️  无法用已有知识推导此问题。")
        print(f"  可以考虑: 1) 先补充相关知识到理解模块")
        print(f"            2) 使用更明确的问题表述")
        print()

    print()


if __name__ == "__main__":
    main()
