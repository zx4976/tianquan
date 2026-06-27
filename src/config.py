#!/usr/bin/env python3
"""
知识引擎 — 配置与持久化路径管理
"""
import os

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 数据根目录（持久化存储）
DATA_ROOT = os.path.join(PROJECT_ROOT, "data")

# 各索引数据路径
TANTIVY_INDEX_DIR = os.path.join(DATA_ROOT, "tantivy_index")
KUZU_DB_PATH = os.path.join(DATA_ROOT, "kuzu_graph", "knowledge.db")
LSI_MODEL_PATH = os.path.join(DATA_ROOT, "lsi", "lsi_model.pkl")
LSI_VECTORIZER_PATH = os.path.join(DATA_ROOT, "lsi", "vectorizer.pkl")
METADATA_PATH = os.path.join(DATA_ROOT, "metadata", "catalog.json")

# 默认参数
LSI_N_COMPONENTS = 100
LSI_MAX_FEATURES = 5000
TANTIVY_HEAP_SIZE = 200_000_000
TANTIVY_NUM_THREADS = 4

# 工作区（临时文件）
WORKSPACE_DIR = "/tmp/ke_workspace"


def ensure_dirs():
    """确保所有数据目录存在（幂等）"""
    dirs = [
        DATA_ROOT,
        TANTIVY_INDEX_DIR,
        os.path.dirname(KUZU_DB_PATH),
        os.path.dirname(LSI_MODEL_PATH),
        os.path.dirname(METADATA_PATH),
        WORKSPACE_DIR,
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def get_stats():
    """获取数据目录统计"""
    ensure_dirs()
    
    total_size = 0
    total_files = 0
    for dirpath, dirnames, filenames in os.walk(DATA_ROOT):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total_size += os.path.getsize(fp)
                total_files += 1
            except OSError:
                pass
    
    # 书籍数量（从 Tantivy 索引读取）
    book_count = 0
    tantivy_meta = os.path.join(TANTIVY_INDEX_DIR, "meta.json")
    if os.path.exists(tantivy_meta):
        try:
            import json
            with open(tantivy_meta) as f:
                meta = json.load(f)
                book_count = meta.get("num_docs", 0)
        except Exception:
            pass
    
    return {
        "data_root": DATA_ROOT,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / 1024 / 1024, 2),
        "total_files": total_files,
        "book_count": book_count,
    }


if __name__ == '__main__':
    ensure_dirs()
    print("数据目录已创建:")
    for d in [DATA_ROOT, TANTIVY_INDEX_DIR, os.path.dirname(KUZU_DB_PATH),
              os.path.dirname(LSI_MODEL_PATH), WORKSPACE_DIR]:
        exists = "✅" if os.path.exists(d) else "❌"
        print(f"  {exists} {d}")
    print(f"\n统计: {get_stats()}")
