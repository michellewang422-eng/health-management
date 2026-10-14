# health-management

一个中文的个人健康管理网站：建立健康档案，每天记录体重、运动、摄入热量和睡眠，系统按参考标准自动打分，并用曲线图展示一个周期内的变化；还带一个卡路里计算器。

> 这是学习项目。登录只输邮箱、没有密码，**不要放真实健康数据**；页面内容仅供学习参考，不能替代医生诊断。

## 功能

| 功能 | 说明 |
| --- | --- |
| 注册 / 登录 / 删除账号 | 姓名 + 邮箱注册，邮箱登录（无密码） |
| 健康档案 | 年龄、性别、身高、体重、目标（减重 / 维持 / 增重）；血糖、血压、胆固醇、平时睡眠为选填 |
| 参考标准 | 自动算出 BMI、健康体重范围、BMR、每日热量目标、每日运动目标、睡眠区间，以及血糖 / 血压 / 胆固醇 / 睡眠的基线评估 |
| 每日打卡 | 体重、运动分钟和强度、摄入热量、昨晚睡眠；每项打「超额 / 完成 / 未完成」，同一天再保存会覆盖 |
| 周期报告 | 体重、运动、热量、睡眠四张曲线图（带目标线）和汇总 |
| 卡路里计算器 | 输入食物和克数得到总热量；「鸡肉」这类通用词有多个候选时让你选；可一键填入今天的打卡 |

## 架构

三个独立的服务，通过 HTTP 通信：

```
浏览器 ── health-web (8777，静态页面)
            ├── User-management-service (8000)  用户姓名、邮箱、登录（另一个仓库）
            └── health-service          (8001)  档案、打卡、标准、报告、计算器（本仓库，FastAPI + SQLite）
                      └── 创建档案时调用 GET /users/{id} 确认用户存在
```

```
health-service/   FastAPI 后端
  app/routers/    profiles（档案、标准）、logs（每日打卡）、report（周期报告）、calories（食物、计算）
  app/services/   standards（参考标准）、scoring（打分）、report（报告汇总）、calories（食物匹配）、user_client
  app/models.py   SQLAlchemy 表：health_profiles、daily_logs、food_items
  app/seed_foods.py  内置食物及每 100 克热量
  tests/          单元测试 + 接口测试（内存 SQLite，不需要启动任何服务）
health-web/       纯 HTML/JS 前端（login、register、profile、dashboard、report、calories）
scripts/          seed_demo.py（演示数据）、smoke_test.py（端到端冒烟测试）
docs/             项目计划书
```

## 怎么运行

### 准备

- Python 3.10 或更新
- `User-management-service`：另一个仓库，负责用户注册和登录，需要先在它自己的仓库里按它的说明安装

在本仓库根目录创建虚拟环境并安装依赖：

```bash
python3 -m venv .venv
.venv/bin/pip install -r health-service/requirements.txt
```

### 启动（三个终端）

```bash
# 终端 1：User-management-service（端口 8000），在它自己的仓库里
uvicorn app.main:app --reload --port 8000

# 终端 2：health-service（端口 8001），在本仓库根目录
cd health-service && ../.venv/bin/uvicorn app.main:app --reload --port 8001

# 终端 3：网页（端口 8777），不缓存，改了页面刷新就生效
cd health-web && python3 serve.py 8777
```

浏览器打开 <http://localhost:8777/login.html>。接口文档（自动生成）在 <http://127.0.0.1:8001/docs>。

使用顺序：注册 → 自动建档 → 首页查看参考标准、每日打卡 → 报告页看曲线图 → 计算器算热量。

### 端口和跨域

前端固定调用 `http://127.0.0.1:8000`（用户服务）和 `http://127.0.0.1:8001`（health-service），地址写在 `health-web/api.js` 顶部。health-service 的 CORS 白名单只允许 `localhost` / `127.0.0.1` 的 8777 和 5500 端口打开的网页，改前端端口需要同步改 `app/main.py`。

