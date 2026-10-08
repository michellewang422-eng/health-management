"""PR-02 的测试：health_profiles 表的结构和约束对不对？

这里不走 HTTP，直接用 Session 往数据库里写，测的是"表本身"：
默认值、选填列、唯一约束、必填约束，以及用例之间是否互相隔离。
"""

from datetime import date

from sqlalchemy.exc import IntegrityError

from app.models import HealthProfile
from tests._support import DBTestCase, TestingSessionLocal


def make_profile(**overrides):
    """造一条只带 7 个必填字段的档案；overrides 可以覆盖其中任意字段。"""
    fields = dict(user_id=1, age=35, gender="female", height_cm=165, weight_kg=60)
    fields.update(overrides)
    return HealthProfile(**fields)


class HealthProfileModelTestCase(DBTestCase):
    # ---- T2-1 正常路径：只给必填字段，默认值自动补上 ----
    def test_insert_with_required_fields_fills_defaults(self):
        db = TestingSessionLocal()
        db.add(make_profile())
        db.commit()

        row = db.query(HealthProfile).first()
        self.assertEqual(row.id, 1)
        self.assertEqual(row.cycle_days, 30)
        self.assertEqual(row.goal_type, "maintain")
        self.assertEqual(row.start_date, date.today())
        self.assertIsNotNone(row.created_at)
        db.close()

    # ---- T2-2 选填列不传 → None ----
    def test_optional_columns_default_to_none(self):
        db = TestingSessionLocal()
        db.add(make_profile())
        db.commit()

        row = db.query(HealthProfile).first()
        self.assertIsNone(row.baseline_glucose_mgdl)
        self.assertIsNone(row.baseline_cholesterol_mgdl)
        self.assertIsNone(row.baseline_systolic)
        self.assertIsNone(row.baseline_diastolic)
        self.assertIsNone(row.goal_note)
        db.close()

    # ---- T2-3 错误输入：同一个 user_id 不能有两份档案 ----
    def test_duplicate_user_id_raises(self):
        db = TestingSessionLocal()
        db.add(make_profile(user_id=1))
        db.commit()

        db.add(make_profile(user_id=1, age=36))
        with self.assertRaises(IntegrityError):
            db.commit()
        # 出错后 Session 处于"半坏"状态，必须 rollback 才能继续用
        db.rollback()
        db.close()

    # ---- T2-4 错误输入：必填列为空 ----
    def test_missing_required_age_raises(self):
        db = TestingSessionLocal()
        db.add(make_profile(age=None))
        with self.assertRaises(IntegrityError):
            db.commit()
        db.rollback()
        db.close()

    # ---- T2-5 用例隔离：两个测试各插一条，互不干扰 ----
    # 如果隔离失效，第二个测试跑起来表里已经有 user_id=1，就会因为唯一约束而失败
    def test_isolation_first(self):
        db = TestingSessionLocal()
        db.add(make_profile(user_id=1))
        db.commit()
        self.assertEqual(db.query(HealthProfile).count(), 1)
        db.close()

    def test_isolation_second(self):
        db = TestingSessionLocal()
        db.add(make_profile(user_id=1))
        db.commit()
        self.assertEqual(db.query(HealthProfile).count(), 1)
        db.close()
