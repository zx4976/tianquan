#!/usr/bin/env python3
"""
上下文管理器 — 解决 LLM 上下文窗口有限的问题
策略：分层加载 + 子代理分治 + 文件工作区
"""
import os
import json
import time
import sys
import shutil

# 支持作为脚本直接运行和作为模块导入
if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.book_pipeline import BookPipeline
    from src import rrf
else:
    from .book_pipeline import BookPipeline
    from . import rrf


class ContextManager:
    """
    上下文管理器 — 确保知识检索结果不会撑爆 LLM 上下文窗口。
    
    三层策略：
      策略1: 分层加载 — 先返回摘要/标题，用户选后再加载详情
      策略2: 子代理分治 — 每个子代理只处理一本书，返回小摘要
      策略3: 文件工作区 — 超大的中间结果写到文件，按需读取
    """

    def __init__(self, workspace_dir=None, persistent=False):
        self.workspace_dir = workspace_dir or "/tmp/ke_workspace"
        self.persistent = persistent
        os.makedirs(self.workspace_dir, exist_ok=True)
        self._session_files = []

    # ============================================================
    # 策略1: 分层加载
    # ============================================================
    def search_summary(self, query, limit=10):
        """
        第一层搜索：只返回标题+来源+得分，不加载正文。
        适合直接显示给用户选择。
        """
        with BookPipeline(persistent=self.persistent) as pipe:
            results = pipe.search(query, limit=limit)
        
        summary = []
        for r in results:
            summary.append({
                'id': r.get('id', ''),
                'title': r.get('title', ''),
                'author': r.get('author', ''),
                'category': r.get('category', ''),
                'source': r.get('source', 'rrf'),
                'score': round(r.get('rrf_score', r.get('score', 0)), 4),
                # 不返回 body，只返回元数据
            })
        
        return summary

    def load_book_detail(self, book_id, max_chars=3000):
        """
        第二层：按需加载某本书的详情。
        max_chars 限制返回的文本长度，防止撑爆上下文。
        """
        # 从 Tantivy 索引中读取
        from .tantivy_index import BookIndex
        
        idx = BookIndex()
        # 这里需要一个持久化的索引路径
        # 当前实现需要改进以支持持久化索引
        return {
            'book_id': book_id,
            'detail': "(持久化索引尚未实现，需要先确定存储路径)",
        }

    # ============================================================
    # 策略2: 子代理分治
    # ============================================================
    def prepare_delegation_tasks(self, query, max_books=5):
        """
        为子代理分治准备任务清单。
        每个子代理只处理一本书，返回小摘要。
        
        返回: list[dict], 每项是给一个子代理的任务描述
        """
        summary = self.search_summary(query, limit=max_books)
        
        tasks = []
        for i, book in enumerate(summary):
            task = {
                'task_id': f"book_{i}",
                'goal': f"阅读《{book['title']}》中与以下问题相关的内容，提取关键要点（300字以内），返回结构化摘要",
                'context': f"""
问题: {query}
书籍: {book['title']}
作者: {book['author']}
类别: {book['category']}
匹配分数: {book['score']}

请从这本书中提取与问题直接相关的:
1. 核心观点（1-3条）
2. 关键数据/事实（如有）
3. 原文引用（1-2条，带章节）
返回格式: 纯文本，每部分用 --- 分隔，总字数不超过300字
                """.strip(),
            }
            tasks.append(task)
        
        return tasks

    def merge_subagent_results(self, results):
        """
        合并多个子代理的返回摘要。
        results: list[str], 每个子代理返回的文本摘要
        """
        merged = []
        for i, text in enumerate(results):
            merged.append(f"--- 书{i+1} ---\n{text}")
        return "\n\n".join(merged)

    # ============================================================
    # 策略3: 文件工作区
    # ============================================================
    def save_to_workspace(self, data, filename=None):
        """
        将大数据写到文件，只在上下文中保留文件路径。
        返回文件路径，后续可以用 read_file 按需读取。
        """
        if filename is None:
            filename = f"ke_data_{int(time.time())}.json"
        
        filepath = os.path.join(self.workspace_dir, filename)
        
        if isinstance(data, str):
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(data)
        else:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        
        self._session_files.append(filepath)
        return filepath

    def read_from_workspace(self, filepath, max_chars=5000):
        """从工作区读取文件的一部分"""
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(max_chars)
        
        return content

    def cleanup_session(self):
        """清理本次会话的工作区文件"""
        for fp in self._session_files:
            if os.path.exists(fp):
                os.remove(fp)
        self._session_files = []

    # ============================================================
    # 智能调度：根据查询复杂度自动选择策略
    # ============================================================
    def smart_query(self, query, max_summary_chars=2000, user_context_remaining=30000):
        """
        智能查询 —— 根据上下文剩余空间自动选择策略。
        
        user_context_remaining: 上下文中还剩多少字符可用（由 agent 评估传入）
        
        返回策略说明 + 结果路径
        """
        # 先搜摘要（轻量）
        summary = self.search_summary(query, limit=10)
        
        # 估算摘要大小
        summary_text = json.dumps(summary, ensure_ascii=False)
        
        if len(summary_text) > user_context_remaining * 0.3:
            # 策略3: 摘要都太大，写到文件
            path = self.save_to_workspace(summary, "search_summary.json")
            return {
                'strategy': 'file_workspace',
                'message': f'搜索完成。结果已写入工作区文件，路径: {path}',
                'filepath': path,
                'summary': summary[:3],  # 只给前3条预览
                'total_results': len(summary),
            }
        
        elif len(summary) >= 5 and user_context_remaining < 10000:
            # 策略2: 书太多 + 上下文紧，建议分治
            tasks = self.prepare_delegation_tasks(query, max_books=min(5, len(summary)))
            return {
                'strategy': 'subagent_delegation',
                'message': f'找到 {len(summary)} 本相关书籍，建议派发 {len(tasks)} 个子代理并行处理',
                'tasks': tasks,
                'summary': summary,
                'total_results': len(summary),
            }
        else:
            # 策略1: 直接返回摘要，上下文够用
            return {
                'strategy': 'direct_summary',
                'message': f'找到 {len(summary)} 本相关书籍',
                'summary': summary,
                'total_results': len(summary),
            }
    
    def close(self):
        self.cleanup_session()


