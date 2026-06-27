#!/usr/bin/env python3
"""
RRF (Reciprocal Rank Fusion) — 多路检索结果融合
纯数学，零依赖
"""

def rrf_fusion(ranked_lists, k=60):
    """
    融合多个检索器的排名结果。

    参数:
        ranked_lists: list[list[dict]], 每个元素是一个检索器的排名结果列表
                      每项 dict 必须包含 'id' 字段，可选包含 'title', 'score', 'source'
        k: int, RRF 常数，默认 60

    返回:
        list[dict]: 融合后的排名结果，每项包含原始字段 + rrf_score
    """
    scores = {}
    docs = {}

    for rank_list in ranked_lists:
        for rank, doc in enumerate(rank_list, start=1):
            doc_id = doc.get('id', str(hash(str(doc))))
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
            if doc_id not in docs:
                docs[doc_id] = {**doc, 'rrf_score': 0.0}

    # 写入 RRF 分数并按分数降序排列
    for doc_id in docs:
        docs[doc_id]['rrf_score'] = scores[doc_id]

    sorted_docs = sorted(docs.values(), key=lambda d: d['rrf_score'], reverse=True)
    return sorted_docs


def weighted_rrf_fusion(ranked_lists, weights, k=60):
    """
    带权重的 RRF 融合。
    
    参数:
        weights: list[float], 每个检索器的权重，长度必须与 ranked_lists 相同
    """
    if len(ranked_lists) != len(weights):
        raise ValueError("ranked_lists 和 weights 长度必须相同")

    scores = {}
    docs = {}

    for idx, rank_list in enumerate(ranked_lists):
        w = weights[idx]
        for rank, doc in enumerate(rank_list, start=1):
            doc_id = doc.get('id', str(hash(str(doc))))
            scores[doc_id] = scores.get(doc_id, 0.0) + w / (k + rank)
            if doc_id not in docs:
                docs[doc_id] = {**doc, 'rrf_score': 0.0}

    for doc_id in docs:
        docs[doc_id]['rrf_score'] = scores[doc_id]

    sorted_docs = sorted(docs.values(), key=lambda d: d['rrf_score'], reverse=True)
    return sorted_docs


if __name__ == '__main__':
    # 简单自测
    list1 = [{'id': 'a', 'title': '书A'}, {'id': 'b', 'title': '书B'}, {'id': 'c', 'title': '书C'}]
    list2 = [{'id': 'b', 'title': '书B'}, {'id': 'a', 'title': '书A'}, {'id': 'd', 'title': '书D'}]
    list3 = [{'id': 'a', 'title': '书A'}, {'id': 'd', 'title': '书D'}, {'id': 'e', 'title': '书E'}]

    fused = rrf_fusion([list1, list2, list3], k=60)
    print("RRF 融合结果:")
    for doc in fused:
        print(f"  {doc['title']}: rrf_score={doc['rrf_score']:.4f}")
    assert fused[0]['id'] == 'a', "书A 应在最前"
    assert fused[1]['id'] == 'b', "书B 应在第二"
    print("✅ RRF 自测通过")
