"""PR-10 的测试：卡路里计算器。预期值都是手算的。"""

import unittest
from types import SimpleNamespace

from sqlalchemy.exc import IntegrityError

from app.models import FoodItem
from app.seed_foods import seed
from app.services.calories import item_kcal, match_food
from tests._support import DBTestCase, TestingSessionLocal


def food(name, aliases="", kcal=100, source="seed"):
    return SimpleNamespace(name=name, aliases=aliases, kcal_per_100g=kcal, source=source)


class PureFunctionsTestCase(unittest.TestCase):
    # ---- T10-1 ----
    def test_item_kcal(self):
        self.assertEqual(item_kcal(100, 130), 130.0)
        self.assertEqual(item_kcal(250, 130), 325.0)

    def test_matching_order(self):
        foods = [food("鸡蛋（水煮）", "鸡蛋,水煮蛋"), food("鸡蛋饼"), food("鸡胸肉（熟）", "鸡胸")]
        self.assertEqual(match_food("鸡蛋（水煮）", foods).name, "鸡蛋（水煮）")   # 名字完全一致
        self.assertEqual(match_food("鸡蛋", foods).name, "鸡蛋（水煮）")            # 别名完全一致
        self.assertEqual(match_food("胸肉", foods).name, "鸡胸肉（熟）")            # 包含
        self.assertIsNone(match_food("火星果", foods))
        self.assertIsNone(match_food("  ", foods))

    def test_contains_picks_shortest_name(self):
        foods = [food("米饭（熟）加肉"), food("米饭（熟）")]
        self.assertEqual(match_food("米", foods).name, "米饭（熟）")

    # ---- T10-5 大小写 ----
    def test_case_insensitive(self):
        foods = [food("苹果", "apple")]
        self.assertEqual(match_food("Apple", foods).name, "苹果")
        self.assertEqual(match_food("apple", foods).name, "苹果")


class CaloriesAPITestCase(DBTestCase):
    def setUp(self):
        super().setUp()
        db = TestingSessionLocal()
        seed(db)
        db.close()

    def calc(self, *items):
        return self.client.post("/calories/calculate",
                                json={"items": [{"name": n, "grams": g} for n, g in items]})

    # ---- T10-2 / T10-3 ----
    def test_rice_and_egg_total_381(self):
        body = self.calc(("白饭", 150), ("水煮蛋", 120)).json()
        self.assertEqual([i["kcal"] for i in body["items"]], [195.0, 186.0])
        self.assertEqual(body["total_kcal"], 381.0)
        self.assertEqual(body["items"][0]["matched"], "米饭（熟）")
        self.assertEqual(body["unmatched"], [])

    # ---- T10-4 ----
    def test_contains_match(self):
        self.assertEqual(self.calc(("鸡胸", 100)).json()["items"][0]["matched"], "鸡胸肉（熟）")

    # ---- T10-6 ----
    def test_unknown_food_goes_to_unmatched(self):
        body = self.calc(("火星果", 100), ("米饭", 100)).json()
        self.assertEqual(body["unmatched"], ["火星果"])
        self.assertEqual(body["total_kcal"], 130.0)

    # ---- T10-7 / T10-8 ----
    def test_invalid_grams_and_empty_items(self):
        for grams in (0, -5, 5001):
            with self.subTest(grams=grams):
                self.assertEqual(self.calc(("米饭", grams)).status_code, 422)
        self.assertEqual(self.client.post("/calories/calculate", json={"items": [{"name": "米饭"}]}).status_code, 422)
        self.assertEqual(self.client.post("/calories/calculate", json={"items": []}).status_code, 422)
        self.assertEqual(self.calc(("米饭", 5000)).status_code, 200)

    # ---- T10-9 种子幂等 ----
    def test_seed_is_idempotent(self):
        db = TestingSessionLocal()
        before = db.query(FoodItem).count()
        seed(db)
        seed(db)
        self.assertEqual(db.query(FoodItem).count(), before)
        self.assertGreaterEqual(before, 50)
        db.close()

    # ---- T10-10 重名 ----
    def test_duplicate_name_rejected(self):
        db = TestingSessionLocal()
        db.add(FoodItem(name="米饭（熟）", kcal_per_100g=1))
        with self.assertRaises(IntegrityError):
            db.commit()
        db.rollback()
        db.close()

    # ---- T10-11 查询 ----
    def test_search_foods(self):
        names = [f["name"] for f in self.client.get("/foods", params={"q": "米"}).json()]
        self.assertIn("米饭（熟）", names)
        self.assertEqual(len(self.client.get("/foods").json()), 20)       # 空查询最多 20 条
        self.assertEqual(self.client.get("/foods", params={"q": "' OR 1=1 --"}).json(), [])
        self.assertEqual(self.client.get("/foods", params={"q": "%"}).json(), [])   # % 只是普通字符
        # 注入之后表还在
        self.assertEqual(self.calc(("米饭", 100)).status_code, 200)
