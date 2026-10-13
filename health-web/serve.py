"""开发用的静态网页服务器：和 `python3 -m http.server` 一样，但告诉浏览器不要缓存。

普通的 http.server 会让浏览器按"上次修改时间"猜测缓存，改了 JS 刷新后还是旧页面。
用法：cd health-web && python3 serve.py 8777
"""
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8777
    ThreadingHTTPServer(("127.0.0.1", port), NoCacheHandler).serve_forever()
