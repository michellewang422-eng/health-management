"""PR-04 的测试：参考标准引擎。

上半部分是纯函数测试：不启动 server、不碰数据库，直接调用函数对比数字。
所有预期值都是**先用计算器手算**再写进来的（不是先跑代码拿输出当答案）。
下半部分测 GET /profiles/{id}/standards 这个接口。
"""

import unittest
from types import SimpleNamespace

from app.models import HealthProfile
from app.services.standards import (
    build_standards,
    calc_bmi,
    calc_bmr,
    classify_blood_pressure,
    classify_bmi,
    classify_cholesterol,
    classify_glucose,
    daily_calories,
    daily_exercise_minutes,
    effective_minutes,
    hdl_reference,
    healthy_weight_range,
    suggested_exercises,
)
from tests._support import DBTestCase, TestingSessionLocal


class BodyMetricsTestCase(unittest.TestCase):
    # ---- T4-1 BMI ----
    def test_bmi_60kg_165cm(self):
        self.assertEqual(calc_bmi(60, 165), 22.0)

    def test_bmi_categories_at_boundaries(self):
        for bmi, expected in [(18.4, "underweight"), (18.5, "normal"), (24.9, "normal"),
                              (25.0, "overweight"), (29.9, "overweight"), (30.0, "obese")]:
            with self.subTest(bmi=bmi):
                self.assertEqual(classify_bmi(bmi), expected)

    # ---- T4-2 健康体重范围 ----
    def test_healthy_weight_range_165cm(self):
        self.assertEqual(healthy_weight_range(165), [50.4, 67.8])


class CalorieTestCase(unittest.TestCase):
    # ---- T4-3 BMR ----
    def test_bmr_female_35_165_60(self):
        self.assertAlmostEqual(calc_bmr("female", 35, 165, 60), 1295.25, places=2)

    def test_bmr_male_40_180_80(self):
        self.assertAlmostEqual(calc_bmr("male", 40, 180, 80), 1730, places=2)

    # ---- T4-4 女 35/165/60 ----
    def test_daily_calories_female(self):
        for goal, expected in [("maintain", 1780), ("lose_weight", 1280), ("gain_weight", 2080)]:
            with self.subTest(goal=goal):
                self.assertEqual(daily_calories("female", 35, 165, 60, goal), expected)

    # ---- T4-5 男 40/180/80 ----
    def test_daily_calories_male(self):
        self.assertEqual(daily_calories("male", 40, 180, 80, "maintain"), 2380)
        self.assertEqual(daily_calories("male", 40, 180, 80, "lose_weight"), 1880)

    # ---- T4-6 安全下限：算出来比下限低，就取下限 ----
    def test_calorie_floor(self):
        # 女：1014.6 → 1200；男：1445.6 → 1500
        self.assertEqual(daily_calories("female", 25, 150, 45, "lose_weight"), 1200)
        self.assertEqual(daily_calories("male", 18, 160, 50, "lose_weight"), 1500)


class ExerciseTestCase(unittest.TestCase):
    # ---- T4-7 每日运动目标 ----
    def test_daily_exercise_minutes(self):
        self.assertEqual(daily_exercise_minutes("lose_weight"), 45)
        self.assertEqual(daily_exercise_minutes("maintain"), 30)
        self.assertEqual(daily_exercise_minutes("gain_weight"), 30)

    # ---- T4-8 强度折算 ----
    def test_intensity_conversion(self):
        self.assertEqual(effective_minutes(10, "low"), 5)
        self.assertEqual(effective_minutes(10, "moderate"), 10)
        self.assertEqual(effective_minutes(10, "high"), 20)

    # ---- T4-9 推荐项目随年龄变 ----
    def test_suggestions_by_age(self):
        self.assertIn("力量训练每周 2 天", suggested_exercises(25))
        self.assertIn("慢跑", suggested_exercises(25))
        senior = suggested_exercises(70)
        self.assertIn("平衡训练", senior)
        self.assertNotIn("慢跑", senior)

    def test_suggestions_age_group_boundaries(self):
        self.assertIn("慢跑", suggested_exercises(39))
        self.assertNotIn("慢跑", suggested_exercises(40))
        self.assertNotIn("平衡训练", suggested_exercises(64))
        self.assertIn("平衡训练", suggested_exercises(65))


