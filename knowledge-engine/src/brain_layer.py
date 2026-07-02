#!/usr/bin/env python3
"""
知识引擎 — 合成回答层 + 知识缺口分析

纯算法实现，零 LLM 依赖。
"""
import re
import os
import sys
from collections import Counter

# 支持直接运行
if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tantivy_index import BookIndex
from src.kuzu_graph import KnowledgeGraph
from src.book_pipeline import BookPipeline


# 相关性分数阈值
SCORE_FLOOR = 0.05


def _load_pipeline():
    from src.config import TANTIVY_INDEX_DIR, KUZU_DB_PATH
    index_path = TANTIVY_INDEX_DIR if os.path.exists(TANTIVY_INDEX_DIR) else None
    graph_path = KUZU_DB_PATH if os.path.exists(KUZU_DB_PATH) else None
    idx = BookIndex(index_path) if index_path else None
    kg = KnowledgeGraph(graph_path) if graph_path else None
    return idx, kg


def search(query, limit=10):
    """搜索并返回结构化结果"""
    with BookPipeline(persistent=True) as pipe:
        results = pipe.search(query, limit=limit)
    return results


def synthesize(query, limit=5):
    """合成回答：将搜索结果组织成带引用的结构化回答
    
    纯算法实现，按来源分组 + 提取匹配句。
    """
    results = search(query, limit=limit)
    if not results:
        return {
            'query': query,
            'answer': f"知识库中未找到与「{query}」相关的内容。",
            'sources': [],
            'confidence': 0.0,
        }

    # 按来源分组
    groups = {}
    for r in results:
        src = r.get('source', 'unknown')
        if src not in groups:
            groups[src] = []
        groups[src].append(r)

    # 构建回答
    lines = []
    sources = []
    total_score = sum(r.get('score', 0) for r in results)
    
    # 按主题归类
    seen_titles = set()
    for r in results:
        title = r.get('title', '')
        if title in seen_titles:
            continue
        seen_titles.add(title)
        
        score = r.get('score', 0)
        author = r.get('author', '') or ''
        lang = r.get('lang', '') or ''
        source = r.get('source', '')
        
        score_pct = f"{score:.1%}" if score < 1 else f"{score:.2f}"
        
        sources.append({
            'title': title,
            'author': author,
            'score': score,
            'source': source,
            'lang': lang,
        })
        
        lines.append(f"- **{title}**")
        if author:
            lines[-1] += f"（{author}）"
        lines[-1] += f" [得分:{score_pct}, 来源:{source}]"
    
    # 综合判断
    top_score = results[0].get('score', 0) if results else 0
    avg_score = total_score / len(results) if results else 0
    confidence = min(1.0, avg_score * 2)
    
    # 构建总结
    summary_parts = []
    if top_score > 0.5:
        summary_parts.append(f"已找到高度相关的内容（最佳匹配得分{top_score:.0%}）。")
    elif top_score > 0.2:
        summary_parts.append(f"找到部分相关内容（最佳匹配得分{top_score:.0%}）。")
    else:
        summary_parts.append(f"找到的结果相关性较低（最佳匹配得分{top_score:.0%}）。")
    
    answer = '\n'.join([
        f"## 关于「{query}」\n",
        ' '.join(summary_parts),
        '',
        '### 相关来源',
        '',
        '\n'.join(lines),
    ])
    
    return {
        'query': query,
        'answer': answer,
        'sources': sources,
        'confidence': confidence,
        'total_hits': len(results),
    }


def gap_analysis(query):
    """知识缺口分析：找出知识引擎知道什么、不知道什么
    
    纯算法，基于：
    1. 搜索结果覆盖率
    2. 相关概念在 Kùzu 中的存在度
    3. 查询涉及的知识领域覆盖面
    """
    results = search(query, limit=20)
    
    if not results:
        # 完全不相关 → 直接反映
        return {
            'query': query,
            'known': [],
            'gaps': [f"知识库中没有「{query}」相关的内容"],
            'suggestions': [f"建议导入与「{query}」相关的书籍或文献"],
            'coverage': 0.0,
        }
    
    known_topics = set()
    gaps = []
    suggestions = []
    
    # 1. 从搜索结果提取已知话题
    for r in results:
        title = r.get('title', '')
        cat = r.get('category', '未分类')
        known_topics.add(cat)
    
    # 2. 从 Kùzu 图谱检查相关概念
    try:
        from src.kuzu_graph import KnowledgeGraph
        from src.config import KUZU_DB_PATH
        if os.path.exists(KUZU_DB_PATH):
            kg = KnowledgeGraph(KUZU_DB_PATH)
            # 检查查询词是否作为概念存在
            r_check = kg.conn.execute(
                f"MATCH (c:Concept) WHERE c.name CONTAINS '{query.replace(chr(39), chr(39)+chr(39))}' RETURN c.name, c.category LIMIT 5"
            )
            concepts_found = []
            while r_check.has_next():
                row = r_check.get_next()
                concepts_found.append(row[0])
            kg.close()
            
            if concepts_found:
                known_topics.add('概念节点')
    except:
        pass
    
    # 3. 计算覆盖率
    total_possible = max(len(results), 1)
    coverage = min(1.0, total_possible / 10)
    
    # 4. 寻找知识缺口
    if len(results) < 3:
        gaps.append(f"只找到 {len(results)} 个相关来源，信息可能不完整")
        suggestions.append("尝试使用更具体的搜索词，或导入更多相关书籍")
    
    # 检查结果时效性（检测是否有近期的来源）
    has_recent = any(r.get('score', 0) > 0.1 for r in results[:3])
    if not has_recent and results:
        gaps.append("相关内容的匹配得分偏低，可能需要更深入的相关资料")
        suggestions.append("导入更多覆盖该主题的专业书籍")
    
    # 如果全在一个来源，提醒可能存在偏倚
    sources_set = set(r.get('source', '') for r in results)
    if len(sources_set) <= 1 and len(results) > 0:
        gaps.append("所有结果来自单一检索路径，可考虑增加多样性")
        suggestions.append("导入覆盖不同视角的参考资料")
    
    return {
        'query': query,
        'known': sorted(known_topics),
        'gaps': gaps if gaps else ["未发现明显的知识缺口"],
        'suggestions': suggestions if suggestions else ["当前的知识覆盖良好"],
        'coverage': round(coverage, 2),
        'total_found': len(results),
        'top_score': round(results[0].get('score', 0), 4) if results else 0,
    }


# 测试
if __name__ == '__main__':
    import sys
    query = ' '.join(sys.argv[1:]) or '线性代数'
    
    print(f'\n🔍 查询: {query}')
    print('=' * 50)
    
    # 合成回答
    synth = synthesize(query)
    print(f'\n📝 合成回答 (置信度: {synth["confidence"]:.0%}):')
    print(synth['answer'])
    
    # 缺口分析
    gap = gap_analysis(query)
    print(f'\n🔎 知识缺口分析 (覆盖率: {gap["coverage"]:.0%}):')
    print(f'  已知领域: {", ".join(gap["known"])}')
    print(f'  缺口: ')
    for g in gap['gaps']:
        print(f'    ⚠️  {g}')
    print(f'  建议: ')
    for s in gap['suggestions'][:2]:
        print(f'    💡  {s}')
