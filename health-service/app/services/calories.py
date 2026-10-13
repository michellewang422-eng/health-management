"""卡路里计算：匹配食物名 + 算热量。纯函数，不读数据库。"""

import re


def item_kcal(grams, kcal_per_100g):
    """每项热量 = 克数 ÷ 100 × 每 100 g 千卡，保留 1 位小数。"""
    return round(grams / 100 * kcal_per_100g, 1)


def _aliases(food):
    return [a.strip().lower() for a in (food.aliases or "").split(",") if a.strip()]


def _core(name):
    """去掉括号里的说明：「米饭（熟）」→「米饭」。"""
    return re.split(r"[（(]", name.lower())[0].strip()


def match_food(keyword, foods):
    """匹配顺序（英文不区分大小写）：
    1 名字完全一致（含去掉括号的名字）→ 2 别名完全一致 → 3 名字或别名包含关键字（多个取名字最短）
    → 4 关键字里包含某个食物名或别名（如「烤鸡胸肉」含「鸡胸」，取最长的那个词）→ None。
    别名完全一致有多个食物时，取列表里靠前的（数据库按 id 排）。"""
    key = keyword.strip().lower()
    if not key:
        return None
    for food in foods:
        if food.name.lower() == key or _core(food.name) == key:
            return food
    for food in foods:
        if key in _aliases(food):
            return food
    hits = [f for f in foods
            if key in f.name.lower() or any(key in a for a in _aliases(f))]
    if hits:
        return min(hits, key=lambda f: len(f.name))
    best, best_len = None, 1            # 至少 2 个字才算，避免「油」「蛋」这类单字误配
    for food in foods:
        for term in [_core(food.name), *_aliases(food)]:
            if len(term) > best_len and term in key:
                best, best_len = food, len(term)
    return best


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
