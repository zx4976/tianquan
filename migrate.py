#!/usr/bin/env python3
"""
隐光迁移工具 — 只导出记忆和知识，不碰 Hermes 配置

用法:
  python3 migrate.py export /path/to/backup.tar.gz
  python3 migrate.py import /path/to/backup.tar.gz
"""
import sys
import os
import tarfile
import json
import shutil
from datetime import datetime

CORE_FILES = {
    "记忆": os.path.expanduser("~/.hermes/memory.db"),
    "知识引擎代码": os.path.expanduser("~/.hermes/knowledge-engine/src"),
    "知识引擎数据": os.path.expanduser("~/.hermes/knowledge-engine/data"),
    "知识引擎脚本": os.path.expanduser("~/.hermes/knowledge-engine/scripts"),
    "集成脚本": os.path.expanduser("~/.hermes/scripts/ke_integration.py"),
    "身份配置": os.path.expanduser("~/.hermes/SOUL.md"),
}


def export_backup(output_path):
    """只导出核心记忆和知识"""
    files_to_pack = []
    missing = []
    
    for name, path in CORE_FILES.items():
        if os.path.exists(path):
            files_to_pack.append(path)
        else:
            missing.append(f"  ⚠️ {name}: 不存在 ({path})")
    
    if not files_to_pack:
        print("❌ 没有找到任何可导出的数据")
        return False
    
    # 写入 manifest
    manifest = {
        "exported_at": datetime.now().isoformat(),
        "name": "隐光记忆与知识",
        "files": {name: path for name, path in CORE_FILES.items() if os.path.exists(path)},
    }
    manifest_path = "/tmp/ke_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    # 打包
    with tarfile.open(output_path, "w:gz") as tar:
        for path in files_to_pack:
            arcname = os.path.relpath(path, os.path.expanduser("~/.hermes"))
            tar.add(path, arcname=arcname)
        tar.add(manifest_path, arcname="manifest.json")
    
    os.remove(manifest_path)
    
    size = os.path.getsize(output_path)
    print(f"✅ 导出完成: {output_path}")
    print(f"   大小: {size/1024:.1f}KB")
    print(f"   内容: {len(files_to_pack)} 项核心数据")
    for m in missing:
        print(m)
    return True


def import_backup(input_path):
    """从备份恢复核心记忆和知识"""
    if not os.path.exists(input_path):
        print(f"❌ 备份文件不存在: {input_path}")
        return False
    
    print(f"📦 正在从 {input_path} 恢复...")
    
    with tarfile.open(input_path, "r:gz") as tar:
        # 先读 manifest
        manifest_file = tar.extractfile("manifest.json")
        if not manifest_file:
            print("❌ 备份文件缺少 manifest")
            return False
        manifest = json.loads(manifest_file.read())
        
        print(f"   导出于: {manifest.get('exported_at', '未知')}")
        
        # 备份当前状态（以防回滚）
        bak_dir = f"/tmp/ke_rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(bak_dir, exist_ok=True)
        for name, rel_path in manifest.get("files", {}).items():
            abs_path = os.path.expanduser(f"~/.hermes/{rel_path}")
            if os.path.exists(abs_path):
                bak_path = os.path.join(bak_dir, os.path.basename(rel_path.rstrip('/')))
                shutil.copytree(abs_path, bak_path) if os.path.isdir(abs_path) else shutil.copy2(abs_path, bak_path)
        
        # 解压到目标位置
        tar.extractall(path=os.path.expanduser("~/.hermes"))
        
        print(f"✅ 恢复完成")
        print(f"   回滚备份: {bak_dir}")
        print(f"   内容:")
        for name, rel_path in manifest.get("files", {}).items():
            print(f"     ✅ {name}")
    
    return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法:")
        print("  python3 migrate.py export /path/to/backup.tar.gz")
        print("  python3 migrate.py import /path/to/backup.tar.gz")
        sys.exit(1)
    
    action = sys.argv[1]
    path = sys.argv[2]
    
    if action == "export":
        export_backup(path)
    elif action == "import":
        import_backup(path)
    else:
        print(f"❌ 未知操作: {action}")
        sys.exit(1)
