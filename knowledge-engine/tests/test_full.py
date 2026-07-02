#!/usr/bin/env python3
"""
完整验收测试 — 多语言 + 持久化 + 备份
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.book_pipeline import BookPipeline, classify_book
from src.config import get_stats, ensure_dirs
from src.tokenizer import tokenize, detect_lang
import json, time, subprocess

print("=" * 60)
print("完整验收测试")
print("=" * 60)

pass_count = 0
fail_count = 0

def check(name, ok):
    global pass_count, fail_count
    if ok:
        print(f"  ✅ {name}")
        pass_count += 1
    else:
        print(f"  ❌ {name}")
        fail_count += 1

# 1. 分词器
print("\n1️⃣ 分词器测试")
check("中文分词", '编程语言' in tokenize('Python是一种编程语言'))
check("日文分词", 'プログラミング' in tokenize('Pythonはプログラミング言語です'))
check("韩文分词", '프로그래밍' in tokenize('Python은 프로그래밍 언어입니다'))
check("希伯来文分词", 'תכנות' in tokenize('Python היא שפת תכנות'))
check("英文分词", 'programming' in tokenize('Python programming language'))
check("语言检测(zh)", detect_lang('Python是一种编程语言') == 'zh')
check("语言检测(ja)", detect_lang('Pythonはプログラミング言語') == 'ja')
check("语言检测(ko)", detect_lang('Python은 프로그래밍 언어') == 'ko')
check("语言检测(he)", detect_lang('Python היא שפת תכנות') == 'he')
check("语言检测(en)", detect_lang('Python programming language') == 'en')

# 2. 全流程
print("\n2️⃣ 全流程测试")
with BookPipeline(persistent=True) as pipe:
    books = [
        {'book_id':'zh1','title':'流畅的Python','author':'Luciano Ramalho','category':'编程',
         'body':'Python是一种优雅的编程语言，支持面向对象和函数式编程，包括异步编程、协程等高级特性。',
         'tags':'Python 编程 异步'},
        {'book_id':'ja1','title':'Python入門','author':'B','category':'プログラミング',
         'body':'Pythonはエレガントなプログラミング言語で、オブジェクト指向や関数型プログラミングをサポートしています。',
         'tags':'Python プログラミング'},
        {'book_id':'en1','title':'Fluent Python','author':'Luciano Ramalho','category':'Programming',
         'body':'Python is an elegant language that supports object-oriented and functional programming.',
         'tags':'Python programming'},
    ]
    
    for b in books:
        r = pipe.process_book(b)
        check(f"分类: {b['title']}", r['category'] in ('编程语言', 'Programming'))
    
    # 重建 LSI
    pipe.rebuild_lsi(n_components=2)
    check("LSI 重建", pipe.lsi is not None and pipe.lsi.is_built)
    
    # 语言感知搜索
    results_zh = pipe.search('Python 异步编程', limit=3)
    check("中文搜索优先同语言", len(results_zh) > 0 and results_zh[0].get('lang') == 'zh')
    
    results_en = pipe.search('Python programming', limit=3)
    check("英文搜索优先同语言", len(results_en) > 0 and results_en[0].get('lang') == 'en')
    
    results_ja = pipe.search('プログラミング', limit=3)
    check("日文搜索优先同语言", len(results_ja) > 0 and results_ja[0].get('lang') == 'ja')

# 3. 持久化
print("\n3️⃣ 持久化测试")
with BookPipeline(persistent=True) as pipe2:
    results = pipe2.search('Python', limit=3)
    check("持久化数据可检索", len(results) >= 3)
    langs = {r.get('lang', '') for r in results}
    check("语言字段已持久化", langs == {'zh', 'ja', 'en'})

# 4. 数据统计
print("\n4️⃣ 数据统计")
stats = get_stats()
check(f"数据目录存在: {stats['data_root']}", os.path.exists(stats['data_root']))
check(f"数据文件 > 0: {stats['total_files']}", stats['total_files'] > 0)

# 5. 备份
print("\n5️⃣ 备份测试")
backup_script = os.path.expanduser("~/.hermes/knowledge-engine/scripts/backup.sh")
result = subprocess.run(["bash", backup_script], capture_output=True, text=True, timeout=30)
check("备份脚本执行成功", result.returncode == 0)
check("备份输出包含校验通过", "校验通过" in result.stdout)

# 统计备份文件
backup_dir = "/mnt/天权智库/天权智库/工作文档/知识引擎备份"
backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.tar.gz')]
check("备份文件已生成", len(backup_files) > 0)

# 6. 自动分类
print("\n6️⃣ 自动分类测试")
for title, body, expected in [
    ('流畅的Python', 'Python 编程 异步', '编程语言'),
    ('深入理解计算机系统', '计算机 系统 内存 架构', '计算机科学'),
    ('算法导论', '算法 排序 数据结构', '计算机科学'),
    ('深度学习入门', '神经网络 深度学习 AI', 'AI机器学习'),
]:
    cat, sub, score = classify_book(title, body, '')
    check(f"分类: {title[:15]} → {cat}", cat == expected)

# 汇总
print(f"\n{'='*60}")
print(f"测试结果: {pass_count} 通过, {fail_count} 失败, {pass_count+fail_count} 总计")
if fail_count == 0:
    print("✅ 全部通过")
else:
    print(f"❌ 有 {fail_count} 项失败")
print(f"{'='*60}")
