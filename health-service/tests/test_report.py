"""PR-09 的测试：周期报告。预期值都是手算的（和 PR-05 计划书里的 3 天数据一致）。"""

from datetime import date, timedelta

from app.models import DailyLog, HealthProfile
from app.services.report import build_report
from tests._support import DBTestCase, TestingSessionLocal

TODAY = date.today()


class ReportTestCase(DBTestCase):
    def add_profile(self, **overrides):
        """女 35 岁 165cm 60kg、减重、周期从前天开始。"""
        fields = dict(user_id=1, age=35, gender="female", height_cm=165, weight_kg=60,
                      goal_type="lose_weight", start_date=TODAY - timedelta(days=2))
        fields.update(overrides)
        db = TestingSessionLocal()
        db.add(HealthProfile(**fields))
        db.commit()
        db.close()

    def put_log(self, day, **body):
        return self.client.put(f"/profiles/1/logs/{day.isoformat()}", json=body)

    def three_days(self, sleep=None):
        sleep = sleep or [None, None, None]
        d0, d1, d2 = TODAY - timedelta(days=2), TODAY - timedelta(days=1), TODAY
        self.put_log(d0, weight_kg=60.0, exercise_minutes=50, calories_in=1300, sleep_hours=sleep[0])
        self.put_log(d1, weight_kg=60.2, exercise_minutes=60, exercise_intensity="high",
                     calories_in=1500, sleep_hours=sleep[1])
        self.put_log(d2, weight_kg=59.2, exercise_minutes=20, exercise_intensity="low",
                     calories_in=1100, sleep_hours=sleep[2])

    def report(self):
        resp = self.client.get("/profiles/1/report")
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    # ---- T9-1 没有任何记录：不报错，实际值全是 null ----
    def test_empty_report(self):
        self.add_profile(start_date=TODAY)
        r = self.report()
        self.assertEqual(len(r["series"]), 30)
        self.assertTrue(all(d["weight_kg"] is None and d["calories_in"] is None
                            and d["sleep_hours"] is None for d in r["series"]))
        self.assertEqual(r["summary"]["logged_days"], 0)
        self.assertIsNone(r["summary"]["completion_rate_pct"])
        self.assertIsNone(r["summary"]["avg_sleep_hours"])
        self.assertEqual(r["summary"]["total_exercise_minutes"], 0)

    # ---- T9-2 3 天数据，不填睡眠 ----
    def test_three_days_without_sleep(self):
        self.add_profile()
        self.three_days()
        s = self.report()["summary"]
        self.assertEqual((s["logged_days"], s["points"], s["scored"]), (3, 6, 9))
        self.assertEqual(s["completion_rate_pct"], 66.7)
        self.assertEqual(s["avg_calories"], 1300)
        self.assertEqual(s["total_exercise_minutes"], 130)
        self.assertEqual(s["weight_change_kg"], -0.8)
        self.assertIsNone(s["avg_sleep_hours"])

    # ---- T9-2b / T9-3 睡眠 5.5 / 7.5 / 9.5 ----
    def test_three_days_with_sleep(self):
        self.add_profile()
        self.three_days(sleep=[5.5, 7.5, 9.5])
        s = self.report()["summary"]
        self.assertEqual((s["points"], s["scored"]), (7, 12))
        self.assertEqual(s["completion_rate_pct"], 58.3)
        self.assertEqual(s["avg_sleep_hours"], 7.5)
        self.assertEqual(s["status_counts"], {
            "weight": {"exceeded": 1, "met": 2, "missed": 0},
            "exercise": {"exceeded": 1, "met": 1, "missed": 1},
            "calories": {"exceeded": 1, "met": 1, "missed": 1},
            "sleep": {"exceeded": 1, "met": 1, "missed": 1},
        })

    def test_status_counts_without_sleep_are_zero(self):
        self.add_profile()
        self.three_days()
        self.assertEqual(self.report()["summary"]["status_counts"]["sleep"],
                         {"exceeded": 0, "met": 0, "missed": 0})

    # ---- T9-4 周期结束边界 ----
    def test_is_finished_boundary(self):
        self.add_profile(start_date=TODAY - timedelta(days=30))
        self.assertTrue(self.report()["cycle"]["is_finished"])
        self.client.delete("/profiles/1")
        self.add_profile(start_date=TODAY - timedelta(days=29))
        c = self.report()["cycle"]
        self.assertFalse(c["is_finished"])
        self.assertEqual(c["elapsed_days"], 30)

    # ---- T9-5 第 14 天的目标体重 ----
    def test_target_weight_day_14(self):
        self.add_profile(start_date=TODAY - timedelta(days=14))
        self.assertEqual(self.report()["series"][14]["target_weight_kg"], 59.0)

    # ---- T9-6 周期外的记录不计入 ----
    def test_logs_outside_cycle_are_ignored(self):
        self.add_profile(start_date=TODAY - timedelta(days=5), cycle_days=7)
        db = TestingSessionLocal()
        db.add(DailyLog(user_id=1, log_date=TODAY - timedelta(days=6), exercise_minutes=100))
        db.add(DailyLog(user_id=1, log_date=TODAY + timedelta(days=2), exercise_minutes=100))
        db.add(DailyLog(user_id=1, log_date=TODAY, exercise_minutes=30))
        db.commit()
        db.close()
        r = self.report()
        self.assertEqual(r["summary"]["logged_days"], 1)
        self.assertEqual(r["summary"]["total_exercise_minutes"], 30)

    # ---- T9-7 只有 1 个体重 ----
    def test_single_weight_gives_null_change(self):
        self.add_profile()
        self.put_log(TODAY, weight_kg=59.5)
        self.assertIsNone(self.report()["summary"]["weight_change_kg"])

    # ---- T9-8 周期 7 天 ----
    def test_cycle_7_days(self):
        self.add_profile(cycle_days=7)
        self.assertEqual(len(self.report()["series"]), 7)

    # ---- T9-9 档案不存在 ----
    def test_missing_profile_returns_404(self):
        self.assertEqual(self.client.get("/profiles/9/report").status_code, 404)

    # ---- T9-10 / T9-11 睡眠目标线 ----
    def test_sleep_targets_follow_age(self):
        self.add_profile(age=35)
        d = self.report()["series"][0]
        self.assertEqual((d["target_sleep_min_hours"], d["target_sleep_max_hours"]), (7, 9))
        self.client.delete("/profiles/1")
        self.add_profile(age=65)
        d = self.report()["series"][0]
        self.assertEqual((d["target_sleep_min_hours"], d["target_sleep_max_hours"]), (7, 8))

    def test_unlogged_day_has_null_actual_but_targets(self):
        self.add_profile()
        d = self.report()["series"][5]      # 没打卡的一天
        self.assertIsNone(d["sleep_hours"])
        self.assertEqual(d["target_calories"], 1280)
        self.assertEqual(d["target_exercise_min"], 45)

    # ---- T9-12 睡眠只填 2 天：均值不含没填的天 ----
    def test_avg_sleep_skips_unfilled_days(self):
        self.add_profile()
        self.put_log(TODAY - timedelta(days=2), sleep_hours=7.0)
        self.put_log(TODAY - timedelta(days=1), sleep_hours=8.0)
        self.put_log(TODAY, exercise_minutes=30)
        self.assertEqual(self.report()["summary"]["avg_sleep_hours"], 7.5)

    def test_build_report_without_aggregates_matches(self):
        # 纯函数不依赖 SQL 聚合：自己算的结果也一样
        from types import SimpleNamespace
        p = SimpleNamespace(age=35, gender="female", height_cm=165, weight_kg=60,
                            goal_type="lose_weight", start_date=TODAY, cycle_days=7)
        logs = [SimpleNamespace(log_date=TODAY, weight_kg=None, exercise_minutes=45,
                                exercise_intensity="moderate", exercise_type=None,
                                calories_in=1300, sleep_hours=8.0)]
        r = build_report(p, logs, TODAY)
        self.assertEqual(r["summary"]["avg_calories"], 1300)
        self.assertEqual(r["summary"]["avg_sleep_hours"], 8.0)
