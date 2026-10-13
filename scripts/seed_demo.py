"""造一个演示用户：周期从 29 天前开始、目标减重，并生成 30 天带随机波动的打卡数据。

用法（两个后端都要开着）：
    .venv/bin/python scripts/seed_demo.py
    .venv/bin/python scripts/seed_demo.py --email demo@example.com
"""

import argparse
import random
import time
from datetime import date, timedelta

import httpx

USER_API = "http://127.0.0.1:8000"
HEALTH_API = "http://127.0.0.1:8001"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=f"demo{int(time.time())}@example.com")
    args = parser.parse_args()
    rng = random.Random(42)            # 固定种子：每次生成的数据一样，方便对照

    user = httpx.post(f"{USER_API}/users", timeout=5, json={
        "email": args.email, "first_name": "Demo", "last_name": "User"})
    user.raise_for_status()
    uid = user.json()["id"]

    start = date.today() - timedelta(days=29)
    httpx.post(f"{HEALTH_API}/profiles", timeout=5, json={
        "user_id": uid, "age": 35, "gender": "female", "height_cm": 165, "weight_kg": 60,
        "sleep_hours": 7.0, "goal_type": "lose_weight", "cycle_days": 30,
        "start_date": start.isoformat()}).raise_for_status()

    for i in range(30):
        day = start + timedelta(days=i)
        if rng.random() < 0.1:         # 大约 10% 的日子忘了打卡
            continue
        body = {
            "weight_kg": round(60 - 0.07 * i + rng.uniform(-0.4, 0.4), 1),
            "exercise_minutes": rng.choice([20, 30, 45, 50, 60]),
            "exercise_intensity": rng.choice(["low", "moderate", "high"]),
            "calories_in": rng.randint(1100, 1500),
            "sleep_hours": round(rng.uniform(5.5, 9.5) * 4) / 4,
        }
        httpx.put(f"{HEALTH_API}/profiles/{uid}/logs/{day.isoformat()}",
                  timeout=5, json=body).raise_for_status()

    print(f"完成：user_id={uid}，用邮箱 {args.email} 登录，打开「周期报告」查看。")


if __name__ == "__main__":
    main()
