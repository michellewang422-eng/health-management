"""PR-06 的测试：浏览器里的网页能不能跨端口调用我们的接口？

CORS 只对"浏览器里的网页 JS"生效：浏览器发跨源请求会带上 Origin 头，并检查响应里
有没有对应的 Access-Control-Allow-Origin。对 PUT / DELETE 这类"不简单"的请求，
浏览器会先发一个 OPTIONS 请求（叫"预检"）问服务器："我能用 PUT 吗？"，
得到许可之后才发真正的请求。这里用 TestClient 手动带上 Origin 头来模拟浏览器。
"""

import unittest

from fastapi.testclient import TestClient

from app.main import app

WEB_ORIGIN = "http://127.0.0.1:8777"


class CORSPreflightTestCase(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def preflight(self, method, origin=WEB_ORIGIN):
        return self.client.options(
            "/profiles/1",
            headers={"Origin": origin, "Access-Control-Request-Method": method},
        )

    # ---- T6-1 PUT 的预检：放行，并回显 Origin ----
    def test_preflight_for_put_is_allowed(self):
        resp = self.preflight("PUT")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("access-control-allow-origin"), WEB_ORIGIN)

    # ---- T6-2 DELETE 的预检：放行 ----
    def test_preflight_for_delete_is_allowed(self):
        resp = self.preflight("DELETE")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("DELETE", resp.headers.get("access-control-allow-methods", ""))

    # ---- T6-3 白名单外的源：不能有许可头，浏览器就会拒绝这个请求 ----
    def test_preflight_from_unknown_origin_is_not_allowed(self):
        resp = self.preflight("PUT", origin="http://evil.example")
        self.assertIsNone(resp.headers.get("access-control-allow-origin"))

    # ---- 非浏览器的 client（curl / 其它 server）不带 Origin，照常工作 ----
    def test_request_without_origin_still_works(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
