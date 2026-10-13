"""PR-05 的测试（下）：每日记录接口，从 HTTP 请求一直到数据库。

先用 add_profile 直接往数据库放一条档案（不经过 POST，也就不需要假的用户服务），
然后调用 /profiles/{id}/logs/... 这几个接口。
"""

from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import DailyLog, HealthProfile
from tests._support import DBTestCase, TestingSessionLocal

TODAY = date.today()


class LogAPITestCase(DBTestCase):
    def add_profile(self, **overrides):
        """女 35 岁 165cm 60kg、减重、周期从前天开始（标准：热量 1280、运动 45 分钟）。"""
        fields = dict(user_id=1, age=35, gender="female", height_cm=165, weight_kg=60,
                      goal_type="lose_weight", start_date=TODAY - timedelta(days=2))
        fields.update(overrides)
        db = TestingSessionLocal()
        db.add(HealthProfile(**fields))
        db.commit()
        db.close()

    def put_log(self, day, user_id=1, **body):
        return self.client.put(f"/profiles/{user_id}/logs/{day.isoformat()}", json=body)

    def count_logs(self, user_id=1):
        db = TestingSessionLocal()
        n = db.query(DailyLog).filter(DailyLog.user_id == user_id).count()
        db.close()
        return n

    # ---- T5-10 计划书里的 3 天数据：得分依次 3 / 2 / 1 ----
    def test_three_day_scenario_matches_hand_calculation(self):
        self.add_profile()
        d0, d1, d2 = TODAY - timedelta(days=2), TODAY - timedelta(days=1), TODAY
        r0 = self.put_log(d0, weight_kg=60.0, exercise_minutes=50,
                          exercise_intensity="moderate", calories_in=1300).json()
        r1 = self.put_log(d1, weight_kg=60.2, exercise_minutes=60,
                          exercise_intensity="high", calories_in=1500).json()
        r2 = self.put_log(d2, weight_kg=59.2, exercise_minutes=20,
                          exercise_intensity="low", calories_in=1100).json()

        self.assertEqual([r["points"] for r in (r0, r1, r2)], [3, 2, 1])
        self.assertEqual([r["scored"] for r in (r0, r1, r2)], [3, 3, 3])
        self.assertEqual(r0["targets"]["calories"], 1280)
        # 第 1 天：运动超额(good)，热量超额(warn 提醒)
        self.assertEqual(r1["scores"]["exercise"], {"status": "exceeded", "tone": "good"})
        self.assertEqual(r1["scores"]["calories"], {"status": "exceeded", "tone": "warn"})
        self.assertEqual(r1["targets"]["weight_kg"], 59.93)
        # 第 2 天：体重超额(好)，运动、热量未完成
        self.assertEqual(r2["scores"]["weight"], {"status": "exceeded", "tone": "good"})
        self.assertEqual(r2["scores"]["exercise"], {"status": "missed", "tone": "bad"})
        self.assertEqual(r2["scores"]["calories"], {"status": "missed", "tone": "bad"})

    # ---- T5-11 同一天 PUT 两次：都 200，只有 1 行，值是第二次的 ----
    def test_put_same_day_twice_overwrites(self):
        self.add_profile()
        self.assertEqual(self.put_log(TODAY, exercise_minutes=10).status_code, 200)
        resp = self.put_log(TODAY, exercise_minutes=40)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.count_logs(), 1)
        self.assertEqual(resp.json()["exercise_minutes"], 40)

    # ---- T5-12 不合法的输入 → 422 ----
    def test_invalid_input_returns_422(self):
        self.add_profile()
        tomorrow = TODAY + timedelta(days=1)
        cases = [
            ("未来日期", tomorrow, {"exercise_minutes": 10}),
            ("运动 -1 分钟", TODAY, {"exercise_minutes": -1}),
            ("运动 601 分钟", TODAY, {"exercise_minutes": 601}),
            ("强度 extreme", TODAY, {"exercise_intensity": "extreme"}),
            ("体重 29", TODAY, {"weight_kg": 29}),
            ("热量 10001", TODAY, {"calories_in": 10001}),
        ]
        for label, day, body in cases:
            with self.subTest(case=label):
                self.assertEqual(self.put_log(day, **body).status_code, 422)
        self.assertEqual(self.count_logs(), 0)

    def test_boundary_values_are_accepted(self):
        self.add_profile()
        resp = self.put_log(TODAY, weight_kg=30, exercise_minutes=600, calories_in=10000)
        self.assertEqual(resp.status_code, 200)

    # ---- T5-13 档案不存在时 PUT / GET / DELETE → 404 ----
    def test_missing_profile_returns_404(self):
        day = TODAY.isoformat()
        self.assertEqual(self.put_log(TODAY, user_id=7, exercise_minutes=10).status_code, 404)
        self.assertEqual(self.client.get("/profiles/7/logs").status_code, 404)
        self.assertEqual(self.client.delete(f"/profiles/7/logs/{day}").status_code, 404)

    # ---- T5-14 from / to 区间：包含两端，按日期从早到晚 ----
    def test_list_with_range_is_inclusive_and_sorted(self):
        self.add_profile()
        days = [TODAY - timedelta(days=n) for n in (3, 2, 1, 0)]
        for day in reversed(days):               # 故意倒着插，验证返回时会排序
            self.put_log(day, exercise_minutes=10)

        all_logs = self.client.get("/profiles/1/logs").json()
        self.assertEqual([r["log_date"] for r in all_logs], [d.isoformat() for d in days])

        resp = self.client.get("/profiles/1/logs", params={
            "from": days[1].isoformat(), "to": days[2].isoformat()})
        self.assertEqual([r["log_date"] for r in resp.json()],
                         [days[1].isoformat(), days[2].isoformat()])

    def test_list_for_profile_without_logs_is_empty(self):
        self.add_profile()
        self.assertEqual(self.client.get("/profiles/1/logs").json(), [])

    def test_logs_of_other_users_are_not_mixed_in(self):
        self.add_profile(user_id=1)
        self.add_profile(user_id=2)
        self.put_log(TODAY, user_id=1, exercise_minutes=10)
        self.put_log(TODAY, user_id=2, exercise_minutes=20)
        rows = self.client.get("/profiles/1/logs").json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["exercise_minutes"], 10)

    # ---- T5-15 DELETE 单天：204 → 再删 404 ----
    def test_delete_single_day(self):
        self.add_profile()
        self.put_log(TODAY, exercise_minutes=10)
        url = f"/profiles/1/logs/{TODAY.isoformat()}"
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(self.client.delete(url).status_code, 404)

    # ---- T5-16 回归：删除档案后，该用户的日志也没了（别人的不受影响）----
    def test_deleting_profile_deletes_its_logs_only(self):
        self.add_profile(user_id=1)
        self.add_profile(user_id=2)
        self.put_log(TODAY, user_id=1, exercise_minutes=10)
        self.put_log(TODAY, user_id=2, exercise_minutes=10)
        self.assertEqual(self.client.delete("/profiles/1").status_code, 204)
        self.assertEqual(self.count_logs(user_id=1), 0)
        self.assertEqual(self.count_logs(user_id=2), 1)

    # ---- T5-17 派生不存库：改档案目标后，同一条日志的标准和分数自动重算 ----
    def test_scores_are_recomputed_after_profile_change(self):
        self.add_profile()
        self.put_log(TODAY, exercise_minutes=50, calories_in=1500)
        before = self.client.get("/profiles/1/logs").json()[0]
        self.assertEqual(before["targets"]["calories"], 1280)

        profile = self.client.get("/profiles/1").json()
        update = {k: v for k, v in profile.items()
                  if k not in ("id", "user_id", "created_at", "updated_at")}
        update["goal_type"] = "maintain"
        self.assertEqual(self.client.put("/profiles/1", json=update).status_code, 200)

        after = self.client.get("/profiles/1/logs").json()[0]
        self.assertEqual(after["targets"]["calories"], 1780)
        self.assertEqual(after["scores"]["calories"]["status"], "missed")   # 1500/1780 = 84%

    # ---- T5-18 绕过 API 直接插入重复的 (user_id, log_date)：数据库约束兜底 ----
    def test_database_rejects_duplicate_user_and_date(self):
        db = TestingSessionLocal()
        db.add(DailyLog(user_id=1, log_date=TODAY))
        db.commit()
        db.add(DailyLog(user_id=1, log_date=TODAY))
        with self.assertRaises(IntegrityError):
            db.commit()
        db.rollback()
        db.close()

    # ---- 回归：绕过 Python 直接写 SQL 时，没写的列要有数据库层面的默认值 ----
    # 这是手动验证时发现的：只有 default=（Python 层）不够，还要 server_default=（数据库层）
    def test_raw_sql_insert_gets_database_defaults(self):
        db = TestingSessionLocal()
        db.execute(text("INSERT INTO daily_logs (user_id, log_date, weight_kg) "
                        "VALUES (1, :d, 59.9)"), {"d": TODAY.isoformat()})
        db.commit()
        row = db.query(DailyLog).first()
        self.assertEqual(row.exercise_minutes, 0)
        self.assertEqual(row.exercise_intensity, "moderate")
        db.close()


