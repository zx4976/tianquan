#!/usr/bin/env python3
"""
cron 包装器 — 每日知识引擎备份
由 Hermes cron 调度，输出直接报告状态
"""
import subprocess
import sys
import os
from datetime import datetime

BACKUP_SCRIPT = "/root/projects/knowledge-engine/scripts/backup.sh"

try:
    result = subprocess.run(
        ["bash", BACKUP_SCRIPT],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode == 0:
        # 提取备份文件名和大小
        lines = result.stdout.strip().split('\n')
        print(f"✅ 知识引擎备份成功 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        for line in lines:
            if '文件:' in line or '大小:' in line or '位置:' in line:
                print(f"  {line.strip()}")
    else:
        print(f"❌ 备份失败 (exit={result.returncode})")
        print(result.stderr[:500])

except subprocess.TimeoutExpired:
    print(f"❌ 备份超时 (>120s)")
except Exception as e:
    print(f"❌ 备份异常: {e}")
