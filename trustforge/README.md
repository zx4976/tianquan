# TrustForge — 零信任隔离铸造机

> 强迫大模型进入"绝对闭卷模式"，只能输出离散化的结构数据，
> 从而在物理上切断它与内部训练数据"脑补"的通道。

## 安装

```bash
# 克隆项目
git clone <repo_url> trustforge
cd trustforge

# 安装依赖（推荐使用 uv）
uv venv
uv pip install -e .
uv pip install pytest fastapi httpx

# 验证安装
trustforge --help
```

## 使用流程

### 第一步：初始化项目

```bash
trustforge init my-project
cd my-project
```

生成 `trustforge.json`（DSL 模板）和 `requirements.md`（需求文档模板）。

### 第二步：编写需求文档

编辑 `requirements.md`，用 Markdown 格式描述功能需求。每个功能点用 `##` 标题分隔。

### 第三步：解析需求

```bash
trustforge parse requirements.md
```

生成 `requirements.req_schema.json`，包含每个需求切片的 `req_id` 和原文锚定。

### 第四步：编写 DSL（由大模型完成）

根据 `req_schema.json`，大模型输出 `logic.dsl.json`。大模型只能声明：

- **数据实体** — 字段名、类型、约束
- **状态机** — 状态节点、迁移、触发条件、守卫条件
- **API 端点** — 方法、路径、输入输出、错误码
- **校验规则** — 字段级校验声明

大模型**不能**写任何控制流（if/else/for/while）或计算逻辑。

### 第五步：验证 DSL

```bash
trustforge verify logic.dsl.json
```

硬核校验：
1. 所有节点必须映射到 `req_id`（防脑补）
2. 状态机必须有闭环，无孤立状态（防偷懒）
3. 所有异常分支必须指向已定义的错误码（防吞异常）

### 第六步：编译

```bash
trustforge compile logic.dsl.json -o ./generated
```

确定性生成：
- `models.py` — Pydantic 数据模型
- `state_machine.py` — 状态机（所有 if/else 由编译器生成）
- `api.py` — FastAPI 路由
- `validators.py` — 数据校验器
- `tests/` — PyTest 测试

### 第七步：沙盒验证

```bash
trustforge run logic.dsl.json -o ./out
```

真实执行测试，验证代码可编译、可运行。大模型无法篡改测试结果。

## 完整示例

```bash
# 从示例目录运行
cd examples/user_auth

# 解析需求
trustforge parse requirements.md

# 验证 DSL
trustforge verify logic.dsl.json

# 编译并测试
trustforge run logic.dsl.json
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

## 当前支持

| 特性 | 状态 |
|------|------|
| 需求解析 (parse) | ✅ |
| DSL 验证 (verify) | ✅ |
| Python 代码生成 (compile) | ✅ |
| 沙盒测试 (run) | ✅ |
| 状态机守卫条件 | ✅ |
| 数据校验规则 | ✅ |
| API 路由生成 | ✅ |
| 项目初始化 (init) | ✅ |
| 自定义错误码 | ✅ |

## 路线图

- [ ] Go 代码生成
- [ ] 更多守卫条件表达式支持
- [ ] DSL 可视化编辑器
- [ ] 读书理解模块集成
