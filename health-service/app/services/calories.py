"""卡路里计算：匹配食物名 + 算热量。纯函数，不读数据库。"""


def item_kcal(grams, kcal_per_100g):
    """每项热量 = 克数 ÷ 100 × 每 100 g 千卡，保留 1 位小数。"""
    return round(grams / 100 * kcal_per_100g, 1)


def _aliases(food):
    return [a.strip().lower() for a in (food.aliases or "").split(",") if a.strip()]


def match_food(keyword, foods):
    """匹配顺序：名字完全一致 → 别名完全一致 → 名字或别名包含关键字（多个取名字最短）→ None。
    英文不区分大小写。foods 是有 name / aliases 属性的对象列表。"""
    key = keyword.strip().lower()
    if not key:
        return None
    for food in foods:
        if food.name.lower() == key:
            return food
    for food in foods:
        if key in _aliases(food):
            return food
    hits = [f for f in foods
            if key in f.name.lower() or any(key in a for a in _aliases(f))]
    return min(hits, key=lambda f: len(f.name)) if hits else None


def calculate(items, foods):
    """items：[{name, grams}]。没匹配到的食物不计入总数，单独列在 unmatched 里。"""
    result, unmatched, total = [], [], 0.0
    for item in items:
        food = match_food(item["name"], foods)
        if food is None:
            unmatched.append(item["name"])
            continue
        kcal = item_kcal(item["grams"], food.kcal_per_100g)
        total += kcal
        result.append({
            "input": item["name"], "matched": food.name, "grams": item["grams"],
            "kcal_per_100g": food.kcal_per_100g, "kcal": kcal, "source": food.source,
        })
    return {"items": result, "unmatched": unmatched, "total_kcal": round(total, 1)}
