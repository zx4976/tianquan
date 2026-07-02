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
│   ├── state_machine.py（状态机）
│   ├── api.py（FastAPI 路由）
│   ├── validators.py（校验器）
│   └── tests/（自动生成测试）
│
├── run <dsl.json>          # 沙盒执行
│   └── 真实跑 pytest，代码可编译可运行才算通过
│
└── understand              # 读书理解模块
    ├── store               # 存入理解（Layer 2：evidence验证）
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
│   ├── understand.py       # 读书理解模块实现
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
├── README.md
└── pyproject.toml
```

## 两个场景的完整流程

### 开发场景：用户登录

```
1. 用户写 requirements.md（自然语言需求）
2. trustforge parse → req_schema.json（6个需求切片）
3. 我（大模型）根据 req_schema 编写 logic.dsl.json
   - 只能声明：实体/状态/迁移/API/校验规则
   - 不能写任何 if/else/for/while
4. trustforge verify → 检查通过
   - 所有节点映射到 req_id ✅
   - 状态机无孤立节点 ✅
   - 异常分支已覆盖 ✅
5. trustforge compile → 生成代码+测试
   - 16个测试全部生成
6. trustforge run → 16/16通过 ✅
```

### 读书场景：精读《微积分五讲》

```
1. trustforge understand info shelf_223 → 查看书籍信息
2. trustforge understand store --dim "第二讲" --content "..." --evidence "..."
   → Layer 2 验证 evidence 是否在正文中
   → 通过才存入
3. trustforge understand status → 查看已存理解
4. trustforge understand derive shelf_223 "自由落体5秒"
   → 从 knowledge 表调取公式，数值计算
   → 不依赖大模型参数
5. trustforge understand audit → 闭卷审计
   → 抽5条，证据验证3条，≥80%标记已读
```

## 为什么要独立于知识引擎和读书工具

TrustForge 不替你做任何"创造"——它替你做的都是"验证"。

- 知识引擎（`knowledge-engine/`）负责存储和搜索
- 读书工具（`store_understanding.py`）负责方便地存理解
- TrustForge 负责：**你说存了？证据呢？你说读完了？审计通过了吗？**

三个独立，职责分明，互不污染。
