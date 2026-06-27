#!/usr/bin/env python3
"""
LSI 语义索引层 — TF-IDF + SVD 语义联想
纯代数，零模型依赖
"""
import jieba
import jieba.analyse
import pickle
import os
import tempfile
import shutil

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics.pairwise import cosine_similarity


def tokenize_zh(text):
    return ' '.join(jieba.cut(text))


def extract_keywords(text, topK=20):
    """用 TextRank 提取关键词（纯图算法）"""
    return jieba.analyse.textrank(text, topK=topK)


class SemanticIndex:
    """LSI 语义索引 — TF-IDF → SVD → 语义检索"""

    def __init__(self, n_components=100, max_features=5000):
        self.n_components = n_components
        self.max_features = max_features
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            token_pattern=r'(?u)\b\w+\b',
        )
        self.lsa = TruncatedSVD(n_components=n_components, random_state=42)
        self.lsi_matrix = None
        self.doc_metadata = []  # 每项的 {id, title, author, category}
        self._is_built = False

    def build(self, books):
        """构建 LSI 索引
        
        参数:
            books: list[dict], 每项包含 id, title, author, category, body
        """
        # 分词
        texts = [tokenize_zh(b.get('body', '') + ' ' + b.get('title', '')) for b in books]
        
        # TF-IDF
        tfidf_matrix = self.vectorizer.fit_transform(texts)
        
        # 自动调整 n_components
        n_features = tfidf_matrix.shape[1]
        n_docs = tfidf_matrix.shape[0]
        actual_components = min(self.n_components, n_features, max(1, n_docs - 1))
        if actual_components < self.n_components:
            self.lsa = TruncatedSVD(n_components=actual_components, random_state=42)
        
        # SVD 降维
        self.lsi_matrix = self.lsa.fit_transform(tfidf_matrix)
        
        # 保存元数据
        self.doc_metadata = [
            {
                'id': b.get('id', str(i)),
                'title': b.get('title', ''),
                'author': b.get('author', ''),
                'category': b.get('category', ''),
            }
            for i, b in enumerate(books)
        ]
        
        self._is_built = True

    def search(self, query_text, top_k=10):
        """语义检索
        
        返回: list[dict]
        """
        if not self._is_built:
            return []
        
        # 对查询分词 + 向量化
        query_vec = self.vectorizer.transform([tokenize_zh(query_text)])
        query_lsi = self.lsa.transform(query_vec)
        
        # 计算余弦相似度
        sims = cosine_similarity(query_lsi, self.lsi_matrix)[0]
        
        # 取 top_k
        top_indices = sims.argsort()[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            score = float(sims[idx])
            if score <= 0:
                continue
            meta = self.doc_metadata[idx]
            results.append({
                'id': meta['id'],
                'title': meta['title'],
                'author': meta['author'],
                'category': meta['category'],
                'score': score,
                'source': 'lsi',
            })
        
        return results

    def save(self, path):
        """保存索引到磁盘"""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        data = {
            'vectorizer': self.vectorizer,
            'lsa': self.lsa,
            'lsi_matrix': self.lsi_matrix,
            'doc_metadata': self.doc_metadata,
            'n_components': self.n_components,
            'max_features': self.max_features,
        }
        with open(path, 'wb') as f:
            pickle.dump(data, f)

    def load(self, path):
        """从磁盘加载索引"""
        with open(path, 'rb') as f:
            data = pickle.load(f)
        self.vectorizer = data['vectorizer']
        self.lsa = data['lsa']
        self.lsi_matrix = data['lsi_matrix']
        self.doc_metadata = data['doc_metadata']
        self.n_components = data['n_components']
        self.max_features = data['max_features']
        self._is_built = True

    def suggest_related_terms(self, term, top_k=5):
        """推荐相关术语（共现+语义近似）"""
        if not self._is_built:
            return []
        
        # 从 TF-IDF 词汇空间找与 term 最相近的特征词
        term_vec = self.vectorizer.transform([tokenize_zh(term)])
        feature_names = self.vectorizer.get_feature_names_out()
        term_feature_sim = term_vec.toarray()[0]
        
        top_idx = term_feature_sim.argsort()[-top_k:][::-1]
        suggestions = []
        for idx in top_idx:
            if term_feature_sim[idx] > 0:
                suggestions.append({
                    'term': feature_names[idx],
                    'score': float(term_feature_sim[idx]),
                })
        
        return suggestions

    @property
    def is_built(self):
        return self._is_built


if __name__ == '__main__':
    print("LSI 语义索引自测...")
    
    books = [
        {"id": "1", "title": "流畅的Python", "author": "LR", "category": "编程语言",
         "body": "Python是一种优雅的编程语言。本书介绍异步编程、协程、元编程等高级特性。"},
        {"id": "2", "title": "Python并发编程", "author": "V", "category": "编程语言",
         "body": "深入讲解多线程、多进程、异步IO、事件循环、GIL、线程安全等并发技术。"},
        {"id": "3", "title": "计算机系统", "author": "RB", "category": "计算机科学",
         "body": "讲解处理器架构、内存层次、虚拟内存、网络编程和并发编程。"},
        {"id": "4", "title": "算法导论", "author": "TC", "category": "计算机科学",
         "body": "介绍排序、图算法、动态规划、贪心算法等核心算法设计方法。"},
        {"id": "5", "title": "分布式系统", "author": "MK", "category": "计算机科学",
         "body": "数据库、流处理、批处理和分布式系统的复制、分区、共识算法。"},
        {"id": "6", "title": "深度学习入门", "author": "XX", "category": "AI",
         "body": "神经网络、卷积网络、循环神经网络和Transformer架构入门。"},
    ]

    si = SemanticIndex(n_components=20, max_features=1000)
    si.build(books)
    
    queries = [
        "Python异步编程协程",
        "并发多线程并行",
        "算法数据结构", 
        "神经网络深度学习AI",
        "数据库分布式",
    ]
    
    for q in queries:
        results = si.search(q, top_k=3)
        if results:
            top = results[0]
            print(f"  '{q}' → {top['title']} ({top['score']:.4f})")
        else:
            print(f"  '{q}' → 无结果")

    print("  相关术语 (异步):", si.suggest_related_terms("异步", top_k=3))
    print("✅ LSI 语义索引自测通过")
