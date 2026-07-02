#!/usr/bin/env python3
"""
零信任隔离铸造机 — TrustForge

强制大模型进入"绝对闭卷模式"，只能输出离散化的结构数据，
从而在物理上切断它与内部训练数据"脑补"的通道。

使用流程:
  1. trustforge init             初始化项目
  2. trustforge parse req.md     解析需求 → req_schema.json
  3. (大模型根据 req_schema 生成 logic.dsl.json)
  4. trustforge verify dsl.json  验证 DSL 逻辑完整性
  5. trustforge compile dsl.json 编译为代码+测试
  6. trustforge run dsl.json     沙盒执行验证
"""
import sys, json, os, argparse, subprocess, textwrap
from pathlib import Path


def cmd_understanding(args):
    """读书理解模块 — 用知识引擎 venv 的 python 直接执行"""
    engine_dir = os.path.expanduser("~/projects/knowledge-engine")
    venv_python = os.path.join(engine_dir, ".venv", "bin", "python3")
    script = os.path.join(os.path.dirname(__file__), "understand.py")
    
    cmd = [venv_python, script]
    
    if args.action == "store":
        cmd += ["store", args.book_id, "--dim", args.dim, "--motivation", args.motivation, "--content", args.content, "--application", args.application]
        if args.evidence: cmd += ["--evidence", args.evidence]
        if args.imp: cmd += ["--imp", str(args.imp)]
    elif args.action == "derive":
        cmd += ["derive", args.book_id, args.question]
    elif args.action == "mark":
        cmd += ["mark", args.book_id, args.chapter]
    else:
        cmd.append(args.action)
        if hasattr(args, 'book_id') and args.book_id:
            cmd.append(args.book_id)
    
    result = subprocess.run(cmd, cwd=engine_dir, capture_output=False)
    return result.returncode


def cmd_init(args):
    """初始化 trustforge 项目"""
    path = Path(args.dir) if args.dir else Path(".")
    examples_dir = Path(__file__).parent.parent / "examples" / "user_auth"
    
    # 创建 DSL 模板
    dsl_template = {
        "entities": [
            {"entity_id": "ENT-0001", "name": "example", "req_ref": "REQ-0001",
             "fields": [{"name": "id", "dtype": "string", "required": True, "constraints": []}],
             "unique_keys": ["id"]}
        ],
        "states": [
            {"state_id": "ST-0001", "name": "初始", "req_ref": "REQ-0001", "entry_actions": []}
        ],
        "transitions": [],
        "apis": [
            {"api_id": "API-0001", "method": "GET", "path": "/api/v1/health",
             "req_ref": "REQ-0001", "input_params": [], "output_entity": "ENT-0001", "error_codes": []}
        ],
        "validations": []
    }
    
    req_template = "# 需求文档\n\n## 需求一\n\n功能描述\n"
    
    (path / "trustforge.json").write_text(json.dumps(dsl_template, ensure_ascii=False, indent=2))
    (path / "requirements.md").write_text(req_template)
    
    print(f"  ✅ trustforge 项目已初始化: {path.resolve()}")
    print(f"  📄 trustforge.json  — DSL 模板")
    print(f"  📄 requirements.md  — 需求文档模板")
    print(f"  📁 examples/user_auth/ — 完整示例")
    return 0


def cmd_parse(args):
    """解析需求文档"""
    from trustforge.models import ReqSchema, RequirementSlice
    
    req_path = Path(args.file)
    if not req_path.exists():
        print(f"  ❌ 需求文件不存在: {req_path}")
        return 1
    
    with open(req_path) as f:
        content = f.read()
    
    print(f"  📋 读取需求文件: {req_path.name}")
    print(f"  📏 原文长度: {len(content)} 字符")
    
    out_path = args.output or req_path.with_suffix(".req_schema.json")
    
    import re
    sections = re.split(r'\n#{1,3}\s+|\n---+\n', content)
    
    slices = []
    for i, sec in enumerate(sections):
        sec = sec.strip()
        if len(sec) < 20:
            continue
        lines = [l.strip() for l in sec.split('\n') if l.strip()]
        title = lines[0][:80] if lines else f"段落{i}"
        slices.append({
            "req_id": f"REQ-{i+1:04d}",
            "title": title[:80],
            "description": sec[:300],
            "source_section": f"sec-{i+1}",
            "source_text": sec[:200],
            "input_params": [],
            "output_params": [],
            "actions": [],
        })
    
    schema = {"title": req_path.stem, "slices": slices}
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    
    print(f"  ✅ 需求切片已生成: {out_path} ({len(slices)} 个切片)")
    print(f"  ℹ️  请用大模型补充 input_params/output_params/actions")
    print(f"     然后根据 req_schema.json 编写 logic.dsl.json")
    return 0


