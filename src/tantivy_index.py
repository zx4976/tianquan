#!/usr/bin/env python3
"""
Tantivy 全文索引层 — 书籍精确检索（支持持久化）
"""
import tantivy
import os
import json
import tempfile
import shutil

from .tokenizer import tokenize, tokenize_with_lang, detect_lang


def tokenize_text(text):
    return tokenize(text)


class BookIndex:
    """书籍全文索引 — 支持内存模式（测试）和持久化模式"""

    def __init__(self, index_path=None):
        self.index_path = index_path
        self.schema = self._build_schema()
        self.index = None
        self.searcher = None
        self._temp_dir = None
        self._num_docs = 0

        if index_path:
            self._open_or_create(index_path)

    def _build_schema(self):
        sb = tantivy.SchemaBuilder()
        sb.add_text_field("book_id", stored=True)
        sb.add_text_field("title", stored=True)
        sb.add_text_field("author", stored=True)
        sb.add_text_field("category", stored=True)
        sb.add_text_field("body", stored=True)
        sb.add_text_field("tags", stored=True)
        sb.add_text_field("lang", stored=True)
        return sb.build()

    def _open_or_create(self, path):
        if isinstance(path, str):
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
        self.index = tantivy.Index(self.schema, path=str(path))
        self.index.reload()
        self.searcher = self.index.searcher()
        self._load_meta()

    def create_in_memory(self):
        self._temp_dir = tempfile.mkdtemp(prefix="book_index_")
        self.index = tantivy.Index(self.schema, path=self._temp_dir)
        self.searcher = self.index.searcher()
        return self

    def _meta_path(self):
        if self.index_path:
            # 存在 config 的数据目录下，不在 Tantivy 索引目录内
            return os.path.join(
                os.path.dirname(os.path.dirname(str(self.index_path))),
                "metadata", "tantivy_meta.json"
            )
        return None

    def _save_meta(self):
        meta_path = self._meta_path()
        if meta_path:
            os.makedirs(os.path.dirname(meta_path), exist_ok=True)
            with open(meta_path, 'w') as f:
                json.dump({"num_docs": self._num_docs}, f)

    def _load_meta(self):
        meta_path = self._meta_path()
        if meta_path and os.path.exists(meta_path):
            try:
                with open(meta_path) as f:
                    self._num_docs = json.load(f).get("num_docs", 0)
            except Exception:
                self._num_docs = 0
    def add_book(self, book_id, title, author, category, body, tags="", lang="", tokenized=False):
        if not self.index:
            raise RuntimeError("索引未初始化")
        if not lang:
            from .tokenizer import detect_lang
            lang = detect_lang(f"{title} {author} {body[:200]}")
        
        writer = self.index.writer(heap_size=100_000_000, num_threads=4)
        doc = tantivy.Document()
        doc.add_text("book_id", str(book_id))
        doc.add_text("title", title)
        doc.add_text("author", author)
        doc.add_text("category", category)
        if tokenized:
            doc.add_text("body", body)
            doc.add_text("tags", tags)
        else:
            doc.add_text("body", tokenize_text(body))
            doc.add_text("tags", tokenize_text(tags))
        doc.add_text("lang", lang)
        writer.add_document(doc)
        writer.commit()
        self._num_docs += 1
        self._save_meta()
        self.reload()

    def add_books_batch(self, books, tokenized=False):
        if not self.index:
            raise RuntimeError("索引未初始化")
        writer = self.index.writer(heap_size=100_000_000, num_threads=4)
        for book in books:
            doc = tantivy.Document()
            body = str(book.get("body", ""))
            tags = str(book.get("tags", ""))
            doc.add_text("book_id", str(book.get("book_id", "")))
            doc.add_text("title", str(book.get("title", "")))
            doc.add_text("author", str(book.get("author", "")))
            doc.add_text("category", str(book.get("category", "")))
            if tokenized:
                doc.add_text("body", body)
                doc.add_text("tags", tags)
            else:
                doc.add_text("body", tokenize_text(body))
                doc.add_text("tags", tokenize_text(tags))
            doc.add_text("lang", str(book.get("lang", "")))
            writer.add_document(doc)
        writer.commit()
        del writer
        self._num_docs += len(books)
        self._save_meta()

    def reload(self):
        if self.index:
            self.index.reload()
            self.searcher = self.index.searcher()

    @property
    def num_docs(self):
        return self._num_docs

    def search(self, query_str, field="body", limit=10):
        if not self.searcher:
            self.reload()
            if not self.searcher:
                return []
        try:
            q = self.index.parse_query(query_str, default_field_names=[field])
        except Exception:
            return []
        hits = self.searcher.search(q, limit=limit).hits
        results = []
        for score, addr in hits:
            doc = self.searcher.doc(addr)
            results.append({
                'id': doc.get_first("book_id") or "",
                'title': doc.get_first("title") or "",
                'author': doc.get_first("author") or "",
                'category': doc.get_first("category") or "",
                'lang': doc.get_first("lang") or "",
                'score': score,
                'source': 'tantivy',
            })
        return results

    def get_body(self, book_id):
        """按 book_id 获取正文"""
        if not self.searcher:
            self.reload()
        if not self.searcher:
            return ''
        try:
            from tantivy import Occur, Query
            parser = self.index.parse_query(book_id, default_field_names=['book_id'])
            hits = self.searcher.search(parser, limit=1).hits
            if hits:
                doc = self.searcher.doc(hits[0][1])
                return doc.get_first("body") or ''
        except Exception:
            pass
        return ''

    def search_multi_field(self, query_str, fields=None, limit=10):
        fields = fields or ["title", "body"]
        if not self.searcher:
            self.reload()
        try:
            q = self.index.parse_query(query_str, default_field_names=fields)
        except Exception:
            return []
        hits = self.searcher.search(q, limit=limit).hits
        results = []
        for score, addr in hits:
            doc = self.searcher.doc(addr)
            results.append({
                'id': doc.get_first("book_id") or "",
                'title': doc.get_first("title") or "",
                'author': doc.get_first("author") or "",
                'category': doc.get_first("category") or "",
                'lang': doc.get_first("lang") or "",
                'score': score,
                'source': 'tantivy',
            })
        return results

    def close(self):
        if self._temp_dir:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None
        self.index = None
        self.searcher = None

    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()
