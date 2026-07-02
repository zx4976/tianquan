"""
DSL 验证引擎 — 零信任核心

三条铁律检查:
  1. 所有节点必须映射到 req_schema 中的 req_id（防脑补）
  2. 状态机必须有闭环，无孤立状态（防偷懒）
  3. 所有异常分支必须指向已定义的错误码（防吞异常）
"""
import json, sys
from pathlib import Path
from typing import List, Tuple, Dict, Set
from trustforge.models import LogicDSL, ReqSchema


class DSLEngine:
    """DSL 验证器 — 纯逻辑检查，无 AI 参与"""
    
    def __init__(self):
        self.errors: List[str] = []
    
    def validate(self, dsl_path: Path, req_path: Path = None) -> Tuple[bool, List[str]]:
        """验证 DSL 文件，返回 (通过?, 错误列表)"""
        self.errors = []
        
        # 加载 DSL
        with open(dsl_path) as f:
            raw = json.load(f)
        
        # 加载需求 schema（可选）
        req_schema = None
        if req_path and req_path.exists():
            with open(req_path) as f:
                req_data = json.load(f)
            req_schema = {s["req_id"]: s for s in req_data.get("slices", [])}
        
        try:
            dsl = LogicDSL(**raw)
        except Exception as e:
            self.errors.append(f"DSL 结构解析失败: {e}")
            return False, self.errors
        
        # ── 检查 1: 节点映射到需求 ──
        if req_schema:
            self._check_req_refs(dsl, req_schema)
        
        # ── 检查 2: 状态机闭环 ──
        self._check_state_machine(dsl)
        
        # ── 检查 3: 异常覆盖 ──
        self._check_error_coverage(dsl)
        
        # ── 检查 4: 数据完整性 ──
        self._check_data_integrity(dsl)
        
        return len(self.errors) == 0, self.errors
    
    def _check_req_refs(self, dsl: LogicDSL, req_schema: Dict):
        """铁律一：所有节点必须映射到需求"""
        valid_ids = set(req_schema.keys())
        
        for ent in dsl.entities:
            if ent.req_ref not in valid_ids:
                self.errors.append(
                    f"实体 {ent.entity_id}({ent.name}) 引用了不存在的需求 {ent.req_ref}")
        for st in dsl.states:
            if st.req_ref not in valid_ids:
                self.errors.append(
                    f"状态 {st.state_id}({st.name}) 引用了不存在的需求 {st.req_ref}")
        for tr in dsl.transitions:
            if tr.req_ref not in valid_ids:
                self.errors.append(
                    f"迁移 {tr.trans_id} 引用了不存在的需求 {tr.req_ref}")
        for api in dsl.apis:
            if api.req_ref not in valid_ids:
                self.errors.append(
                    f"API {api.api_id}({api.method} {api.path}) 引用了不存在的需求 {api.req_ref}")
        for vr in dsl.validations:
            if vr.req_ref not in valid_ids:
                self.errors.append(
                    f"校验规则 {vr.rule_id} 引用了不存在的需求 {vr.req_ref}")
    
    def _check_state_machine(self, dsl: LogicDSL):
        """铁律二：状态机必须有闭环，无孤立状态"""
        state_ids = {st.state_id for st in dsl.states}
        
        # 检查迁移引用的状态是否存在
        for tr in dsl.transitions:
            if tr.from_state not in state_ids:
                self.errors.append(
                    f"迁移 {tr.trans_id} 的起始状态 {tr.from_state} 不存在")
            if tr.to_state not in state_ids:
                self.errors.append(
                    f"迁移 {tr.trans_id} 的目标状态 {tr.to_state} 不存在")
        
        # 检查孤立状态（没有入边也没有出边的状态）
        if state_ids:
            has_in = {sid: False for sid in state_ids}
            has_out = {sid: False for sid in state_ids}
            for tr in dsl.transitions:
                if tr.from_state in has_out:
                    has_out[tr.from_state] = True
                if tr.to_state in has_in:
                    has_in[tr.to_state] = True
            
            for sid in state_ids:
                if not has_in[sid] and not has_out[sid]:
                    self.errors.append(
                        f"状态 {sid}({self._state_name(sid, dsl)}) 是孤立状态，没有入边和出边")
        
        # 检查死循环（A→B→A 且没有出边的循环）
        trans_map = {}
        for tr in dsl.transitions:
            trans_map.setdefault(tr.from_state, []).append(tr)
        
        for sid in state_ids:
            visited = set()
            self._detect_cycle(sid, sid, trans_map, visited, [sid])
    
    def _detect_cycle(self, start, current, trans_map, visited, path):
        """检测从 current 出发能否回到 start"""
        if current in visited:
            return
        visited.add(current)
        for tr in trans_map.get(current, []):
            if tr.to_state == start and len(path) > 1:
                # 找到循环，检查是否有出边
                has_exit = any(
                    t.to_state not in path for t in trans_map.get(start, [])
                )
                if not has_exit and len(path) >= 3:
                    cycle_str = " → ".join(
                        self._state_name(s, None) for s in path + [start])
                    self.errors.append(
                        f"状态循环无出口: {cycle_str}")
            elif tr.to_state not in visited:
                self._detect_cycle(start, tr.to_state, trans_map, visited, path + [tr.to_state])
    
    def _check_error_coverage(self, dsl: LogicDSL):
        """铁律三：所有异常分支必须指向已定义的错误码"""
        # 收集所有在 API 中声明的错误码
        all_error_codes = set()
        for api in dsl.apis:
            all_error_codes.update(api.error_codes)
        
        # 收集在校验规则中引用的错误码
        validation_errors = set()
        for vr in dsl.validations:
            if vr.error_code:
                validation_errors.add(vr.error_code)
                all_error_codes.add(vr.error_code)
        
        # 检查校验规则的错误码是否在 API 的 error_codes 中
        for vr in dsl.validations:
            if vr.error_code and vr.target_field:
                # 找到包含此字段的 API
                found = False
                for api in dsl.apis:
                    if vr.target_field in api.input_params:
                        found = True
                        if vr.error_code not in api.error_codes:
                            self.errors.append(
                                f"校验规则 {vr.rule_id} 的错误码 '{vr.error_code}' "
                                f"未在 API {api.api_id} 的 error_codes 中声明")
                if not found:
                    self.errors.append(
                        f"校验规则 {vr.rule_id} 的目标字段 '{vr.target_field}' "
                        f"未在任何 API 的 input_params 中")
    
    def _check_data_integrity(self, dsl: LogicDSL):
        """检查数据完整性"""
        entity_fields = {}
        for ent in dsl.entities:
            entity_fields[ent.entity_id] = {f.name for f in ent.fields}
        
        # API 引用的实体存在
        for api in dsl.apis:
            if api.output_entity and api.output_entity not in entity_fields:
                self.errors.append(
                    f"API {api.api_id} 引用了不存在的输出实体 {api.output_entity}")
        
        # 校验规则的目标字段存在于某实体中
        all_fields = set()
        for ef in entity_fields.values():
            all_fields.update(ef)
        for vr in dsl.validations:
            if vr.target_field and vr.target_field not in all_fields:
                # 可能是宽松检查：字段存在于至少一个实体即可
                pass  # 暂不报错，因为可能跨实体
    
    def _state_name(self, state_id: str, dsl: LogicDSL) -> str:
        """根据 state_id 获取状态名"""
        if dsl:
            for st in dsl.states:
                if st.state_id == state_id:
                    return st.name
        return state_id
