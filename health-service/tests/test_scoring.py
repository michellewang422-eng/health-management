"""PR-05 的测试（上）：打分规则，纯函数，不碰数据库、不走 HTTP。

预期值都是先手算的。重点是每个阈值的"刚好等于"和"差一点点"两侧。
"""

import unittest
from datetime import date
from types import SimpleNamespace

from app.services.scoring import (
    build_log_out,
    expected_weight,
    score_calories,
    score_exercise,
    score_sleep,
    score_weight,
    tone_for,
)
from app.services.standards import effective_minutes


class ExerciseScoreTestCase(unittest.TestCase):
    # ---- T5-1 运动完成度（目标 30 分钟）----
    def test_exercise_boundaries(self):
        for minutes, expected in [(36, "exceeded"), (35, "met"), (27, "met"), (26, "missed")]:
            with self.subTest(effective_minutes=minutes):
                self.assertEqual(score_exercise(minutes, 30), expected)

    # ---- T5-2 强度折算后再打分 ----
    def test_intensity_is_converted_before_scoring(self):
        # 60 分钟低强度 = 30 分钟中等 → 刚好完成
        self.assertEqual(score_exercise(effective_minutes(60, "low"), 30), "met")
        # 20 分钟高强度 = 40 分钟中等 → 133% 超额
        self.assertEqual(score_exercise(effective_minutes(20, "high"), 30), "exceeded")
        self.assertEqual(score_exercise(effective_minutes(0, "moderate"), 30), "missed")


class CaloriesScoreTestCase(unittest.TestCase):
    # ---- T5-3 热量（目标 2000）：超过 110% 才算超标 ----
    def test_calorie_boundaries(self):
        for intake, expected in [(2200, "met"), (2201, "exceeded"), (1800, "met"), (1799, "missed")]:
            with self.subTest(calories_in=intake):
                self.assertEqual(score_calories(intake, 2000), expected)

    def test_float_edge_case_is_not_misjudged(self):
        # 1780 * 1.1 在浮点数里是 1958.0000000000002；刚好 110% 必须判 met
        self.assertEqual(score_calories(1958, 1780), "met")


class WeightScoreTestCase(unittest.TestCase):
    def check(self, goal, expected_w, cases):
        for actual, status in cases:
            with self.subTest(goal=goal, actual=actual):
                self.assertEqual(score_weight(actual, expected_w, goal), status)

    # ---- T5-4 减重，第 0 天（期望 60.0）----
    def test_lose_weight_day_0(self):
        self.check("lose_weight", 60.0,
                   [(60.3, "met"), (60.31, "missed"), (59.6, "met"), (59.5, "exceeded")])

    # ---- T5-5 减重，第 14 天（期望 59.0）----
    def test_lose_weight_day_14(self):
        self.assertEqual(expected_weight(60, "lose_weight", date(2026, 10, 1), date(2026, 10, 15)), 59.0)
        self.check("lose_weight", 59.0, [(59.0, "met"), (58.4, "exceeded")])

    # ---- T5-6 维持：偏差 ≤ 1.0 kg 算完成 ----
    def test_maintain(self):
        self.check("maintain", 60.0, [(60.9, "met"), (61.1, "missed"), (59.0, "met"), (58.9, "missed")])

    # ---- T5-7 增重，第 7 天（期望 60.25）----
    def test_gain_weight_day_7(self):
        self.assertEqual(expected_weight(60, "gain_weight", date(2026, 10, 1), date(2026, 10, 8)), 60.25)
        self.check("gain_weight", 60.25, [(60.8, "exceeded"), (60.0, "met"), (59.9, "missed")])

    def test_expected_weight_before_start_date_is_start_weight(self):
        self.assertEqual(expected_weight(60, "lose_weight", date(2026, 10, 10), date(2026, 10, 1)), 60)


