# health-management

健康管理网站。三个服务：

- `User-management-service`（另一个仓库，端口 8000）：用户姓名、邮箱、登录
- `health-service`（端口 8001）：健康档案、每日打卡、参考标准、卡路里计算器
- `health-web`（端口 8777）：网页前端

详细的开发计划见 `docs/项目计划书.md`（按 PR-01 到 PR-11 顺序开发，每个 PR 一个分支）。

## 怎么启动（三个终端）

```bash
# 终端 1：User-management-service（端口 8000），在它自己的仓库里
uvicorn app.main:app --reload --port 8000

# 终端 2：health-service（端口 8001）
cd health-service && ../.venv/bin/uvicorn app.main:app --reload --port 8001

# 终端 3：网页（端口 8777）
cd health-web && python3 -m http.server 8777
```

浏览器打开 <http://localhost:8777/login.html>。

注意：User-management-service 自带的网页如果也跑在 8777 端口，两个网页会共用同一份 `localStorage`（都用 `currentUser` 这个键）。同时开发时请用不同端口，或者一个用 `localhost`、一个用 `127.0.0.1` 打开。

跑测试：`cd health-service && ../.venv/bin/python -m unittest discover -v`
