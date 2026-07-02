# TrustForge — 零信任隔离铸造机

> 强迫大模型进入"绝对闭卷模式"，只能输出离散化的结构数据，
> 从而在物理上切断它与内部训练数据"脑补"的通道。

## 解决的问题

| 问题 | TrustForge 方案 |
|------|---------------|
| 大模型编造不存在的API/函数 | DSL 只允许声明，不允许写控制流，编译器强制生成完整代码 |
| 大模型假装实现了功能但实际没跑通 | 沙盒执行真实测试，测试结果不可篡改 |
| 大模型声称理解了但实际没有 | 三要素强制约束 + 证据验证 + 闭卷推导验证 |
| 大模型推理依赖训练数据而非已学知识 | 符号推导引擎只基于 knowledge 表中的公理 |
| 开发版数据与生产数据混在一起 | understanding.db 路径在项目目录下，与 AI Agent 隔离 |

## 安装

```bash
# 克隆项目
git clone <repo_url> trustforge
cd trustforge

# 安装依赖（推荐使用 uv）
uv venv
uv pip install -e .
uv pip install pytest fastapi httpx sympy

# 验证安装
trustforge --help
```

## 使用流程

### 软件开发流程

```bash
# 1. 初始化项目
trustforge init my-project
cd my-project

# 2. 编写需求文档 requirements.md

# 3. 解析需求（带原文坐标锚定）
trustforge parse requirements.md

# 4. 大模型根据 req_schema.json 编写 logic.dsl.json
#    大模型只能声明：数据实体、状态迁移、API端点、校验规则
#    不能写任何 if/else/for/while 或计算逻辑

# 5. 验证 DSL 逻辑完整性
trustforge verify logic.dsl.json
#    - 所有节点映射到 req_id（防脑补）
#    - 状态机无孤立节点（防偷懒）
#    - 异常分支已覆盖（防吞异常）

# 6. 编译为代码 + 测试
trustforge compile logic.dsl.json -o ./generated

# 7. 沙盒执行验证
trustforge run logic.dsl.json
```

### 读书理解流程

```bash
# 1. 查看书籍信息
trustforge understand info <book_id>

# 2. 逐章存入理解（强制三要素 + evidence 验证）
trustforge understand store <book_id> \\
  --dim "第1章" \\
  --motivation "这个知识为了解决什么问题而诞生？" \\
  --content "核心定理/定义是什么？" \\
  --application "它能用来推导什么？解决什么问题？" \\
  --evidence "原文引用片段"

# 3. 验证理解（闭卷推导，确认真正理解了）
trustforge understand verify <book_id> --dim "第1章"

# 4. 全书审计
trustforge understand audit <book_id>

# 5. 标记已读
trustforge understand mark-read <book_id>

# 6. 基于已存知识的符号推导（不依赖大模型）
trustforge understand derive <book_id> "自由落体3秒后的速度"
```

## 理解模块三要素

每条理解必须包含：

1. **由来/动机（motivation）** — 这个知识为了解决什么问题而诞生？
2. **核心断言（content）** — 它的核心定理/定义是什么？
3. **应用（application）** — 它能用来推导什么？解决什么问题？

缺少任何一个要素，`trustforge understand store` 拒绝存入。

## 三层防幻觉架构

| 层级 | 名称 | 机制 | 谁执行 |
|------|------|------|--------|
| Layer 1 | 原文阅读 | 从 body_raw 读取原文后提取 atomic knowledge | AI Agent（我） |
| Layer 2 | 证据验证 | 检查 evidence 是否在 body_raw 中 | TrustForge 工具 |
| Layer 3 | 闭卷审计 | 5题问答 + 3条证据随机验证 | AI Agent + TrustForge |

## 推导引擎

所有推导基于 understanding.db 的 knowledge 表，不依赖大模型参数。

| 引擎 | 文件 | 功能 |
|------|------|------|
| 运动学 | understand.py | 自由落体、加速度积分 |
| 行列式 | determinant_engine.py | 交错多重线性映射 → 行列式公式 |
| 线性代数 | algebra_engine.py | 子空间交、线性无关 |

引擎输出标注"未调用大模型参数"，每一步可追溯至已存公理。

## 命令清单

| 命令 | 功能 | 状态 |
|------|------|------|
| `init` | 项目初始化 | ✅ |
| `parse` | 需求解析（原文锚定） | ✅ |
| `verify` | DSL 逻辑验证 | ✅ |
| `compile` | 编译为 Python 代码+测试 | ✅ |
| `run` | 沙盒执行测试 | ✅ |
| `understand store` | 存入理解（三要素+evidence） | ✅ |
| `understand status` | 查看理解进度 | ✅ |
| `understand verify` | 闭卷推导验证 | ✅ |
| `understand audit` | 全书闭卷审计 | ✅ |
| `understand derive` | 基于知识的符号推导 | ✅ |
| `understand info` | 书籍信息 | ✅ |
| `understand list` | 未读书籍列表 | ✅ |

## 完整示例

```bash
# 开发流程示例（用户登录）
cd examples/user_auth
trustforge parse requirements.md
trustforge verify logic.dsl.json
trustforge run logic.dsl.json

# 读书流程示例
trustforge understand info shelf_177
trustforge understand derive shelf_177 "证明子空间的交仍然是子空间"
```

## 原理

```
需求文档 → 阶段一：强锚定提取 → req_schema.json（带原文坐标）
                                       ↓
大模型根据 req_schema 输出 logic.dsl.json → 阶段二：形式化 DSL
                                       ↓
                         阶段三：确定性编译 → 代码 + 测试
                                       ↓
                         沙盒执行 → 通过/失败（二值判定）
```

读书流程对应：

```
书籍原文 → Layer 1: AI 阅读提取 → 三要素理解 + evidence
                                       ↓
                          Layer 2: evidence 验证 → 通过/拒绝
                                       ↓
                          Layer 3: 全书审计 → 标记已读
                                       ↓
                          符号推导引擎（基于已存公理）
```

## 路线图

- [ ] Go 代码生成
- [ ] 更多守卫条件表达式支持
- [ ] DSL 可视化编辑器
- [ ] 更多学科推导引擎（群表示、复分析、解析数论）
