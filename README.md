# health-management

健康管理网站。三个服务：

- `User-management-service`（另一个仓库，端口 8000）：用户姓名、邮箱、登录
- `health-service`（端口 8001）：健康档案、每日打卡、参考标准、卡路里计算器
- `health-web`（端口 8777）：网页前端

详细的开发计划见 `docs/项目计划书.md`（按 PR-01 到 PR-11 顺序开发，每个 PR 一个分支；睡眠功能是 PR-08.5）。

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

## 功能

- 注册 / 登录 / 编辑 / 删除档案（睡眠时长选填）
- 参考标准：热量、运动、BMI、血糖血压胆固醇、睡眠（7–9 小时，页面小字标注依据）
- 每日打卡（体重、运动、热量、睡眠）并打分：超额 / 完成 / 未完成
- 周期报告：体重、运动、热量、睡眠四张曲线图和汇总
- 卡路里计算器：输入食物和克数，一键填入今天打卡

## 演示数据和验收

```bash
# 两个后端都开着时
.venv/bin/python scripts/seed_demo.py       # 造一个有 30 天数据的演示用户，打印登录邮箱
.venv/bin/python scripts/smoke_test.py      # 端到端冒烟测试，退出码 0 = 全部通过
```

升级提示：`create_all` 只建新表、不改旧表。如果本地 `health.db` 是 PR-08 之前建的，
请删掉 `health-service/health.db` 再启动（开发期数据可以丢）。

## 安全说明和免责声明

- 登录只输邮箱、没有密码，**不安全，不要放真实健康数据**。
- 所有页面底部都有「仅供学习参考，不能替代医生诊断」。
- 睡眠标准依据：AASM/SRS 2015 共识（成人每晚至少 7 小时）、NSF 2015 睡眠时长建议。