class ToneTestCase(unittest.TestCase):
    # ---- T5-8 同样是"超额"，热量超标且目标不是增重时是 warn ----
    def test_calories_exceeded_tone_depends_on_goal(self):
        self.assertEqual(tone_for("calories", "exceeded", "lose_weight"), "warn")
        self.assertEqual(tone_for("calories", "exceeded", "maintain"), "warn")
        self.assertEqual(tone_for("calories", "exceeded", "gain_weight"), "good")

    def test_exercise_and_weight_exceeded_are_good(self):
        self.assertEqual(tone_for("exercise", "exceeded", "lose_weight"), "good")
        self.assertEqual(tone_for("weight", "exceeded", "lose_weight"), "good")

    def test_met_is_good_and_missed_is_bad(self):
        for metric in ["weight", "exercise", "calories"]:
            self.assertEqual(tone_for(metric, "met", "maintain"), "good")
            self.assertEqual(tone_for(metric, "missed", "maintain"), "bad")


def make_profile(goal="lose_weight"):
    return SimpleNamespace(age=35, gender="female", height_cm=165, weight_kg=60,
                           goal_type=goal, start_date=date(2026, 10, 1))


def make_log(**overrides):
    fields = dict(log_date=date(2026, 10, 1), weight_kg=None, exercise_minutes=0,
                  exercise_intensity="moderate", exercise_type=None, calories_in=None)
    fields.update(overrides)
    return SimpleNamespace(**fields)


class BuildLogOutTestCase(unittest.TestCase):
    # ---- T5-9 没填体重：weight 不打分，分母少 1 ----
    def test_missing_weight_is_not_scored(self):
        out = build_log_out(make_profile(), make_log(exercise_minutes=50, calories_in=1300))
        self.assertIsNone(out["scores"]["weight"])
        self.assertEqual(out["scored"], 2)
        self.assertEqual(out["points"], 2)

    def test_only_exercise_is_always_scored(self):
        out = build_log_out(make_profile(), make_log(exercise_minutes=10))
        self.assertEqual(out["scored"], 1)
        self.assertEqual(out["points"], 0)

    def test_targets_for_lose_weight_profile(self):
        out = build_log_out(make_profile(), make_log())
        self.assertEqual(out["targets"],
                         {"weight_kg": 60.0, "exercise_effective_minutes": 45, "calories": 1280,
                          "sleep_hours": {"min": 7, "max": 9}})


class SleepScoreTestCase(unittest.TestCase):
    # ---- T85-2 35 岁区间 7–9：刚好等于与差一点点 ----
    def test_sleep_boundaries_age_35(self):
        for hours, expected in [(6.9, "missed"), (6.99, "missed"), (7.0, "met"),
                                (9.0, "met"), (9.1, "exceeded")]:
            with self.subTest(hours=hours):
                self.assertEqual(score_sleep(hours, 35), expected)

    # ---- T85-3 65 岁及以上区间 7–8 ----
    def test_sleep_boundaries_age_70(self):
        self.assertEqual(score_sleep(8.0, 70), "met")
        self.assertEqual(score_sleep(8.5, 70), "exceeded")

    # ---- T85-4 tone：偏长是 warn，不是 good ----
    def test_sleep_tone(self):
        self.assertEqual(tone_for("sleep", "missed", "maintain"), "bad")
        self.assertEqual(tone_for("sleep", "met", "maintain"), "good")
        self.assertEqual(tone_for("sleep", "exceeded", "maintain"), "warn")
        self.assertEqual(tone_for("sleep", "exceeded", "gain_weight"), "warn")

    # ---- T85-11 / T85-12 ----
    def test_log_with_sleep_is_scored_and_counted(self):
        out = build_log_out(make_profile(), make_log(exercise_minutes=50, sleep_hours=7.5))
        self.assertEqual(out["scores"]["sleep"], {"status": "met", "tone": "good"})
        self.assertEqual(out["sleep_hours"], 7.5)
        self.assertEqual(out["targets"]["sleep_hours"], {"min": 7, "max": 9})
        self.assertEqual(out["scored"], 2)    # 运动 + 睡眠

    def test_log_without_sleep_is_unchanged(self):
        out = build_log_out(make_profile(), make_log(exercise_minutes=50, calories_in=1300))
        self.assertIsNone(out["scores"]["sleep"])
        self.assertEqual(out["scored"], 2)    # 回归：和加睡眠之前一样
