# 隐光知识引擎 (YinGuang Knowledge Engine)

> 北斗第九星 — 隐光内弼。隐而不显，在内辅弼。

## 产品说明

隐光知识引擎是一个**纯算法、零 LLM 依赖**的书籍知识管理系统。它不依赖任何大语言模型或外部 API，仅通过经典信息检索算法（TF-IDF、SVD、BM25）和图数据库（Kùzu）实现对书籍内容的精确检索、语义联想和知识图谱关联。

### 核心特性

- **零 LLM 依赖** — 全文检索、语义索引、知识图谱全部使用纯算法实现
- **精确可追溯** — 每一条检索结果都指向原文，不产生幻觉
- **多路并行检索** — 同时运行关键词搜索、语义联想、图遍历三种检索策略
- **RRF 融合排序** — 使用 Reciprocal Rank Fusion 算法融合多路结果，提升检索精度
- **自动分类** — 根据书名、目录、正文自动对书籍进行学科分类
- **中文原生支持** — 使用 jieba 分词，中文检索无需额外配置
- **持久化存储** — 索引数据写入磁盘，关闭后重新打开数据仍在
- **一键备份恢复** — 内置备份/恢复脚本，支持 SHA256 校验

### 架构

```
用户查询
    │
    ├──► Tantivy (BM25 关键词精确检索)
    │
    ├──► LSI (TF-IDF + SVD 语义联想)
    │
    ├──► Kùzu (图数据库 — 概念关系遍历)
    │
    └──► RRF 融合 → 排序结果
```

## 应用场景

### 个人知识管理
将个人藏书导入知识引擎，通过关键词或自然语言查询快速定位相关内容。支持自动生成读书笔记到 Obsidian。

### AI Agent 外接知识库
AI Agent 可通过 REST API 或 Python SDK 调用知识引擎，在对话中检索精确的书籍知识，避免大模型幻觉。

### 学术研究
管理论文、技术文档、教材等专业资料。语义联想功能可在不同文献之间发现潜在的概念关联。

### 企业文档管理
将内部技术文档、规范、手册导入引擎，提供统一的知识检索入口。

## 支持的 AI Agent

隐光知识引擎提供 REST API 接口和 Python SDK，可以接入任何支持 HTTP 请求的 AI Agent：

| AI Agent | 接入方式 | 说明 |
|----------|---------|------|
| Hermes Agent | Python SDK (`ke_integration.py`) | 原生支持，可直接 import 调用 |
| Claude Code / Cursor | REST API | 通过 `curl` 或 HTTP 客户端调用 |
| ChatGPT / GPTs | REST API | 通过 Custom GPT 的 Action 配置接入 |
| 任意 AI Agent | REST API | 标准 JSON over HTTP |
| 传统应用 | REST API | 可直接作为搜索后端使用 |

## 技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| 全文检索 | Tantivy 0.26+ | BM25 关键词精确搜索 |
| 语义索引 | scikit-learn TfidfVectorizer + TruncatedSVD | TF-IDF 向量化 + LSI 降维 |
| 知识图谱 | Kùzu 0.11+ | 概念节点关系存储与图遍历 |
| 中文分词 | jieba 0.42+ | 中文文本分词 |
| API 服务 | Python http.server (内置) | 零依赖的 REST API |
| 数据持久化 | 磁盘文件 | Tantivy 索引 + Kùzu 数据库 + pickle 模型 |

## 安装

### 系统要求

- Python 3.10+
- 操作系统：Linux / macOS / Windows (WSL)
- 内存：建议 2GB+（取决于数据量）
- 磁盘：100 万本书约需 70MB（Tantivy 索引）+ 400MB（Kùzu 图谱）

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/你的用户名/knowledge-engine.git
cd knowledge-engine

# 2. 创建虚拟环境
uv venv --python 3.11 .venv

# 3. 安装依赖
uv pip install tantivy kuzu scikit-learn jieba pypdf

# 4. 初始化数据目录
python3 -c "from src.config import ensure_dirs; ensure_dirs()"

# 5. 启动 API 服务
python3 api_server.py
```

### 启动 API 服务

```bash
# 默认端口 8765
python3 api_server.py

# 自定义端口
KE_API_PORT=8888 python3 api_server.py
```

### Docker（规划中）

```dockerfile
# Dockerfile 正在准备中
```

## 使用指南

### 命令行导入书籍

```bash
# 从文本文件导入
python3 main.py import --file /path/to/book.txt --author "作者名" --tags "标签"