# 快捷函数：供 agent 直接调用
def search_light(query, limit=10):
    """轻量搜索，只返回标题+得分。适合直接放回对话。"""
    cm = ContextManager()
    try:
        return cm.search_summary(query, limit=limit)
    finally:
        cm.close()


def prepare_subagent_tasks(query, max_books=5):
    """准备子代理任务。适合跨书融合场景。"""
    cm = ContextManager()
    try:
        return cm.prepare_delegation_tasks(query, max_books=max_books)
    finally:
        cm.close()


if __name__ == '__main__':
    print("上下文管理器自测...")
    
    cm = ContextManager()
    
    # 测试1: 轻量搜索
    print("\n1. 轻量搜索（策略1）:")
    results = cm.search_summary("Python 并发", limit=5)
    print(f"  找到 {len(results)} 条结果")
    for r in results:
        print(f"    [{r['score']:.4f}] {r['title']} ({r['source']})")
    
    # 测试2: 子代理任务（策略2）
    print("\n2. 子代理任务（策略2）:")
    tasks = cm.prepare_delegation_tasks("Python 并发", max_books=3)
    print(f"  生成 {len(tasks)} 个子任务:")
    for t in tasks:
        print(f"    [{t['task_id']}] {t['goal'][:60]}...")
    
    # 测试3: 文件工作区（策略3）
    print("\n3. 文件工作区（策略3）:")
    path = cm.save_to_workspace({"test": "data", "items": list(range(100))})
    print(f"  写入: {path}")
    content = cm.read_from_workspace(path, max_chars=100)
    print(f"  读取: {content[:80]}...")
    
    # 测试4: 智能调度
    print("\n4. 智能调度:")
    result = cm.smart_query("Python", user_context_remaining=50000)
    print(f"  策略: {result['strategy']}")
    print(f"  结果数: {result['total_results']}")
    
    cm.close()
    print("\n✅ 上下文管理器自测通过")
