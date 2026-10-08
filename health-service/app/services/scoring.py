"""打分：拿用户"实际做到的"和 standards.py 算出的"应该做到的"对比。

三个结果：exceeded（超额）/ met（完成）/ missed（未完成）。
同样是"超额"，对不同指标意义不同（运动超额是好事，热量超标要提醒），
所以每个结果再带一个 tone：good（好）、warn（提醒）、bad（没做到）。

这个文件全是纯函数，不读数据库。打分结果**不存库**，每次读取时现算：
这样用户改了档案（比如目标），历史记录的分数会自动跟着更新。
"""

from datetime import date

from app.services.standards import (
    daily_calories,
    daily_exercise_minutes,
    effective_minutes,
    weekly_weight_change,
)

# ---------- 阈值（都写在这里，改标准只改这里）----------
EXERCISE_EXCEED, EXERCISE_MET = 1.2, 0.9   # 完成度 ≥120% 超额；≥90% 完成
CAL_HIGH, CAL_LOW = 1.1, 0.9               # 摄入 >110% 超标；≥90% 算完成
WEIGHT_LOSE_EXCEED, WEIGHT_LOSE_MET = -0.5, 0.3     # 减重：差 ≤ -0.5 超额；≤ +0.3 完成
WEIGHT_GAIN_EXCEED, WEIGHT_GAIN_MET = 0.5, -0.3     # 增重：差 ≥ +0.5 超额；≥ -0.3 完成
WEIGHT_MAINTAIN_TOLERANCE = 1.0                     # 维持：偏差在 ±1.0 kg 内算完成


def score_exercise(effective_min, target_min):
    # round(…, 4)：浮点数有误差，比如 1780 * 1.1 会得到 1958.0000000000002，
    # 先取 4 位小数再比较，刚好等于阈值的数据才不会被判错
    ratio = round(effective_min / target_min, 4)
    if ratio >= EXERCISE_EXCEED:
        return "exceeded"
    if ratio >= EXERCISE_MET:
        return "met"
    return "missed"


def score_calories(calories_in, target):
    ratio = round(calories_in / target, 4)
    if ratio > CAL_HIGH:
        return "exceeded"      # 摄入超标
    if ratio >= CAL_LOW:
        return "met"
    return "missed"            # 摄入不足


def expected_weight(start_weight, goal_type, start_date, log_date):
    """当天期望体重 = 起始体重 + 每周变化 × 已过天数 ÷ 7。

    log_date 早于 start_date（周期开始之前）时按 0 天算，即期望体重 = 起始体重。
    """
    days = max((log_date - start_date).days, 0)
    return start_weight + weekly_weight_change(goal_type) * days / 7


def score_weight(actual, expected, goal_type):
    diff = round(actual - expected, 4)
    if goal_type == "lose_weight":
        if diff <= WEIGHT_LOSE_EXCEED:
            return "exceeded"
        if diff <= WEIGHT_LOSE_MET:
            return "met"
        return "missed"
    if goal_type == "gain_weight":
        if diff >= WEIGHT_GAIN_EXCEED:
            return "exceeded"
        if diff >= WEIGHT_GAIN_MET:
            return "met"
        return "missed"
    # maintain：没有"超额"，只看偏差大不大
    return "met" if abs(diff) <= WEIGHT_MAINTAIN_TOLERANCE else "missed"


def tone_for(metric, status, goal_type):
    """met 一律 good；missed 一律 bad；exceeded 默认 good，
    唯独"热量超标且目标不是增重"是 warn。"""
    if status == "met":
        return "good"
    if status == "missed":
        return "bad"
    if metric == "calories" and goal_type != "gain_weight":
        return "warn"
    return "good"


def _score(metric, status, goal_type):
    return {"status": status, "tone": tone_for(metric, status, goal_type)}


def build_log_out(profile, log):
    """把"档案 + 当天记录"拼成接口返回的字典：记录原值 + 目标 + 三项打分 + 得分。

    profile / log 只要有对应属性就行（数据库对象或测试里随手造的对象都可以）。
    没填的指标（体重、热量）不打分，也不计入分母。
    """
    goal = profile.goal_type
    cal_target = daily_calories(profile.gender, profile.age, profile.height_cm,
                                profile.weight_kg, goal)
    exercise_target = daily_exercise_minutes(goal)
    weight_target = expected_weight(profile.weight_kg, goal, profile.start_date, log.log_date)

    scores = {"weight": None, "exercise": None, "calories": None}
    if log.weight_kg is not None:
        scores["weight"] = _score("weight", score_weight(log.weight_kg, weight_target, goal), goal)
    # 运动时间默认 0，所以运动总是要打分的
    eff = effective_minutes(log.exercise_minutes, log.exercise_intensity)
    scores["exercise"] = _score("exercise", score_exercise(eff, exercise_target), goal)
    if log.calories_in is not None:
        scores["calories"] = _score("calories", score_calories(log.calories_in, cal_target), goal)

    given = [s for s in scores.values() if s is not None]
    return {
        "log_date": log.log_date,
        "weight_kg": log.weight_kg,
        "exercise_minutes": log.exercise_minutes,
        "exercise_intensity": log.exercise_intensity,
        "exercise_type": log.exercise_type,
        "calories_in": log.calories_in,
        "targets": {
            "weight_kg": round(weight_target, 2),
            "exercise_effective_minutes": exercise_target,
            "calories": cal_target,
        },
        "scores": scores,
        "points": sum(1 for s in given if s["tone"] == "good"),
        "scored": len(given),
    }
