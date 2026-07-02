    def _gen_test_state_machine(self, dsl: LogicDSL) -> str:
        import re
        lines = []
        lines.append('"""自动生成状态机测试"""')
        lines.append('import pytest')
        lines.append('from ..state_machine import StateMachine')
        lines.append('')
        
        if dsl.states:
            initial = dsl.states[0].name
            lines.append('')
            lines.append('def test_initial_state():')
            lines.append('    sm = StateMachine()')
            lines.append(f"    assert sm.current_state == '{initial}'")
            
            for tr in dsl.transitions:
                fn = self._find_state_name(tr.from_state, dsl)
                tn = self._find_state_name(tr.to_state, dsl)
                safe = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fff]', '_', tr.trigger)[:30]
                test_name = f"test_{tr.trans_id.lower()}_{safe}"
                lines.append('')
                lines.append(f'def {test_name}():')
                lines.append(f"    sm = StateMachine(initial_state='{fn}')")
                lines.append(f"    result = sm.transition('{tr.trigger}', {{}})")
                lines.append("    assert result['success'], f'Transition failed: {result}'")
                lines.append(f"    assert sm.current_state == '{tn}', f'Expected {tn}, got {{sm.current_state}}'")
        
        return '\n'.join(lines)