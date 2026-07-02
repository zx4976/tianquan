#!/usr/bin/env python3
"""
知识引擎 REST API — 基于 Python 内置 http.server，零额外依赖
"""
import os
import sys
import json
import time
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# 确保能找到 src
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.book_pipeline import BookPipeline, classify_book
from src.config import get_stats, ensure_dirs


API_PORT = int(os.environ.get("KE_API_PORT", "8765"))
API_HOST = os.environ.get("KE_API_HOST", "0.0.0.0")


class KEHandler(BaseHTTPRequestHandler):
    
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
    
    def _send_error(self, msg, status=400):
        self._send_json({"error": msg}, status)
    
    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw": body}
    
    def do_OPTIONS(self):
        """CORS preflight"""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = urllib.parse.parse_qs(parsed.query)
        
        def p(name, default=None):
            vals = params.get(name, [])
            return vals[0] if vals else default
        
        try:
            # GET /api/search?q=xxx&limit=10
            if path == "/api/search":
                q = p("q")
                if not q:
                    return self._send_error("缺少参数 q (搜索关键词)")
                limit = int(p("limit", "10"))
                with BookPipeline(persistent=True) as pipe:
                    results = pipe.search(q, limit=limit)
                return self._send_json({
                    "query": q,
                    "count": len(results),
                    "results": results,
                })
            
            # GET /api/stats
            elif path == "/api/stats":
                stats = get_stats()
                # 估算容量
                mb_per_book = stats["total_size_mb"] / max(stats.get("book_count", 1), 1)
                return self._send_json({
                    **stats,
                    "estimated_mb_per_book": round(mb_per_book, 3),
                    "notes_vault": "/mnt/天权智库/天权智库/煦林笔记",
                })
            
            # GET /api/classify?title=xxx&body=xxx
            elif path == "/api/classify":
                title = p("title", "")
                body = p("body", "")
                if not title:
                    return self._send_error("缺少参数 title")
                cat, sub, score = classify_book(title, body, p("tags", ""))
                return self._send_json({
                    "title": title,
                    "category": cat,
                    "subcategory": sub,
                    "score": score,
                })
            
            # GET /api/understanding?book=xxx&limit=20
            elif path == "/api/understanding":
                from src.understanding import Understanding
                u = Understanding()
                book_id = p("book", "")
                limit = int(p("limit", "20"))
                if book_id:
                    comps = u.get_comprehensions(book_id)
                    concepts = u.get_concepts_for_book(book_id)
                    bk = u.get_book(book_id)
                    return self._send_json({
                        "book": bk,
                        "comprehensions": comps,
                        "concepts": concepts,
                        "total": len(comps),
                    })
                else:
                    stats = u.stats()
                    return self._send_json({
                        "stats": stats,
                        "books_registered": stats.get("books", 0),
                        "total_comprehensions": stats.get("理解条目", 0),
                        "total_concepts": stats.get("概念", 0),
                        "cross_links": stats.get("跨书关联", 0),
                    })
            
            # GET /api/health
            elif path == "/api/health":
                return self._send_json({
                    "status": "ok",
                    "version": "0.2",
                    "time": datetime.now().isoformat(),
                })
            
            # GET /api/synthesize?q=xxx
            elif path == "/api/synthesize":
                q = p("q")
                if not q:
                    return self._send_error("缺少参数 q")
                from src.brain_layer import synthesize
                result = synthesize(q)
                return self._send_json(result)
            
            # GET /api/gap?q=xxx
            elif path == "/api/gap":
                q = p("q")
                if not q:
                    return self._send_error("缺少参数 q")
                from src.brain_layer import gap_analysis
                result = gap_analysis(q)
                return self._send_json(result)
            
            else:
                self._send_error(f"未知路径: {path}", 404)
        
        except Exception as e:
            self._send_error(str(e), 500)
    
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = self._read_body()
        
        try:
            # POST /api/books — 导入一本书
            if path == "/api/books":
                required = ["title", "body"]
                for field in required:
                    if field not in body:
                        return self._send_error(f"缺少必填字段: {field}")
                
                book = {
                    "id": body.get("id", f"api_{int(time.time())}"),
                    "title": body["title"],
                    "author": body.get("author", "未知"),
                    "body": body["body"][:50000],
                    "summary": body.get("summary", body["body"][:200]),
                    "tags": body.get("tags", ""),
                }
                concepts = body.get("concepts", [])
                highlights = body.get("highlights", [])
                
                with BookPipeline(persistent=True) as pipe:
                    result = pipe.process_book(book, concepts, highlights)
                    if body.get("rebuild_lsi", True):
                        pipe.rebuild_lsi()
                
                return self._send_json({
                    "status": "imported",
                    "book": result,
                }, 201)
            
            # POST /api/backup — 触发备份
            elif path == "/api/backup":
                import subprocess
                result = subprocess.run(
                    ["bash", os.path.join(os.path.dirname(__file__), "scripts", "backup.sh")],
                    capture_output=True, text=True, timeout=120
                )
                return self._send_json({
                    "status": "success" if result.returncode == 0 else "failed",
                    "output": result.stdout.strip().split('\n')[-3:],
                })
            
            else:
                self._send_error(f"未知路径: {path}", 404)
        
        except Exception as e:
            self._send_error(str(e), 500)
    
    def log_message(self, format, *args):
        """自定义日志格式"""
        sys.stderr.write(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]} {args[1]} {args[2]}\n")


def main():
    ensure_dirs()
    server = HTTPServer((API_HOST, API_PORT), KEHandler)
    print(f"\n{'='*50}")
    print(f"  知识引擎 API 服务")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")
    print(f"  本地:  http://127.0.0.1:{API_PORT}")
    print(f"  局域网: http://192.168.0.200:{API_PORT}  (从 Windows 访问)")
    print(f"  Endpoints:")
    print(f"    GET  /api/health           — 健康检查")
    print(f"    GET  /api/stats            — 数据统计")
    print(f"    GET  /api/search?q=xxx     — 搜索")
    print(f"    GET  /api/classify?title=x — 分类测试")
    print(f"    POST /api/books            — 导入书籍 (JSON body)")
    print(f"    POST /api/backup           — 触发备份")
    print(f"{'='*50}\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.server_close()


if __name__ == '__main__':
    main()
