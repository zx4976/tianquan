"""
trustforge 数据模型

需求切片 Schema (req_schema)：
  由大模型从 requirements.md 提取，CLI 验证每个 req_id 是否真实存在于原文。

逻辑 DSL (logic.dsl.json)：
  大模型声明状态、触发器、条件、数据校验规则。
  不包含任何控制流或计算逻辑。
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Literal


# ── 需求切片 Schema ───────────────────────────────────────────

class RequirementSlice(BaseModel):
    """一个不可再分的功能需求切片"""
    req_id: str = Field(pattern=r"^REQ-\d{4}$",
                        description="需求ID，格式 REQ-NNNN")
    title: str = Field(description="需求标题，简短")
    description: str = Field(description="需求描述，来自原文段落")
    source_section: str = Field(description="来源段落ID，如 'sec-3.2'")
    source_text: str = Field(description="原文精确摘录，用于验证")
    input_params: List[str] = Field(default_factory=list,
                                    description="输入参数名列表")
    output_params: List[str] = Field(default_factory=list,
                                     description="输出参数名列表")
    actions: List[str] = Field(default_factory=list,
                               description="动作动词列表，如 ['创建', '查询', '校验']")


class ReqSchema(BaseModel):
    """完整的需求切片清单"""
    title: str = Field(description="项目/功能名称")
    slices: List[RequirementSlice] = Field(description="所有需求切片")


# ── DSL 节点类型 ──────────────────────────────────────────────

class DataField(BaseModel):
    """数据字段定义"""
    name: str = Field(description="字段名")
    dtype: str = Field(description="数据类型: string/int/float/bool/email/date/ref")
    required: bool = True
    constraints: List[str] = Field(default_factory=list,
                                   description="约束描述列表，如 ['长度3-20', '正则a-zA-Z0-9']")


class DataEntity(BaseModel):
    """数据实体（对应数据库表/模型）"""
    entity_id: str = Field(pattern=r"^ENT-\d{4}$")
    name: str = Field(description="实体名")
    req_ref: str = Field(description="关联的需求ID，REQ-NNNN")
    fields: List[DataField] = Field(description="所有字段定义")
    unique_keys: List[str] = Field(default_factory=list, description="唯一键字段名列表")


class StateNode(BaseModel):
    """状态机节点"""
    state_id: str = Field(pattern=r"^ST-\d{4}$")
    name: str = Field(description="状态名，如 '未激活'/'已激活'/'已锁定'")
    req_ref: str = Field(description="关联的需求ID")
    entry_actions: List[str] = Field(default_factory=list,
                                     description="进入此状态时触发的动作列表")


class Transition(BaseModel):
    """状态迁移"""
    trans_id: str = Field(pattern=r"^TR-\d{4}$")
    from_state: str = Field(description="起始状态 ID")
    to_state: str = Field(description="目标状态 ID")
    trigger: str = Field(description="触发条件描述，如 '登录失败次数>=3'")
    req_ref: str = Field(description="关联的需求ID")
    guard_conditions: List[str] = Field(default_factory=list,
                                        description="守卫条件列表，全部满足才允许迁移")


class ApiEndpoint(BaseModel):
    """API 端点声明"""
    api_id: str = Field(pattern=r"^API-\d{4}$")
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"]
    path: str = Field(description="路径模板，如 '/api/v1/users/{user_id}'")
    req_ref: str = Field(description="关联的需求ID")
    input_params: List[str] = Field(description="输入参数名列表，引用DataField.name")
    output_entity: str = Field(description="输出实体ID，ENT-NNNN")
    error_codes: List[str] = Field(default_factory=list,
                                   description="可能的错误码列表")


class ValidationRule(BaseModel):
    """数据校验规则（声明式，不含计算逻辑）"""
    rule_id: str = Field(pattern=r"^VR-\d{4}$")
    target_field: str = Field(description="目标字段名")
    rule_type: Literal["required", "min_length", "max_length", "pattern",
                        "min", "max", "email", "unique", "enum", "ref_exists"]
    rule_param: Optional[str] = Field(default=None, description="规则参数值")
    error_code: str = Field(description="违反时的错误码")
    req_ref: str = Field(description="关联的需求ID")


class LogicDSL(BaseModel):
    """完整逻辑 DSL — 大模型能声明的全部内容"""
    entities: List[DataEntity] = Field(description="所有数据实体")
    states: List[StateNode] = Field(description="所有状态节点")
    transitions: List[Transition] = Field(description="所有状态迁移")
    apis: List[ApiEndpoint] = Field(description="所有API端点")
    validations: List[ValidationRule] = Field(description="所有数据校验规则")