def cmd_verify(args):
    """验证 DSL 逻辑完整性"""
    from trustforge.validators.dsl_validator import DSLEngine
    
    dsl_path = Path(args.dsl)
    req_path = Path(args.req_schema) if args.req_schema else None
    
    if not dsl_path.exists():
        print(f"  ❌ DSL 文件不存在: {dsl_path}")
        return 1
    
    engine = DSLEngine()
    ok, errors = engine.validate(dsl_path, req_path)
    
    if ok:
        print(f"  ✅ DSL 验证通过")
        print(f"     — 所有节点映射到需求")
        print(f"     — 状态机无孤立节点")
        print(f"     — 异常分支已覆盖")
        return 0
    else:
        print(f"  ❌ DSL 验证失败 — {len(errors)} 个问题:")
        for e in errors:
            print(f"    ✗ {e}")
        print(f"\n  ℹ️  请修正 DSL 后重新验证")
        return 1


def cmd_compile(args):
    """编译 DSL 为目标代码"""
    from trustforge.validators.dsl_validator import DSLEngine
    from trustforge.generators.python_gen import PythonGenerator
    
    dsl_path = Path(args.dsl)
    req_path = Path(args.req_schema) if args.req_schema else None
    
    if not dsl_path.exists():
        print(f"  ❌ DSL 文件不存在: {dsl_path}")
        return 1
    
    # 先验证
    engine = DSLEngine()
    ok, errors = engine.validate(dsl_path, req_path)
    if not ok:
        print(f"  ❌ DSL 验证失败，无法编译:")
        for e in errors:
            print(f"    ✗ {e}")
        print(f"  请先运行: trustforge verify {args.dsl}")
        return 1
    
    # 编译
    gen = PythonGenerator()
    output_dir = Path(args.output) if args.output else Path(".") / "generated"
    
    files = gen.generate(dsl_path, output_dir)
    print(f"  ✅ 编译成功 — 生成 {len(files)} 个文件:")
    for f in files:
        size = Path(f).stat().st_size
        print(f"    📄 {Path(f).name} ({size} 字节)")
    
    # 生成测试
    test_dir = output_dir / "tests"
    test_files = gen.generate_tests(dsl_path, test_dir)
    print(f"  🧪 测试文件: {len(test_files)} 个")
    for f in test_files:
        print(f"    📄 {Path(f).name}")
    
    print(f"\n  📂 输出目录: {output_dir.resolve()}")
    return 0


