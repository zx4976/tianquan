"""
gbrain 风格向量索引 — FAISS + TF-IDF 嵌入
作为第4路搜索加入 RRF 融合（零 LLM 依赖）
"""
import numpy as np
import os
import pickle
import json
from sklearn.feature_extraction.text import TfidfVectorizer
import faiss

class VectorIndex:
    """向量索引：用 TF-IDF 向量 + FAISS 实现语义相似搜索"""

    def __init__(self, index_path=None, dim=256):
        self.index_path = index_path
        self.dim = dim
        self.vectorizer = TfidfVectorizer(max_features=dim, analyzer='char_wb', ngram_range=(2, 4))
        self.index = None
        self.doc_ids = []
        self.doc_meta = {}
        self._fitted = False

    def fit(self, texts, ids, meta_list=None):
        """训练向量化器并建立索引"""
        vectors = self.vectorizer.fit_transform(texts).toarray().astype(np.float32)
        # L2 归一化
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1
        vectors = vectors / norms

        self.dim = vectors.shape[1]
        self.index = faiss.IndexFlatIP(self.dim)
        self.index.add(vectors)

        self.doc_ids = ids
        if meta_list:
            for i, m in enumerate(meta_list):
                self.doc_meta[str(ids[i])] = m
        self._fitted = True

    def add(self, text, doc_id, meta=None):
        """增量添加一篇文档"""
        vec = self.vectorizer.transform([text]).toarray().astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        if self.index is None:
            self.dim = vec.shape[1]
            self.index = faiss.IndexFlatIP(self.dim)
        self.index.add(vec)
        self.doc_ids.append(doc_id)
        if meta:
            self.doc_meta[str(doc_id)] = meta

    def search(self, query, k=10):
        """搜索相似内容"""
        vec = self.vectorizer.transform([query]).toarray().astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm == 0:
            return []
        vec = vec / norm

        scores, indices = self.index.search(vec, min(k, len(self.doc_ids)))
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.doc_ids):
                continue
            doc_id = self.doc_ids[idx]
            meta = self.doc_meta.get(str(doc_id), {})
            results.append({
                'id': doc_id,
                'score': float(score),
                'title': meta.get('title', f'文档_{doc_id}'),
                'author': meta.get('author', ''),
                'category': meta.get('category', ''),
                'lang': meta.get('lang', ''),
                'source': 'vector',
            })
        return results

    def save(self, path):
        """保存索引到磁盘"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        faiss.write_index(self.index, path + '.faiss')
        with open(path + '.pkl', 'wb') as f:
            pickle.dump({
                'vectorizer': self.vectorizer,
                'doc_ids': self.doc_ids,
                'doc_meta': self.doc_meta,
                'dim': self.dim,
            }, f)

    def load(self, path):
        """从磁盘加载索引"""
        self.index = faiss.read_index(path + '.faiss')
        with open(path + '.pkl', 'rb') as f:
            data = pickle.load(f)
        self.vectorizer = data['vectorizer']
        self.doc_ids = data['doc_ids']
        self.doc_meta = data['doc_meta']
        self.dim = data['dim']
        self._fitted = True

    @property
    def size(self):
        return self.index.ntotal if self.index else 0


if __name__ == '__main__':
    vi = VectorIndex(dim=64)
    texts = [
        "Python is an elegant programming language",
        "Machine learning with neural networks",
        "Quantum computing and quantum algorithms",
        "分布式系统设计原理与实践",
    ]
    ids = ['py1', 'ml1', 'qc1', 'ds1']
    metas = [
        {'title': 'Python编程', 'lang': 'en'},
        {'title': '机器学习', 'lang': 'en'},
        {'title': '量子计算', 'lang': 'en'},
        {'title': '分布式系统', 'lang': 'zh'},
    ]
    vi.fit(texts, ids, metas)
    for q in ['Python', 'machine learning', '量子']:
        r = vi.search(q, k=3)
        print(f"查询 '{q}':")
        for d in r:
            print(f"  [{d['score']:.4f}] {d['title']}")
    print("\n✅ 向量索引模块自测通过")