# 从 PDF 导入
python3 main.py import --file /path/to/book.pdf --author "作者名"

# 导入时同步生成 Obsidian 笔记
python3 main.py import --file book.txt --vault /path/to/obsidian-vault/
```

### REST API 调用

```bash
# 健康检查
curl http://127.0.0.1:8765/api/health

# 搜索
curl "http://127.0.0.1:8765/api/search?q=Python异步编程&limit=5"

# 导入书籍
curl -X POST http://127.0.0.1:8765/api/books \
  -H "Content-Type: application/json" \
  -d '{
    "title": "书名",
    "author": "作者",
    "body": "书籍正文内容...",
    "tags": "标签1 标签2"
  }'

# 自动分类测试
curl "http://127.0.0.1:8765/api/classify?title=算法导论&body=排序图算法"

# 数据统计
curl http://127.0.0.1:8765/api/stats
```

### Python SDK

```python
from ke_integration import search, import_book, stats, classify

# 搜索
results = search("Python 异步编程", limit=5)
for book in results['results']:
    print(f"[{book['score']:.2f}] {book['title']}")

# 导入书籍
import_book({
    "title": "流畅的Python",
    "author": "Luciano Ramalho",
    "body": "书籍正文...",
})

# 查看统计
print(stats())
```

## 备份与恢复

### 自动备份（推荐）

内置 cron 备份任务，每天 03:00 自动执行：

```bash
# 查看备份任务
hermes cron list

# 手动触发备份
bash scripts/backup.sh
```

备份内容包括：
- 全部源码 (`src/`, `main.py`, `api_server.py`)
- 索引数据 (`data/`)
- 配置和脚本 (`scripts/`)
- SHA256 校验和

备份文件保存在 `./工作文档/知识引擎备份/`，保留最近 7 天。

### 手动备份

```bash
# 自定义备份目录
BACKUP_DIR=/path/to/backup bash scripts/backup.sh
```

### 灾难恢复

```bash
# 恢复到最新备份
bash scripts/restore.sh

# 恢复到指定备份
bash scripts/restore.sh /path/to/backup/knowledge_engine_20260627.tar.gz
```

恢复流程：
1. ✅ SHA256 校验备份文件完整性
2. ✅ 自动备份当前状态到 `.bak.XXX/`
3. ✅ 解压恢复
4. ✅ 验证核心文件存在

### 恢复后重建环境

```bash
cd /path/to/knowledge-engine
uv venv --python 3.11 .venv
uv pip install tantivy kuzu scikit-learn jieba pypdf
```

## 数据安全设计

本项目的设计吸取了前代 AI 系统（天权 V1-V6）的数据丢失教训：

| 教训 | 当前设计 |
|------|---------|
| 数据与代码混放导致误删 | 数据独立存放于 `data/`，与源码分离 |
| 无备份导致不可恢复 | 内置备份/恢复脚本 + SHA256 校验 |
| 备份后无法验证 | 提供 `restore.sh` 可手动验证恢复流程 |
| 依赖框架内部状态 | 纯算法实现，核心逻辑不依赖任何 AI 框架 |

## 项目结构

```
knowledge-engine/
├── main.py                 # 命令行入口
├── api_server.py           # REST API 服务
├── src/
│   ├── __init__.py
│   ├── rrf.py              # RRF 融合（纯数学）
│   ├── tantivy_index.py    # Tantivy 全文索引
│   ├── kuzu_graph.py       # Kùzu 知识图谱
│   ├── lsi_semantic.py     # LSI 语义索引
│   ├── book_pipeline.py    # 书籍导入管道
│   ├── config.py           # 配置管理
│   └── context_manager.py  # 上下文管理
├── scripts/
│   ├── backup.sh           # 备份脚本
│   └── restore.sh          # 恢复脚本
├── data/                   # 持久化数据（自动生成）
└── .venv/                  # Python 虚拟环境
```

## 性能指标（实测）

| 指标 | 数据 |
|------|------|
| 建索引速度 | 100,000 篇文档 ~2 秒 |
| 单次检索 | < 5ms（10 万篇规模） |
| 索引大小 | ~72 字节/文档 |
| LSI 建索引 | 20,000 篇 ~1.2 秒 |
| 知识图谱遍历 | 10 层 BFS < 10ms |

## 许可证

[MIT License](LICENSE)
