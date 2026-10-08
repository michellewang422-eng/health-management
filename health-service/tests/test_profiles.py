"""PR-03 的测试：健康档案的增查改删接口。

测试里不会真的去调用 User-management-service，而是用 app.dependency_overrides
把 get_user_checker 换成一个"假的 user_exists"：
  - user_id == 999 → 用户不存在
  - user_id == 500 → User-management-service 挂了
  - 其它         → 用户存在
这样测试不依赖网络、也不用启动另一个 server。
"""

from datetime import date

from app.main import app
from app.models import HealthProfile
from app.services.user_client import UserServiceUnavailable, get_user_checker
from tests._support import DBTestCase, TestingSessionLocal

VALID = {"user_id": 1, "age": 35, "gender": "female", "height_cm": 165, "weight_kg": 60}


def fake_exists(user_id):
    if user_id == 500:
        raise UserServiceUnavailable()   # 模拟 User-management-service 挂了
    return user_id != 999                # 999 = 不存在的用户


class ProfileAPITestCase(DBTestCase):
    def setUp(self):
        super().setUp()
        # 把真实的"查用户"换成假的；dependency_overrides 是一个全局字典，用完必须还原
        app.dependency_overrides[get_user_checker] = lambda: fake_exists

    def tearDown(self):
        app.dependency_overrides.pop(get_user_checker, None)
        super().tearDown()

    def reset_db(self):
        """subTest 循环里每轮都要一个空数据库，否则第二轮会因为 user_id 重复而 409。"""
        self.tearDown()
        self.setUp()

    def create(self, **overrides):
        return self.client.post("/profiles", json={**VALID, **overrides})

    # ---- T3-1 只传必填字段：默认值生效 ----
    def test_create_with_required_fields_uses_defaults(self):
        resp = self.create()
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["cycle_days"], 30)
        self.assertEqual(body["goal_type"], "maintain")
        self.assertEqual(body["start_date"], date.today().isoformat())

    # ---- T3-2 传全部选填字段：原样回显 ----
    def test_create_with_all_fields_echoes_back(self):
        full = {
            **VALID,
            "baseline_glucose_mgdl": 92.0,
            "baseline_cholesterol_mgdl": 180.0,
            "baseline_systolic": 118,
            "baseline_diastolic": 76,
            "goal_type": "lose_weight",
            "goal_note": "三个月减 3 公斤",
            "cycle_days": 60,
            "start_date": "2026-10-01",
        }
        resp = self.client.post("/profiles", json=full)
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        for key, value in full.items():
            with self.subTest(field=key):
                self.assertEqual(body[key], value)

    # ---- T3-3 逐个缺少必填字段 → 422 ----
    def test_missing_each_required_field_returns_422(self):
        for field in ["user_id", "age", "gender", "height_cm", "weight_kg"]:
            with self.subTest(missing=field):
                payload = {k: v for k, v in VALID.items() if k != field}
                resp = self.client.post("/profiles", json=payload)
                self.assertEqual(resp.status_code, 422)

    # ---- 边界值：下限 - 1、下限、上限、上限 + 1 ----
    def check_boundaries(self, field, cases):
        for value, expected in cases:
            with self.subTest(field=field, value=value):
                self.reset_db()
                resp = self.create(**{field: value})
                self.assertEqual(resp.status_code, expected)

    # ---- T3-4 年龄 ----
    def test_age_boundaries(self):
        self.check_boundaries("age", [(17, 422), (18, 201), (100, 201), (101, 422)])

    # ---- T3-5 性别只能是 male / female ----
    def test_gender_other_is_rejected(self):
        self.assertEqual(self.create(gender="other").status_code, 422)

    # ---- T3-6 身高、体重 ----
    def test_height_boundaries(self):
        self.check_boundaries("height_cm", [(99, 422), (100, 201), (250, 201), (251, 422)])

    def test_weight_boundaries(self):
        self.check_boundaries("weight_kg", [(29, 422), (30, 201), (300, 201), (301, 422)])

    # ---- T3-7 / T3-8 血压必须成对，且收缩压 > 舒张压 ----
    def test_systolic_without_diastolic_is_rejected(self):
        self.assertEqual(self.create(baseline_systolic=120).status_code, 422)

    def test_diastolic_without_systolic_is_rejected(self):
        self.assertEqual(self.create(baseline_diastolic=80).status_code, 422)

    def test_systolic_not_greater_than_diastolic_is_rejected(self):
        resp = self.create(baseline_systolic=80, baseline_diastolic=120)
        self.assertEqual(resp.status_code, 422)

    def test_valid_blood_pressure_pair_is_accepted(self):
        resp = self.create(baseline_systolic=120, baseline_diastolic=80)
        self.assertEqual(resp.status_code, 201)

    # ---- T3-9 监测周期 ----
    def test_cycle_days_boundaries(self):
        self.check_boundaries("cycle_days", [(6, 422), (7, 201), (365, 201), (366, 422)])

    # ---- T3-10 用户不存在 → 404 ----
    def test_unknown_user_returns_404(self):
        self.assertEqual(self.create(user_id=999).status_code, 404)

    # ---- T3-11 User-management-service 挂了 → 502，且数据库里没有新增行 ----
    def test_user_service_down_returns_502_and_creates_nothing(self):
        self.assertEqual(self.create(user_id=500).status_code, 502)
        db = TestingSessionLocal()
        self.assertEqual(db.query(HealthProfile).count(), 0)
        db.close()

    # ---- T3-12 同一个 user_id 建两次 → 201 然后 409 ----
    def test_duplicate_profile_returns_409(self):
        self.assertEqual(self.create().status_code, 201)
        self.assertEqual(self.create().status_code, 409)

    # ---- T3-13 读档案 ----
    def test_get_existing_and_missing_profile(self):
        self.create()
        self.assertEqual(self.client.get("/profiles/1").status_code, 200)
        self.assertEqual(self.client.get("/profiles/2").status_code, 404)

    # ---- T3-14 PUT 改体重，其它字段和 start_date 不变 ----
    def test_put_updates_weight_and_keeps_start_date(self):
        created = self.create(start_date="2026-10-01").json()
        update = {k: v for k, v in VALID.items() if k != "user_id"}
        update["weight_kg"] = 58
        resp = self.client.put("/profiles/1", json=update)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["weight_kg"], 58)
        self.assertEqual(body["age"], created["age"])
        self.assertEqual(body["start_date"], "2026-10-01")

    # ---- T3-15 PUT 把已有的选填项传 null → 清空 ----
    def test_put_null_clears_optional_field(self):
        self.create(baseline_glucose_mgdl=92.0)
        update = {k: v for k, v in VALID.items() if k != "user_id"}
        update["baseline_glucose_mgdl"] = None
        resp = self.client.put("/profiles/1", json=update)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["baseline_glucose_mgdl"])

    # ---- T3-16 PUT 不存在的档案 → 404 ----
    def test_put_missing_profile_returns_404(self):
        update = {k: v for k, v in VALID.items() if k != "user_id"}
        self.assertEqual(self.client.put("/profiles/42", json=update).status_code, 404)

    # ---- T3-17 DELETE：204 → 再查 404 → 再删 404 ----
    def test_delete_profile_then_gone(self):
        self.create()
        self.assertEqual(self.client.delete("/profiles/1").status_code, 204)
        self.assertEqual(self.client.get("/profiles/1").status_code, 404)
        self.assertEqual(self.client.delete("/profiles/1").status_code, 404)
