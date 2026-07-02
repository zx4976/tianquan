# TrustForge 整体架构

## 总览

TrustForge 是一个"零信任审计层"，不替代任何开发或读书工具，而是悬在所有 AI 输出之上的验证层。

```
用户需求 / 书本文本
        │
        ▼
┌─────────────────────────────────────────────┐
│          AI 输出（我——天权·隐光）              │
│  自然语言理解 / DSL 声明 / 代码 / 断言         │
└──────────────────┬──────────────────────────┘
                   │ 未经信任
                   ▼
┌─────────────────────────────────────────────┐
│           TrustForge 审计层                   │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ 需求锚定  │  │ 逻辑验证  │  │ 沙盒执行  │   │
│  │ (parse)  │→│ (verify) │→│ (run)    │   │
│  └──────────┘  └──────────┘  └──────────┘   │
│                                              │
│  ┌──────────────────────────────────────┐    │
│  │       读书理解模块                    │    │
│  │  store → verify → audit → derive    │    │
│  └──────────────────────────────────────┘    │
│                                              │
│  验证通过的输出 → 可以信任                    │
│  验证失败的输出 → 退回，证据在哪？             │
└─────────────────────────────────────────────┘
```

## 命令架构

```
trustforge
├── init                    # 初始化项目模板
│
├── parse <req.md>          # 阶段一：需求锚定
│   └── 输出 req_schema.json（原文坐标）
│
├── verify <dsl.json>       # 阶段二：逻辑验证
│   ├── 检查 req_id 映射（防脑补）
│   ├── 检查状态机闭环（防偷懒）
│   └── 检查异常覆盖（防吞异常）
│
├── compile <dsl.json>      # 阶段三：确定性编译
│   ├── models.py（Pydantic 数据模型）
│   ├── state_machine.py（状态机，if/else 由编译器生成）
│   ├── api.py（FastAPI 路由）
│   ├── validators.py（校验器）
│   └── tests/（自动生成测试）
│
├── run <dsl.json>          # 沙盒执行
│   └── 真实跑 pytest，代码可编译可运行才算通过
│
└── understand              # 读书理解模块
    ├── store               # 存入理解（三要素 + Layer 2 证据验证）
    │   ├── --motivation    由来/动机
    │   ├── --content       核心断言
    │   └── --application   应用
    ├── verify              # 闭卷推导验证（确认真正理解）
    ├── status              # 查看进度
    ├── mark                # 标记章节
    ├── audit               # 闭卷审计（Layer 3）
    ├── derive              # 符号推导（不依赖大模型）
    ├── info                # 书籍信息
    └── list                # 未读书籍
```

## 目录结构

```
trustforge/
├── trustforge/
│   ├── __init__.py
│   ├── cli.py              # CLI 入口，路由所有命令
│   ├── models.py           # DSL 数据模型（Pydantic）
│   ├── understand.py       # 读书理解模块实现 + 运动学推导
│   ├── determinant_engine.py # 行列式推导引擎（纯模板+itertools）
│   ├── validators/
│   │   ├── __init__.py
│   │   └── dsl_validator.py  # DSL 验证引擎
│   └── generators/
│       ├── __init__.py
│       └── python_gen.py     # Python 代码生成器
├── examples/
│   └── user_auth/           # 完整示例：用户认证状态机
│       ├── requirements.md
│       ├── requirements.req_schema.json
│       └── logic.dsl.json
├── ARCHITECTURE.md
├── README.md
└── pyproject.toml
```

## 完整流程

### 开发场景：用户登录

```
1. 用户写 requirements.md（自然语言需求）
2. trustforge parse → req_schema.json（6个需求切片）
3. 大模型根据 req_schema 编写 logic.dsl.json
   - 只能声明：实体/状态/迁移/API/校验规则
   - 不能写任何 if/else/for/while
4. trustforge verify → 验证通过
   - 所有节点映射到 req_id ✅
   - 状态机无孤立节点 ✅
   - 异常分支已覆盖 ✅
5. trustforge compile → 生成代码+测试
6. trustforge run → 沙盒测试全部通过 ✅
```

### 读书场景

```
1. trustforge understand info <book_id>
2. trustforge understand store --dim "..." --motivation "..." --content "..." --application "..." --evidence "..."
   → Layer 2 验证 evidence 是否在正文中
   → 三要素不完整或 evidence 不在正文 → 拒绝
3. trustforge understand verify --dim "..." → 闭卷推导验证
4. trustforge understand status → 查看进度
5. trustforge understand audit → 闭卷审计
6. trustforge understand derive <book_id> "问题" → 基于已存知识推导
```

## 理解模块三要素

```
一条完整理解 = [由来] 为什么这个知识存在？
              + [核心] 它断言了什么？
              + [应用] 它能推导出什么？
```

三者缺一不可。`trustforge understand store` 拒绝不完整的存入。

## 推导引擎架构

```
理解模块中的 knowledge 表
        │
        ▼
引擎匹配（关键词 + 语义组 + 依赖链扩展）
        │
        ▼
引擎执行（模板推导 / itertools / SymPy 符号计算）
        │
        ▼
输出推导步骤（标注"未调用大模型参数"）
```

| 引擎 | 位置 | 原理 |
|------|------|------|
| 运动学 | understand.py | 数值公式计算 |
| 行列式 | determinant_engine.py | 模板 + itertools.permutations |
| 线性代数 | algebra_engine.py | 模板驱动逻辑推导 |

引擎不接收任何大模型生成的参数——所有计算基于 Python 标准库。

## 数据隔离

```
开发版 understanding.db → ~/projects/knowledge-engine/data/understanding.db
AI Agent 个人数据       → ~/.hermes/（不包含 understanding.db）
```

理解模块的开发测试不会影响 AI Agent 的个人数据。
