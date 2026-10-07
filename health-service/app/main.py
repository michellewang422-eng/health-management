from fastapi import FastAPI
# CORSMiddleware：控制"允许哪些来源的网页调用这个后端"
from fastapi.middleware.cors import CORSMiddleware

# title 会显示在自动生成的文档页 /docs 顶部
app = FastAPI(title="health-service")

# ---- CORS ----
# "源" = 协议 + 域名 + 端口，三者完全一样才算同源。
# 我们的网页将从 http://127.0.0.1:8777 打开，后端在 http://127.0.0.1:8001，
# 端口不同就是不同源，浏览器默认禁止网页读取另一个源的响应。
# 下面这份白名单和 user-service 保持一致，这样同一个网页能同时调用两个后端。
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8777",
        "http://127.0.0.1:8777",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_methods=["*"],   # 允许 GET/POST/PUT/DELETE/OPTIONS 等所有方法
    allow_headers=["*"],   # 允许所有请求头（比如 Content-Type）
)


# @app.get("/health")：把下面这个函数登记成"收到 GET /health 请求时执行的代码"
# 返回的字典会被 FastAPI 自动转成 JSON，状态码默认 200
@app.get("/health")
def health():
    return {"status": "ok"}
