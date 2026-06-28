# 隐光知识引擎 (YinGuang Knowledge Engine)

> 北斗第九星 — 隐光内弼。隐而不显，在内辅弼。

## 产品说明

隐光知识引擎是一个**纯算法、零 LLM 依赖**的书籍知识管理系统。它不依赖任何大语言模型或外部 API，仅通过经典信息检索算法（TF-IDF、SVD、BM25）和图数据库（Kùzu）实现对书籍内容的精确检索、语义联想和知识图谱关联。

### 核心特性

- **零 LLM 依赖** — 全文检索、语义索引、知识图谱全部使用纯算法实现
- **精确可追溯** — 每一条检索结果都指向原文，不产生幻觉
- **四路并行检索** — 同时运行关键词搜索、语义联想、图遍历、向量相似度四种检索策略
- **RRF 融合排序** — 使用 Reciprocal Rank Fusion 算法融合多路结果，提升检索精度
- **自动分类** — 根据书名、目录、正文自动对书籍进行学科分类
- **多语言支持** — 内置六种语言分词引擎，自动检测并选择对应分词器
- **语言感知搜索** — 搜索结果优先展示与查询语言匹配的书籍
- **学术文献分析** — 支持从 arXiv 导入论文，自动解析元数据、参考文献、建立引用图谱
- **个人记忆系统** — 基于 SQLite 的持久化记忆，AI Agent 可存储和检索关键事实
- **持久化存储** — 索引数据写入磁盘，关闭后重新打开数据仍在
- **批量导入优化** — 预分词 + 单writer批量写入，导入速度提升 4.6 倍
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
    ├──► FAISS (TF-IDF 向量相似搜索)
    │
    └──► RRF 融合 → 语言重排序 → 最终结果
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
| 向量搜索 | FAISS + char_wb TF-IDF | 字符级 n-gram 向量相似搜索 |
| 中文分词 | jieba 0.42+ | 中文文本分词 |
| 日文分词 | fugashi 1.5+ (MeCab) | 日文文本分词 |
| 韩文分词 | soynlp 0.0+ | 韩文文本分词 |
| 希伯来文分词 | hebrew-tokenizer 2.3+ | 希伯来文文本分词 |
| 个人记忆 | SQLite + 关键词检索 | AI Agent 持久化记忆存储 |
| API 服务 | Python http.server (内置) | 零依赖的 REST API |
| 数据持久化 | 磁盘文件 | Tantivy 索引 + Kùzu 数据库 + FAISS 索引 |

## 多语言支持

隐光知识引擎内置五种语言的分词引擎，自动检测文本语言并选择对应分词器：

| 语言 | 分词引擎 | 检测方式 | 示例 |
|------|---------|---------|------|
| 中文（简/繁） | jieba | Unicode 汉字检测 | `Python 是 一种 优雅 的 编程语言` |
| 日文 | fugashi (MeCab) | 假名字符检测 | `Python は エレガント な プログラミング 言語` |
| 韩文 | soynlp 规则 | 韩文字符检测 | `Python 우아한 프로그래밍 언어` |
| 希伯来文 | hebrew-tokenizer | 希伯来字符检测 | `Python היא שפת תכנות אלגנטית` |
| 拉丁语系（英/法/德/西等） | 空格分词 | 默认回退 | `Python is an elegant language` |

搜索时，引擎会自动检测查询语言，在结果中对同语言书籍进行排序加权，确保跨语言搜索时优先展示相关性最高的结果。

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
│   ├── vector_index.py     # FAISS 向量相似搜索                                 
│   ├── tokenizer.py        # 多语言分词器（中/日/韩/希伯来/拉丁）              
│   ├── book_pipeline.py    # 书籍导入管道                                      
│   ├── paper_pipeline.py   # 学术文献导入管道                                  
│   ├── arxiv_helper.py     # arXiv API 工具 + 引用解析                          
│   ├── memory.py           # AI Agent 个人记忆系统                              
│   ├── context_manager.py  # 上下文管理                                        
│   └── config.py           # 配置管理                                          
├── scripts/                                                                     
│   ├── import_shelf.py     # 批量导入脚本（预分词 + 单writer）                  
│   ├── backup.sh           # 备份脚本                                          
│   └── restore.sh          # 恢复脚本                                          
├── data/                   # 持久化数据（自动生成）                            
└── .venv/                  # Python 虚拟环境（自动生成）                        
```

## 学术文献分析

隐光知识引擎支持从 arXiv 直接导入学术论文，自动提取元数据、全文、参考文献并建立引用图谱。

### 导入论文

```bash
# 从 arXiv ID 导入
python3 main.py paper 2606.26162

# 导入时重建 LSI 语义索引
python3 main.py paper 2301.00001 --rebuild-lsi
```

### 自动完成的分析流程

1. **arXiv API 获取元数据** — 标题、作者、年份、学科分类
2. **PDF 下载与全文提取** — 自动下载并提取正文文本
3. **学科自动映射** — arXiv 分类（如 cs.HC）映射到知识引擎学科体系
4. **关键词提取** — 从标题+摘要中提取核心概念
5. **参考文献解析** — 自动识别 REFERENCES 章节，提取每条引用的作者、年份、DOI
6. **引用图谱入库** — 每条引用作为 Kùzu 概念节点，与论文建立 COVERS 关系
7. **全文索引** — 论文全文进入 Tantivy 索引，支持关键词搜索

### 引用图谱

多篇论文导入后，Kùzu 知识图谱中自然形成引用网络：

```
论文A ──COVERS──→ 引用[1]
论文B ──COVERS──→ 引用[1]  (同一篇被多篇引用)
论文C ──COVERS──→ 引用[2]
```

支持查询 "哪些论文引用了同一篇文献"、"某篇论文引用了哪些工作"。

### 依赖安装

```bash
# 论文分析额外依赖
uv pip install pypdf
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