class ClassificationTestCase(unittest.TestCase):
    # ---- T4-10 血糖边界 ----
    def test_glucose_boundaries(self):
        for value, expected in [(99, "normal"), (100, "elevated"), (125, "elevated"), (126, "high")]:
            with self.subTest(value=value):
                self.assertEqual(classify_glucose(value), expected)

    # ---- T4-11 血压：从重到轻判断 ----
    def test_blood_pressure_categories(self):
        cases = [
            ((119, 79), "normal"), ((120, 79), "elevated"), ((125, 85), "stage1"),
            ((130, 70), "stage1"), ((140, 70), "stage2"), ((135, 90), "stage2"),
            ((181, 70), "crisis"), ((150, 121), "crisis"),
        ]
        for (sys_, dia), expected in cases:
            with self.subTest(bp=(sys_, dia)):
                self.assertEqual(classify_blood_pressure(sys_, dia), expected)

    # ---- T4-12 总胆固醇边界 ----
    def test_cholesterol_boundaries(self):
        for value, expected in [(199, "ideal"), (200, "borderline"), (239, "borderline"), (240, "high")]:
            with self.subTest(value=value):
                self.assertEqual(classify_cholesterol(value), expected)

    # ---- T4-13 HDL 参考值随性别变 ----
    def test_hdl_reference_by_gender(self):
        self.assertEqual(hdl_reference("male"), ">= 40")
        self.assertEqual(hdl_reference("female"), ">= 50")


def make_profile(**overrides):
    """随手造一个"像档案"的对象，build_standards 只读属性，不需要真的数据库行。"""
    fields = dict(
        age=35, gender="female", height_cm=165, weight_kg=60, goal_type="maintain",
        baseline_glucose_mgdl=None, baseline_cholesterol_mgdl=None,
        baseline_systolic=None, baseline_diastolic=None,
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


class BuildStandardsTestCase(unittest.TestCase):
    def test_example_from_plan(self):
        s = build_standards(make_profile())
        self.assertEqual(s["bmi"], 22.0)
        self.assertEqual(s["bmi_category"], "normal")
        self.assertEqual(s["healthy_weight_kg"], [50.4, 67.8])
        self.assertEqual(s["bmr"], 1295)
        self.assertEqual(s["daily_calories"], 1780)
        self.assertEqual(s["weekly_weight_change_kg"], 0)
        self.assertEqual(s["exercise"]["daily_effective_minutes"], 30)

    # ---- T4-14 没填任何原始指标：三项评估都是 None，不报错 ----
    def test_no_baseline_gives_none_assessments(self):
        s = build_standards(make_profile())
        self.assertEqual(s["baseline_assessment"],
                         {"glucose": None, "blood_pressure": None, "cholesterol": None})

    def test_baseline_assessment_when_provided(self):
        s = build_standards(make_profile(
            baseline_glucose_mgdl=110, baseline_cholesterol_mgdl=205,
            baseline_systolic=135, baseline_diastolic=85))
        self.assertEqual(s["baseline_assessment"],
                         {"glucose": "elevated", "blood_pressure": "stage1", "cholesterol": "borderline"})

    def test_blood_pressure_needs_both_numbers(self):
        # 只有一半血压数据时不评估（接口层已经拦住了这种数据，这里是防御）
        s = build_standards(make_profile(baseline_systolic=120))
        self.assertIsNone(s["baseline_assessment"]["blood_pressure"])


class StandardsAPITestCase(DBTestCase):
    def add_profile(self, **overrides):
        """直接往数据库里放一条档案，不走 POST（这里只关心 standards 接口）。"""
        fields = dict(user_id=1, age=35, gender="female", height_cm=165, weight_kg=60)
        fields.update(overrides)
        db = TestingSessionLocal()
        db.add(HealthProfile(**fields))
        db.commit()
        db.close()

    # ---- T4-15 档案存在 → 200；不存在 → 404 ----
    def test_standards_for_existing_profile(self):
        self.add_profile()
        resp = self.client.get("/profiles/1/standards")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["daily_calories"], 1780)
        self.assertIn("disclaimer", body)

    def test_standards_for_missing_profile_returns_404(self):
        self.assertEqual(self.client.get("/profiles/9/standards").status_code, 404)

    # ---- 目标改成减重：热量 1280、运动 45 分钟 ----
    def test_lose_weight_goal_changes_standards(self):
        self.add_profile(goal_type="lose_weight")
        body = self.client.get("/profiles/1/standards").json()
        self.assertEqual(body["daily_calories"], 1280)
        self.assertEqual(body["exercise"]["daily_effective_minutes"], 45)
        self.assertEqual(body["weekly_weight_change_kg"], -0.5)
