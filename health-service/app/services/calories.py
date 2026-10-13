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


def find_foods(keyword, foods):
    """返回「这个关键字可能指的所有食物」，按 foods 的顺序。0 个 = 没找到；1 个 = 确定；
    多个 = 有歧义，要让用户自己选（比如「鸡肉」→ 鸡胸肉、鸡腿肉）。
    只取第一个有结果的层级（英文不区分大小写）：
    1 名字完全一致（含去掉括号的名字）→ 2 别名完全一致 → 3 名字或别名包含关键字
    → 4 关键字里包含某个食物名或别名（如「烤鸡胸肉」含「鸡胸」，取最长的词，至少 2 个字）。"""
    key = keyword.strip().lower()
    if not key:
        return []
    levels = [
        [f for f in foods if f.name.lower() == key or _core(f.name) == key],
        [f for f in foods if key in _aliases(f)],
        [f for f in foods if key in f.name.lower() or any(key in a for a in _aliases(f))],
    ]
    for hits in levels:
        if hits:
            return hits
    best_len, best = 1, []
    for food in foods:
        longest = max((len(t) for t in [_core(food.name), *_aliases(food)] if t in key), default=0)
        if longest > best_len:
            best_len, best = longest, [food]
        elif longest == best_len and longest > 1:
            best.append(food)
    return best


def match_food(keyword, foods):
    """只有"恰好一个候选"时才返回它；没找到或有歧义返回 None（歧义由 calculate 单独报告）。"""
    hits = find_foods(keyword, foods)
    return hits[0] if len(hits) == 1 else None


def calculate(items, foods):
    """items：[{name, grams}]。结果分三类：
    - items：匹配到唯一食物，计入总数；
    - unmatched：没找到，不计入总数；
    - ambiguous：有多个候选（如「鸡肉」），不替用户做决定，列出选项让用户选，不计入总数。
    index 是这一行在请求里的位置，页面用它知道要改哪一行。"""
    result, unmatched, ambiguous, total = [], [], [], 0.0
    for index, item in enumerate(items):
        hits = find_foods(item["name"], foods)
        if not hits:
            unmatched.append(item["name"])
        elif len(hits) > 1:
            ambiguous.append({
                "index": index, "input": item["name"], "grams": item["grams"],
                "options": [{"name": f.name, "kcal_per_100g": f.kcal_per_100g} for f in hits[:8]],
            })
        else:
            food = hits[0]
            kcal = item_kcal(item["grams"], food.kcal_per_100g)
            total += kcal
            result.append({
                "index": index, "input": item["name"], "matched": food.name,
                "grams": item["grams"], "kcal_per_100g": food.kcal_per_100g,
                "kcal": kcal, "source": food.source,
            })
    return {"items": result, "unmatched": unmatched, "ambiguous": ambiguous,
            "total_kcal": round(total, 1)}