class SleepLogAPITestCase(LogAPITestCase):
    # ---- T85-13 计划书的 3 天数据各加睡眠 5.5 / 7.5 / 9.5 ----
    def test_three_day_scenario_with_sleep(self):
        self.add_profile()
        d0, d1, d2 = TODAY - timedelta(days=2), TODAY - timedelta(days=1), TODAY
        r0 = self.put_log(d0, weight_kg=60.0, exercise_minutes=50, calories_in=1300,
                          sleep_hours=5.5).json()
        r1 = self.put_log(d1, weight_kg=60.2, exercise_minutes=60, exercise_intensity="high",
                          calories_in=1500, sleep_hours=7.5).json()
        r2 = self.put_log(d2, weight_kg=59.2, exercise_minutes=20, exercise_intensity="low",
                          calories_in=1100, sleep_hours=9.5).json()
        self.assertEqual([r["points"] for r in (r0, r1, r2)], [3, 3, 1])
        self.assertEqual([r["scored"] for r in (r0, r1, r2)], [4, 4, 4])
        self.assertEqual(r0["scores"]["sleep"], {"status": "missed", "tone": "bad"})
        self.assertEqual(r1["scores"]["sleep"], {"status": "met", "tone": "good"})
        self.assertEqual(r2["scores"]["sleep"], {"status": "exceeded", "tone": "warn"})

    # ---- T85-10 范围 0–24 ----
    def test_sleep_range_validation(self):
        self.add_profile()
        for hours, expected in [(-1, 422), (0, 200), (24, 200), (24.5, 422)]:
            with self.subTest(hours=hours):
                self.assertEqual(self.put_log(TODAY, sleep_hours=hours).status_code, expected)

    def test_sleep_can_be_cleared_by_overwriting(self):
        self.add_profile()
        self.put_log(TODAY, sleep_hours=7.5)
        body = self.put_log(TODAY, exercise_minutes=30).json()
        self.assertIsNone(body["sleep_hours"])
        self.assertIsNone(body["scores"]["sleep"])

    # ---- T85-14 派生不存库：年龄跨过 65 岁，上限从 9 变成 8 ----
    def test_sleep_score_recomputed_when_age_changes(self):
        self.add_profile(age=64)
        self.put_log(TODAY, sleep_hours=8.5)
        before = self.client.get("/profiles/1/logs").json()[0]
        self.assertEqual(before["scores"]["sleep"]["status"], "met")

        profile = self.client.get("/profiles/1").json()
        update = {k: v for k, v in profile.items()
                  if k not in ("id", "user_id", "created_at", "updated_at")}
        update["age"] = 65
        self.assertEqual(self.client.put("/profiles/1", json=update).status_code, 200)

        after = self.client.get("/profiles/1/logs").json()[0]
        self.assertEqual(after["scores"]["sleep"]["status"], "exceeded")
        self.assertEqual(after["targets"]["sleep_hours"]["max"], 8)
