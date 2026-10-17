"""端到端冒烟测试：真实调用两个后端，走一遍「注册 → 建档 → 标准 → 打卡 → 报告 → 计算器 → 删除」。

用法（User-management-service 和 health-service 都要开着）：
    .venv/bin/python scripts/smoke_test.py
每一步用 assert 检查状态码和关键字段；最后清理自己创建的数据。全部通过时退出码为 0。
"""

import time
from datetime import date, timedelta

import httpx

USER_API = "http://127.0.0.1:8000"
HEALTH_API = "http://127.0.0.1:8001"


def step(name):
    print(f"✓ {name}")


def main():
    email = f"smoke{int(time.time())}@example.com"
    today = date.today()
    start = today - timedelta(days=2)
    uid = None
    with httpx.Client(timeout=5) as c:
        try:
            r = c.post(f"{USER_API}/users", json={"email": email, "first_name": "Smoke", "last_name": "Test"})
            if r.is_success:
                uid = r.json()["id"]          # 先记下 id：后面任何一步失败，finally 都能清理
            # 用户服务创建成功返回 200（不是 201），所以两个都接受
            assert r.status_code in (200, 201), r.text
            step("注册用户")

            r = c.post(f"{USER_API}/auth/login", json={"email": email})
            assert r.status_code == 200 and r.json()["id"] == uid, r.text
            step("登录")

            r = c.post(f"{HEALTH_API}/profiles", json={
                "user_id": uid, "age": 35, "gender": "female", "height_cm": 165, "weight_kg": 60,
                "sleep_hours": 7.0, "goal_type": "lose_weight", "start_date": start.isoformat()})
            assert r.status_code == 201, r.text
            assert r.json()["cycle_days"] == 30
            step("建档（周期默认 30 天）")

            r = c.get(f"{HEALTH_API}/profiles/{uid}/standards")
            s = r.json()
            assert r.status_code == 200 and s["daily_calories"] == 1280, s
            assert s["exercise"]["daily_effective_minutes"] == 45
            assert (s["sleep"]["min_hours"], s["sleep"]["max_hours"]) == (7, 9)
            assert s["sleep"]["sources"], "缺少睡眠依据"
            step("参考标准（1280 kcal、45 分钟、睡眠 7–9 小时）")

            days = [
                (start, dict(weight_kg=60.0, exercise_minutes=50, exercise_intensity="moderate",
                             calories_in=1300, sleep_hours=5.5), 3, 4),
                (start + timedelta(days=1), dict(weight_kg=60.2, exercise_minutes=60,
                             exercise_intensity="high", calories_in=1500, sleep_hours=7.5), 3, 4),
                (today, dict(weight_kg=59.2, exercise_minutes=20, exercise_intensity="low",
                             calories_in=1100, sleep_hours=9.5), 1, 4),
            ]
            for day, body, points, scored in days:
                r = c.put(f"{HEALTH_API}/profiles/{uid}/logs/{day.isoformat()}", json=body)
                assert r.status_code == 200, r.text
                assert (r.json()["points"], r.json()["scored"]) == (points, scored), r.json()
            step("3 天打卡（得分 3/4、3/4、1/4）")

            r = c.get(f"{HEALTH_API}/profiles/{uid}/report")
            rep = r.json()
            assert r.status_code == 200 and len(rep["series"]) == 30
            sm = rep["summary"]
            assert (sm["logged_days"], sm["points"], sm["scored"]) == (3, 7, 12), sm
            assert sm["avg_sleep_hours"] == 7.5 and sm["avg_calories"] == 1300, sm
            step("周期报告（含睡眠）")

            r = c.post(f"{HEALTH_API}/calories/calculate", json={"items": [
                {"name": "白饭", "grams": 150}, {"name": "水煮蛋", "grams": 120}]})
            assert r.status_code == 200 and r.json()["total_kcal"] == 381.0, r.text
            step("卡路里计算器（381 kcal）")
        finally:
            # 清理：先删档案再删用户（顺序不能倒）
            if uid is not None:
                c.delete(f"{HEALTH_API}/profiles/{uid}")
                c.delete(f"{USER_API}/users/{uid}")
                step("清理数据")
    print("全部通过")


if __name__ == "__main__":
    main()
