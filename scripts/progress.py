#!/usr/bin/env python3
"""
导入进度查询 — 配合 background 导入使用

用法:
  python3 scripts/progress.py          # 查看当前进度
  python3 scripts/progress.py --watch  # 每3秒刷新一次
"""
import sys, os, json, time, subprocess

STATUS_FILE = "/tmp/import_status.json"


def read_status():
    if not os.path.exists(STATUS_FILE):
        return None
    try:
        with open(STATUS_FILE, 'r') as f:
            return json.load(f)
    except:
        return None


def show_status(status):
    if not status:
        print("📊 没有正在运行的导入任务")
        return
    
    phase = status.get('phase', '')
    done = status.get('done', 0)
    total = status.get('total', 0)
    errors = status.get('errors', 0)
    elapsed = status.get('elapsed', 0)
    
    if total > 0:
        pct = done / total * 100
        bar = '█' * int(pct // 5) + '░' * (20 - int(pct // 5))
        speed = status.get('speed', 0)
        eta = status.get('eta', 0)
        
        print(f"📊 导入进度")
        print(f"  阶段: {phase}")
        print(f"  进度: |{bar}| {done}/{total} ({pct:.0f}%)")
        print(f"  速度: {speed:.1f}本/秒  耗时: {elapsed:.0f}s  ETA: {eta:.0f}s")
        if errors:
            print(f"  ❌ 错误: {errors} 本")
        if status.get('current_book'):
            print(f"  当前: {status['current_book'][:50]}")
    else:
        print(f"  阶段: {phase} ({done}/{total})")
    
    if status.get('done_phases'):
        for p in status['done_phases']:
            print(f"  ✅ {p}")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--watch':
        print("按 Ctrl+C 停止监控")
        try:
            while True:
                status = read_status()
                os.system('clear' if os.name == 'posix' else 'cls')
                show_status(status)
                time.sleep(3)
        except KeyboardInterrupt:
            print("\n监控已停止")
    else:
        status = read_status()
        show_status(status)


if __name__ == '__main__':
    main()