User-management-service 自带的网页如果也跑在 8777 端口，两个网页会共用同一份 `localStorage`（都用 `currentUser` 这个键）；同时开发时请用不同端口，或者一个用 `localhost`、一个用 `127.0.0.1` 打开。

### 数据库

SQLite，文件是 `health-service/health.db`（已被 `.gitignore` 忽略），首次启动自动创建。`create_all` 只建新表、不改旧表：如果升级后报缺列（例如旧库没有 `sleep_hours`），删掉 `health.db` 重新启动即可（开发期数据可以丢）。内置食物在每次启动时幂等写入。

## 测试

```bash
# 单元测试和接口测试：不需要启动任何服务
cd health-service && ../.venv/bin/python -m unittest discover -v

# 演示数据：两个后端都开着时，造一个有 30 天数据的演示用户，打印登录邮箱
.venv/bin/python scripts/seed_demo.py

# 端到端冒烟测试：真实调用两个后端，走完整流程并清理数据，退出码 0 即通过
.venv/bin/python scripts/smoke_test.py
```

## 接口一览（health-service）

| 方法和路径 | 作用 |
| --- | --- |
| `GET /health` | 服务存活检查 |
| `POST /profiles` | 创建档案（用户必须已在用户服务注册；已建过返回 409） |
| `GET` / `PUT` / `DELETE /profiles/{user_id}` | 查询 / 修改 / 删除档案（删除会连带删除该用户的日志） |
| `GET /profiles/{user_id}/standards` | 参考标准和基线评估 |
| `PUT /profiles/{user_id}/logs/{YYYY-MM-DD}` | 保存某天打卡（同一天覆盖，不能是未来日期） |
| `GET /profiles/{user_id}/logs?from=&to=` | 打卡列表（含得分），按日期升序 |
| `DELETE /profiles/{user_id}/logs/{YYYY-MM-DD}` | 删除某天打卡 |
| `GET /profiles/{user_id}/report` | 周期报告：序列数据和汇总 |
| `GET /foods?q=` | 搜索内置食物 |
| `POST /calories/calculate` | 计算一组「食物 + 克数」的总热量 |

## 评分规则

打分和标准都是纯函数，**不存库、每次读取重新计算**，所以改了档案（年龄、目标等）后历史记录的得分会自动更新。

- 每项结果：`exceeded`（超额）/ `met`（完成）/ `missed`（未完成）；没填的项不计入得分分母。
- **运动**：按强度折算（低 ×0.5、中 ×1、高 ×2）后与目标比较；目标是 30 分钟，减重目标是 45 分钟。
- **热量**：目标 = BMR × 1.375（轻度活动），减重 −500、增重 +300，女性不低于 1200、男性不低于 1500；摄入超过目标 110% 才算超标（增重目标下超标算好事）。
- **体重**：按目标从起始日期线性推算每天的期望体重，减重：比期望值低 0.5 kg 以上算超额、不高于期望 0.3 kg 算完成；增重相反；维持：偏差在 ±1.0 kg 内算完成。
- **睡眠**：18–64 岁 7–9 小时，65 岁及以上 7–8 小时；低于下限「偏短」，区间内「完成」，高于上限「偏长」（提醒色，不算好事）。依据：AASM/SRS 2015 共识（成人每晚至少 7 小时）、NSF 2015 睡眠时长建议，页面以小字标注并附链接。

## 如何添加内置食物

在 `health-service/app/seed_foods.py` 的 `FOODS` 列表里加一行（名称、别名、每 100 克热量），重启 health-service 即可，不需要迁移数据。

## 开发计划

详细的开发计划和决策记录见 [`docs/项目计划书.md`](docs/%E9%A1%B9%E7%9B%AE%E8%AE%A1%E5%88%92%E4%B9%A6.md)，按 PR-01 到 PR-11 的顺序开发，睡眠功能是 PR-08.5。

## 安全说明和免责声明

- 登录只输邮箱、没有密码、没有令牌，**不安全**，仅用于本地学习。
- 所有页面底部都有「仅供学习参考，不能替代医生诊断」。
- 参考标准是通用估算，不是个性化医疗建议。
