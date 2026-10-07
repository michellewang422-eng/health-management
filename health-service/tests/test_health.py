"""PR-01 的测试：服务活着吗？路由和 CORS 白名单对不对？

TestClient 的作用：不用真的启动 uvicorn、不占端口，它在内存里直接把请求交给
app 处理，所以测试跑得非常快（毫秒级）。你在浏览器/curl 里看到的状态码和响应体，
和这里 resp.status_code / resp.json() 拿到的是同一个东西。
"""

import unittest

from fastapi.testclient import TestClient

from app.main import app


class HealthTestCase(unittest.TestCase):
    # setUp 在每个 test_ 方法执行前自动跑一次
    def setUp(self):
        self.client = TestClient(app)

    # ---- T1-1 正常路径 ----
    def test_health_returns_ok(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})

    # ---- T1-2 错误输入：地址写错 ----
    def test_unknown_path_returns_404(self):
        resp = self.client.get("/no-such-path")
        self.assertEqual(resp.status_code, 404)

    # ---- T1-3 错误输入：方法用错 ----
    # /health 只登记了 GET，用 POST 打它 → 405 Method Not Allowed
    def test_post_health_returns_405(self):
        resp = self.client.post("/health")
        self.assertEqual(resp.status_code, 405)

    # ---- T1-4 白名单内的源：响应头里要回显这个 Origin ----
    # 浏览器拿到这个响应头，才允许网页里的 JS 读取响应内容
    def test_allowed_origin_gets_cors_header(self):
        resp = self.client.get("/health", headers={"Origin": "http://localhost:8777"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.headers.get("access-control-allow-origin"),
            "http://localhost:8777",
        )

    # ---- T1-5 白名单外的源：不能有这个响应头 ----
    # 注意：请求其实还是被处理了（返回 200），是浏览器看到"没有许可头"后
    # 拒绝把结果交给网页的 JS。CORS 是浏览器端的限制，不是服务端的鉴权。
    def test_disallowed_origin_has_no_cors_header(self):
        resp = self.client.get("/health", headers={"Origin": "http://evil.example"})
        self.assertIsNone(resp.headers.get("access-control-allow-origin"))