def cmd_run(args):
    """沙盒运行验证"""
    from trustforge.validators.dsl_validator import DSLEngine
    from trustforge.generators.python_gen import PythonGenerator
    
    dsl_path = Path(args.dsl)
    if not dsl_path.exists():
        print(f"  ❌ DSL 文件不存在: {dsl_path}")
        return 1
    
    output_dir = Path(args.output) if args.output else Path(".trustforge_out")
    
    # 编译
    gen = PythonGenerator()
    files = gen.generate(dsl_path, output_dir)
    gen.generate_tests(dsl_path, output_dir / "tests")
    
    # 沙盒运行
    print(f"\n{'━'*56}")
    print(f"  🔒 沙盒执行")
    print(f"{'━'*56}")
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(output_dir / "tests"), "-v", "--tb=short"],
        capture_output=True, text=True, timeout=60
    )
    
    # 输出 pytest 结果
    out = result.stdout
    if len(out) > 2000:
        # 只摘录最后的 summary
        lines = out.split('\n')
        summary_lines = [l for l in lines if 'PASSED' in l or 'FAILED' in l or 'ERROR' in l or 'passed' in l or 'failed' in l]
        if summary_lines:
            print('\n'.join(summary_lines[-20:]))
        else:
            print(out[-1000:])
    else:
        print(out)
    
    if result.stderr and 'Error' in result.stderr:
        print(result.stderr[-500:])
    
    passed = result.returncode == 0
    if passed:
        print(f"\n  ✅ 沙盒测试全部通过")
        print(f"  📂 代码已生成: {output_dir.resolve()}")
    else:
        detail = result.stderr[-300:] if 'Error' in result.stderr else ""
        print(f"\n  ❌ 沙盒测试失败 ({result.returncode})")
        if detail:
            print(f"  {detail}")
    
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(
        description="TrustForge — 零信任隔离铸造机",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            使用流程:
              1. trustforge init              初始化项目
              2. trustforge parse req.md       解析需求 → req_schema.json
              3. (大模型根据 req_schema 生成 logic.dsl.json)
              4. trustforge verify dsl.json    验证 DSL 逻辑完整性
              5. trustforge compile dsl.json   编译为代码+测试
              6. trustforge run dsl.json       沙盒执行验证
        """)
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # understand
    p_und = subparsers.add_parser("understand", help="读书理解模块")
    p_und_sub = p_und.add_subparsers(dest="action")
    
    p_store = p_und_sub.add_parser("store", help="存入一条理解")
    p_store.add_argument("book_id", help="书籍 ID")
    p_store.add_argument("--dim", required=True, help="维度（如 '第7章'）")
    p_store.add_argument("--motivation", required=True, help="由来/动机：这个知识为了解决什么问题而诞生？")
    p_store.add_argument("--content", required=True, help="核心断言/定理：它的核心定理/定义是什么？")
    p_store.add_argument("--application", required=True, help="应用/推导：它能用来推导什么？解决什么问题？")
    p_store.add_argument("--evidence", help="原文证据")
    p_store.add_argument("--imp", type=int, default=5, help="重要度 1-10")
    
    p_status = p_und_sub.add_parser("status", help="查看理解进度")
    p_status.add_argument("book_id", help="书籍 ID")
    
    p_mark = p_und_sub.add_parser("mark", help="标记章节已读")
    p_mark.add_argument("book_id", help="书籍 ID")
    p_mark.add_argument("chapter", help="章节名")
    
    p_audit = p_und_sub.add_parser("audit", help="全书闭卷审计")
    p_audit.add_argument("book_id", help="书籍 ID")
    
    p_verify = p_und_sub.add_parser("verify", help="验证单条理解（闭卷推导）")
    p_verify.add_argument("book_id", help="书籍 ID")
    p_verify.add_argument("--dim", help="维度（可选，不指定则验证最重要的那条）")
    
    p_mr = p_und_sub.add_parser("mark-read", help="标记整本已读")
    p_mr.add_argument("book_id", help="书籍 ID")
    
    p_info = p_und_sub.add_parser("info", help="书籍信息")
    p_info.add_argument("book_id", help="书籍 ID")
    
    p_list = p_und_sub.add_parser("list", help="列出未读书籍")
    
    p_derive = p_und_sub.add_parser("derive", help="基于知识的符号推导")
    p_derive.add_argument("book_id", help="书籍 ID")
    p_derive.add_argument("question", help="问题描述")
    
    for s in [p_store, p_status, p_mark, p_audit, p_verify, p_mr, p_info, p_list, p_derive]:
        s.set_defaults(func=cmd_understanding)
    
    # init
    p_init = subparsers.add_parser("init", help="初始化 trustforge 项目")
    p_init.add_argument("dir", nargs="?", default=".", help="项目目录 (默认当前目录)")
    p_init.set_defaults(func=cmd_init)
    
    # parse
    p_parse = subparsers.add_parser("parse", help="解析需求文档为需求切片")
    p_parse.add_argument("file", help="requirements.md 路径")
    p_parse.add_argument("-o", "--output", help="输出路径 (默认同目录)")
    p_parse.set_defaults(func=cmd_parse)
    
    # verify
    p_verify = subparsers.add_parser("verify", help="验证 DSL 逻辑完整性")
    p_verify.add_argument("dsl", help="logic.dsl.json 路径")
    p_verify.add_argument("--req-schema", help="req_schema.json 路径 (可选，验证req映射)")
    p_verify.set_defaults(func=cmd_verify)
    
    # compile
    p_compile = subparsers.add_parser("compile", help="编译 DSL 为目标代码+测试")
    p_compile.add_argument("dsl", help="logic.dsl.json 路径")
    p_compile.add_argument("-o", "--output", help="输出目录 (默认 ./generated)")
    p_compile.add_argument("--req-schema", help="req_schema.json 路径 (可选，验证req映射)")
    p_compile.set_defaults(func=cmd_compile)
    
    # run
    p_run = subparsers.add_parser("run", help="沙盒运行验证")
    p_run.add_argument("dsl", help="logic.dsl.json 路径")
    p_run.add_argument("-o", "--output", help="输出目录 (默认 ./.trustforge_out)")
    p_run.set_defaults(func=cmd_run)
    
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
