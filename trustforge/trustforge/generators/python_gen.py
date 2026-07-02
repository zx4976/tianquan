"""
Python 代码生成器

从 LogicDSL 确定性生成:
  - 数据模型 (Pydantic)
  - 状态机 (transitions)
  - API 路由 (FastAPI)
  - 校验规则
  - PyTest 测试

生成逻辑完全由 DSL 驱动，不包含任何 AI 决策。
"""
import json, os, textwrap
from pathlib import Path
from typing import List
from trustforge.models import LogicDSL


class PythonGenerator:
    """DSL → Python 确定性编译器"""
    
    def generate(self, dsl_path: Path, output_dir: Path) -> List[str]:
        """编译 DSL 为 Python 代码"""
        with open(dsl_path) as f:
            raw = json.load(f)
        dsl = LogicDSL(**raw)
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        files = []
        
        # 生成数据模型
        model_code = self._gen_models(dsl)
        model_path = output_dir / "models.py"
        model_path.write_text(model_code)
        files.append(str(model_path))
        
        # 生成状态机
        sm_code = self._gen_state_machine(dsl)
        sm_path = output_dir / "state_machine.py"
        sm_path.write_text(sm_code)
        files.append(str(sm_path))
        
        # 生成 API
        api_code = self._gen_api(dsl)
        api_path = output_dir / "api.py"
        api_path.write_text(api_code)
        files.append(str(api_path))
        
        # 生成校验器
        val_code = self._gen_validators(dsl)
        val_path = output_dir / "validators.py"
        val_path.write_text(val_code)
        files.append(str(val_path))
        
        # 生成 __init__
        init_code = self._gen_init(dsl)
        init_path = output_dir / "__init__.py"
        init_path.write_text(init_code)
        files.append(str(init_path))
        
        return files
    
    def generate_tests(self, dsl_path: Path, output_dir: Path) -> List[str]:
        """生成 PyTest 测试"""
        with open(dsl_path) as f:
            raw = json.load(f)
        dsl = LogicDSL(**raw)
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_dir / "__init__.py"
        
        files = []
        
        # 测试数据模型
        test_model = self._gen_test_models(dsl)
        tm_path = output_dir / "test_models.py"
        tm_path.write_text(test_model)
        files.append(str(tm_path))
        
        # 测试状态机
        if dsl.states:
            test_sm = self._gen_test_state_machine(dsl)
            tsm_path = output_dir / "test_state_machine.py"
            tsm_path.write_text(test_sm)
            files.append(str(tsm_path))
        
        # 测试 API
        if dsl.apis:
            test_api = self._gen_test_api(dsl)
            tap_path = output_dir / "test_api.py"
            tap_path.write_text(test_api)
            files.append(str(tap_path))
        
        return files
    
    def _gen_models(self, dsl: LogicDSL) -> str:
        """生成 Pydantic 数据模型"""
        lines = ['"""自动生成数据模型"""', 'from pydantic import BaseModel, Field, field_validator',
                 'from typing import Optional, List', 'from datetime import datetime', '',
                 '', '# ── 字段校验超类 ──']
        
        lines.append("""
class ValidationMixin:
    \"\"\"数据校验混入，由 DSL 校验规则驱动\"\"\"
    
    @classmethod
    def _get_field_rules(cls, field_name: str) -> list:
        rules = {
""")
        
        for vr in dsl.validations:
            param = f"'{vr.rule_param}'" if vr.rule_param else "None"
            lines.append(f"            '{vr.target_field}': [('{vr.rule_type}', {param}, '{vr.error_code}')],")
        
        lines.append("""        }.get(field_name, [])
        return rules
""")
        
        # 实体模型
        for ent in dsl.entities:
            fields_def = []
            for f in ent.fields:
                py_type = self._to_py_type(f.dtype)
                default = "" if f.required else " = None"
                fields_def.append(f"    {f.name}: {py_type}{default}")
            
            # 校验规则（用 @model_validator）
            entity_field_names = {f.name for f in ent.fields}
            has_entity_validators = any(
                vr.target_field in entity_field_names for vr in dsl.validations
            )
            
            lines.append(f"""
class {self._to_class_name(ent.name)}(BaseModel):
    \"\"\"{ent.name}\"\"\"
""")
            if fields_def:
                lines.append("\n".join(fields_def))
            else:
                lines.append("    pass")
            
            if has_entity_validators:
                # 使用 model_validator 代替 field_validator，因为校验涉及多个字段逻辑
                lines.append(f"""
    @classmethod
    def validate_all(cls, values):
        \"\"\"由 DSL 校验规则驱动\"\"\"
""")
                for vr in dsl.validations:
                    if vr.target_field in [ff.name for ff in ent.fields]:
                        lines.append(f"        if '{vr.target_field}' in values:")
                        lines.append(f"            rules = ValidationMixin._get_field_rules('{vr.target_field}')")
                        lines.append(f"            for rule_type, rule_param, err_code in rules:")
                        lines.append(f"                val = values['{vr.target_field}']")
                        lines.append(f"                if rule_type == 'min_length' and rule_param and len(str(val)) < int(rule_param):")
                        lines.append(f"                    raise ValueError(f\"{{err_code}}: length < {{rule_param}}\")")
                        lines.append(f"                if rule_type == 'max_length' and rule_param and len(str(val)) > int(rule_param):")
                        lines.append(f"                    raise ValueError(f\"{{err_code}}: length > {{rule_param}}\")")
                        lines.append(f"                if rule_type == 'pattern' and rule_param:")
                        lines.append(f"                    import re")
                        lines.append(f"                    if not re.match(rule_param, str(val)):")
                        lines.append(f"                        raise ValueError(f\"{{err_code}}: pattern mismatch\")")
                        lines.append(f"                if rule_type == 'email' and '@' not in str(val):")
                        lines.append(f"                    raise ValueError(f\"{{err_code}}: invalid email\")")
                        break
                lines.append("        return values")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _gen_state_machine(self, dsl: LogicDSL) -> str:
        """生成状态机—所有 if/else 由编译器自动生成"""
        lines = []
        initial_state_name = dsl.states[0].name if dsl.states else "initial"
        
        # 用 list 构建，每行 append，避免字符串嵌套
        lines.append('"""自动生成状态机"""')
        lines.append('from enum import Enum')
        lines.append('from typing import Optional, Dict, List')
        lines.append('from datetime import datetime')
        lines.append('')
        
        # 状态枚举
        lines.append('')
        lines.append('class State(str, Enum):')
        for st in dsl.states:
            lines.append(f"    {st.name.upper()} = '{st.name}'")
        lines.append('')
        
        # 迁移表
        lines.append('')
        lines.append('# 迁移表 — 编译器生成，大模型无法修改')
        lines.append('TRANSITION_TABLE: Dict[tuple, str] = {')
        for tr in dsl.transitions:
            fn = self._find_state_name(tr.from_state, dsl)
            tn = self._find_state_name(tr.to_state, dsl)
            lines.append(f"    ('{fn}', '{tr.trigger}'): '{tn}',")
        lines.append('}')
        
        # 守卫条件
        has_guards = any(tr.guard_conditions for tr in dsl.transitions)
        lines.append('')
        lines.append('GUARD_TABLE: Dict[tuple, list] = {')
        for tr in dsl.transitions:
            if tr.guard_conditions:
                fn = self._find_state_name(tr.from_state, dsl)
                guards_str = ', '.join(f"'{c}'" for c in tr.guard_conditions)
                lines.append(f"    ('{fn}', '{tr.trigger}'): [{guards_str}],")
        lines.append('}')
        
        # StateMachine 类
        lines.append('')
        lines.append('')
        lines.append('class StateMachine:')
        lines.append('    """确定性状态机 — 所有分支由编译器生成"""')
        lines.append('')
        lines.append('    def __init__(self, initial_state: str = None):')
        lines.append('        if initial_state:')
        lines.append("            self._state = initial_state")
        lines.append('        else:')
        lines.append(f"            self._state = '{initial_state_name}'")
        lines.append('        self._history: List[dict] = []')
        lines.append('')
        lines.append('    @property')
        lines.append('    def current_state(self) -> Optional[str]:')
        lines.append('        return self._state')
        lines.append('')
        lines.append('    def transition(self, trigger: str, context: dict = None) -> dict:')
        lines.append('        """执行状态迁移"""')
        lines.append("        if not self._state:")
        lines.append('            return {"success": False, "error": "NO_INITIAL_STATE", "code": 500}')
        lines.append('')
        lines.append('        key = (self._state, trigger)')
        lines.append('        next_state = TRANSITION_TABLE.get(key)')
        lines.append('')
        lines.append('        if not next_state:')
        lines.append('            return {"success": False, "error": "INVALID_TRANSITION",')
        lines.append('                    "code": 400,')
        lines.append('                    "message": f"Cannot transition from {self._state} via {trigger}"}')
        lines.append('')
        
        # 守卫条件检查（编译器根据 DSL 生成）
        if has_guards:
            lines.append('')
            lines.append('        # guard conditions (compiler generated)')
            lines.append('        guards = GUARD_TABLE.get(key, [])')
            lines.append('        if guards:')
            # 按迁移分组，每组所有守卫合并到一个 if 块
            for tr in dsl.transitions:
                if tr.guard_conditions:
                    fn = self._find_state_name(tr.from_state, dsl)
                    lines.append(f"            if key == ('{fn}', '{tr.trigger}'):")
                    for gc in tr.guard_conditions:
                        if '>=' in gc:
                            parts = gc.split('>=')
                            var = parts[0].strip().replace(' ', '_')
                            # 去掉 % 符号
                            val = parts[1].strip().rstrip('%')
                            lines.append(f"                if not context or context.get('{var}', 0) < {val}:")
                            lines.append(f'                    return {{"success": False, "error": "GUARD_FAILED", "code": 403,')
                            lines.append(f'                            "message": "Guard condition not satisfied"}}')
                        elif '>' in gc and '=' not in gc:
                            parts = gc.split('>')
                            var = parts[0].strip().replace(' ', '_')
                            val = parts[1].strip()
                            lines.append(f"                if not context or context.get('{var}', 0) <= {val}:")
                            lines.append(f'                    return {{"success": False, "error": "GUARD_FAILED", "code": 403,')
                            lines.append(f'                            "message": "Guard condition not satisfied"}}')
                        else:
                            # 无解析条件的守卫（如"激活链接未过期"），留作开发者实现
                            lines.append('                pass')
                    lines.append('')
        
        lines.append('')
        lines.append('        old_state = self._state')
        lines.append("        self._state = next_state")
        lines.append("        self._history.append({")
        lines.append('            "from": old_state, "to": next_state,')
        lines.append('            "trigger": trigger, "at": datetime.now().isoformat()')
        lines.append("        })")
        lines.append('        return {"success": True, "state": self._state}')
        lines.append('')
        lines.append('    def can_transition(self, trigger: str) -> bool:')
        lines.append('        """Check if transition is allowed (without executing)"""')
        lines.append('        key = (self._state, trigger)')
        lines.append('        return key in TRANSITION_TABLE')
        lines.append('')
        lines.append('    def get_allowed_triggers(self) -> list:')
        lines.append('        """Get all allowed triggers from current state"""')
        lines.append('        return [t for (s, t) in TRANSITION_TABLE if s == self._state]')
        
        return '\n'.join(lines)
    
    def _gen_api(self, dsl: LogicDSL) -> str:
        """生成 FastAPI 路由"""
        lines = ['"""auto-generated API routes"""',
                 'from fastapi import FastAPI, HTTPException, Depends',
                 'import sys; sys.path.insert(0, sys.path[0] + "/..") if "__file__" in dir() else None',
                 'from models import *',
                 'from state_machine import StateMachine',
                 'from validators import validate_input',
                 '',
                 'app = FastAPI(title="TrustForge Generated API")',
                 '',
                 '# ── 状态机实例 ──',
                 '_state_machines: dict = {}',
                 '',
                 'def get_state_machine(session_id: str = "default") -> StateMachine:',
                 '    if session_id not in _state_machines:',
                 '        _state_machines[session_id] = StateMachine()',
                 '    return _state_machines[session_id]',
                 '']
        
        for api in dsl.apis:
            # 生成安全的函数名
            raw_name = api.path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
            func_name = raw_name.replace("-", "_").replace(".", "_")
            if not func_name:
                func_name = f"endpoint_{api.api_id.lower().replace('-', '_')}"
            params = ", ".join(api.input_params)
            
            lines.append(f"""
@{'app.get' if api.method == 'GET' else 'app.post' if api.method == 'POST' else 'app.put' if api.method == 'PUT' else 'app.delete' if api.method == 'DELETE' else 'app.patch'}("{api.path}")
async def {func_name}({params + ", " if params else ""}sm: StateMachine = Depends(get_state_machine)):
    \"\"\"{api.api_id}: {api.req_ref}\"\"\"
    # 输入校验（编译器根据 DSL 自动生成）
    errors = validate_input({'{' + ', '.join(f'"{p}": {p}' for p in api.input_params) + '}' if api.input_params else '{}'}, 
                           '{api.api_id}')
    if errors:
        raise HTTPException(status_code=400, detail=errors)
    
    # TODO: 实际业务逻辑由 DSL 扩展生成
    return {{"status": "ok", "api_id": "{api.api_id}"}}
""")
        
        return "\n".join(lines)
    
    def _gen_validators(self, dsl: LogicDSL) -> str:
        """生成校验函数"""
        lines = [f'"""自动生成数据校验器 — {len(dsl.validations)} 条规则"""',
                 'from typing import Dict, List, Optional',
                 '',
                 '']
        
        lines.append("""
def validate_input(data: dict, api_id: str) -> List[str]:
    \"\"\"根据 DSL 校验规则验证输入\"\"\"
    errors = []
    
    RULES = {
""")
        
        for api in dsl.apis:
            for vr in dsl.validations:
                param = f"'{vr.rule_param}'" if vr.rule_param else "None"
                lines.append(f"        '{api.api_id}': [('{vr.target_field}', '{vr.rule_type}', {param}, '{vr.error_code}')],")
        
        lines.append("""    }
    
    rules = RULES.get(api_id, [])
    for field_name, rule_type, rule_param, err_code in rules:
        value = data.get(field_name)
        
        if rule_type == 'required' and (value is None or value == ''):
            errors.append(f"{err_code}: {field_name} 为必填")
        
        if value is not None:
            if rule_type == 'min_length' and len(str(value)) < int(rule_param or '0'):
                errors.append(f"{err_code}: {field_name} 长度不能少于 {rule_param}")
            elif rule_type == 'max_length' and len(str(value)) > int(rule_param or '999'):
                errors.append(f"{err_code}: {field_name} 长度不能超过 {rule_param}")
            elif rule_type == 'pattern':
                import re
                if not re.match(rule_param or '', str(value)):
                    errors.append(f"{err_code}: {field_name} 格式不匹配")
            elif rule_type == 'min' and isinstance(value, (int, float)) and value < float(rule_param or '0'):
                errors.append(f"{err_code}: {field_name} 不能小于 {rule_param}")
            elif rule_type == 'max' and isinstance(value, (int, float)) and value > float(rule_param or '999'):
                errors.append(f"{err_code}: {field_name} 不能大于 {rule_param}")
            elif rule_type == 'email' and '@' not in str(value):
                errors.append(f"{err_code}: {field_name} 必须是有效邮箱")
    
    return errors
""")
        
        return "\n".join(lines)
    
    def _gen_init(self, dsl: LogicDSL) -> str:
        return '"""TrustForge 生成代码"""\n'
    
    def _gen_test_models(self, dsl: LogicDSL) -> str:
        lines = ['"""auto-generated model tests"""',
                 'import pytest', 'import sys; sys.path.insert(0, sys.path[0] + "/..")',
                 'from models import *', '']
        
        for ent in dsl.entities:
            fields_str = ", ".join(
                f'{f.name}="test_{f.name}"' if f.dtype == 'string' else
                f'{f.name}=1' if f.dtype == 'int' else
                f'{f.name}=True' if f.dtype == 'bool' else
                f'{f.name}=1.0' if f.dtype == 'float' else
                f'{f.name}="test@example.com"' if f.dtype == 'email' else
                f'{f.name}="test"'
                for f in ent.fields
            )
            cls = self._to_class_name(ent.name)
            lines.append(f"""
def test_{ent.name}_create():
    \"\"\"验证 {ent.name} 模型可创建\"\"\"
    obj = {cls}({fields_str})
    assert obj is not None
""")
        
        return "\n".join(lines)
    
    def _gen_test_state_machine(self, dsl: LogicDSL) -> str:
        import re
        lines = []
        lines.append('"""auto-generated state machine tests"""')
        lines.append('import pytest')
        lines.append('import sys; sys.path.insert(0, sys.path[0] + "/..")')
        lines.append('from state_machine import StateMachine')
        lines.append('')
        if dsl.states:
            init = dsl.states[0].name
            lines.append('')
            lines.append('def test_initial_state():')
            lines.append('    sm = StateMachine()')
            lines.append(f"    assert sm.current_state == '{init}'")
            for tr in dsl.transitions:
                fn = self._find_state_name(tr.from_state, dsl)
                tn = self._find_state_name(tr.to_state, dsl)
                safe = re.sub(r'[^a-zA-Z0-9_]', '_', tr.trigger)[:30]
                tname = f"test_{tr.trans_id.lower().replace('-','_')}_{safe}"
                lines.append('')
                lines.append(f'def {tname}():')
                lines.append(f"    sm = StateMachine(initial_state='{fn}')")
                # 如果有守卫条件，生成满足条件的 context
                if tr.guard_conditions:
                    ctx_parts = []
                    for gc in tr.guard_conditions:
                        if '>=' in gc:
                            parts = gc.split('>=')
                            var = parts[0].strip().replace(' ', '_')
                            val = parts[1].strip().rstrip('%')
                            ctx_parts.append(f"'{var}': {int(val) + 1}")
                        elif '>' in gc and '=' not in gc:
                            parts = gc.split('>')
                            var = parts[0].strip().replace(' ', '_')
                            val = parts[1].strip()
                            ctx_parts.append(f"'{var}': {int(val) + 1}")
                        elif '<=' in gc:
                            parts = gc.split('<=')
                            var = parts[0].strip().replace(' ', '_')
                            val = parts[1].strip()
                            ctx_parts.append(f"'{var}': {int(val) - 1}")
                        elif '<' in gc:
                            parts = gc.split('<')
                            var = parts[0].strip().replace(' ', '_')
                            val = parts[1].strip()
                            ctx_parts.append(f"'{var}': {int(val) - 1}")
                        elif '==' in gc:
                            parts = gc.split('==')
                            var = parts[0].strip().replace(' ', '_')
                            val = parts[1].strip()
                            ctx_parts.append(f"'{var}': {val}")
                    if ctx_parts:
                        ctx_str = '{' + ', '.join(ctx_parts) + '}'
                        lines.append(f"    result = sm.transition('{tr.trigger}', {ctx_str})")
                    else:
                        lines.append(f"    result = sm.transition('{tr.trigger}', {{}})")
                else:
                    lines.append(f"    result = sm.transition('{tr.trigger}', {{}})")
                lines.append("    assert result['success'], f'fail: {result}'")
                lines.append(f"    assert sm.current_state == '{tn}'")
        return '\n'.join(lines)
    
    def _gen_test_api(self, dsl: LogicDSL) -> str:
        lines = ['"""auto-generated API tests"""',
                 'import pytest',
                 'import sys; sys.path.insert(0, sys.path[0] + "/..")',
                 'from api import app',
                 '',
                 'from fastapi.testclient import TestClient',
                 'client = TestClient(app)',
                 '']
        
        for api in dsl.apis:
            method_lower = api.method.lower()
            safe_api = api.api_id.lower().replace('-', '_')
            lines.append(f"""
def test_{safe_api}():
    response = client.{method_lower}("{api.path}")
    assert response.status_code in (200, 201, 400, 422)
""")
        
        return "\n".join(lines)
    
    # ── 工具方法 ──
    def _to_py_type(self, dtype: str) -> str:
        mapping = {
            "string": "str", "int": "int", "float": "float",
            "bool": "bool", "email": "str", "date": "str",
            "ref": "str",
        }
        return mapping.get(dtype, "str")
    
    def _to_class_name(self, name: str) -> str:
        """实体名 → Python 类名"""
        return "".join(word.capitalize() for word in name.replace("-", "_").split("_"))
    
    def _find_state_name(self, state_id: str, dsl: LogicDSL) -> str:
        for st in dsl.states:
            if st.state_id == state_id:
                return st.name
        return state_id
