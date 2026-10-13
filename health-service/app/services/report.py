"""周期报告：把一个监测周期内的记录整理成「曲线图数据 + 汇总数字」。

build_report 是纯函数：不读数据库。记录和 SQL 聚合结果都由路由传进来，
这样不启动 server 也能直接测试。
"""

from datetime import timedelta

from app.services.scoring import build_log_out, expected_weight
from app.services.standards import (
    daily_calories,
    daily_exercise_minutes,
    effective_minutes,
    sleep_range,
)

METRICS = ("weight", "exercise", "calories", "sleep")


def cycle_info(profile, today):
    start = profile.start_date
    end = start + timedelta(days=profile.cycle_days - 1)
    elapsed = (today - start).days + 1
    return {
        "start_date": start,
        "end_date": end,
        "days": profile.cycle_days,
        # 第几天：周期还没开始是 0，结束后不超过 cycle_days
        "elapsed_days": max(0, min(elapsed, profile.cycle_days)),
        "is_finished": today > end,      # 第 30 天当天还不算结束
    }


def build_report(profile, logs, today, aggregates=None):
    """logs：周期内的记录（有 log_date 等属性的对象）；
    aggregates：SQL 聚合结果 {logged_days, avg_calories, total_exercise_minutes, avg_sleep_hours}，
    不传就用 Python 自己算（测试里方便）。"""
    cycle = cycle_info(profile, today)
    start = cycle["start_date"]
    by_date = {log.log_date: log for log in logs}

    goal = profile.goal_type
    cal_target = daily_calories(profile.gender, profile.age, profile.height_cm,
                                profile.weight_kg, goal)
    ex_target = daily_exercise_minutes(goal)
    sleep_lo, sleep_hi = sleep_range(profile.age)

    series = []
    for i in range(profile.cycle_days):
        day = start + timedelta(days=i)
        log = by_date.get(day)
        series.append({
            "date": day,
            "weight_kg": log.weight_kg if log else None,
            "target_weight_kg": round(expected_weight(profile.weight_kg, goal, start, day), 2),
            "exercise_effective_min": (
                effective_minutes(log.exercise_minutes, log.exercise_intensity) if log else None),
            "target_exercise_min": ex_target,
            "calories_in": log.calories_in if log else None,
            "target_calories": cal_target,
            "sleep_hours": log.sleep_hours if log else None,
            "target_sleep_min_hours": sleep_lo,
            "target_sleep_max_hours": sleep_hi,
        })

    # 给每条记录打分，统计得分和各项 超额/完成/未完成 次数
    counts = {m: {"exceeded": 0, "met": 0, "missed": 0} for m in METRICS}
    points = scored = 0
    for log in logs:
        out = build_log_out(profile, log)
        points += out["points"]
        scored += out["scored"]
        for metric, score in out["scores"].items():
            if score is not None:
                counts[metric][score["status"]] += 1

    if aggregates is None:
        cal = [l.calories_in for l in logs if l.calories_in is not None]
        sleep = [l.sleep_hours for l in logs if l.sleep_hours is not None]
        aggregates = {
            "logged_days": len(logs),
            "avg_calories": sum(cal) / len(cal) if cal else None,
            "total_exercise_minutes": sum(l.exercise_minutes for l in logs),
            "avg_sleep_hours": sum(sleep) / len(sleep) if sleep else None,
        }

    weights = [l.weight_kg for l in sorted(logs, key=lambda l: l.log_date) if l.weight_kg is not None]
    avg_cal = aggregates["avg_calories"]
    avg_sleep = aggregates["avg_sleep_hours"]
    return {
        "cycle": cycle,
        "series": series,
        "summary": {
            "logged_days": aggregates["logged_days"],
            "points": points,
            "scored": scored,
            # 没有任何打分项时是 None，不是 0，也不报错（分母为 0）
            "completion_rate_pct": round(points / scored * 100, 1) if scored else None,
            "avg_calories": None if avg_cal is None else round(avg_cal),
            "total_exercise_minutes": aggregates["total_exercise_minutes"] or 0,
            "weight_change_kg": round(weights[-1] - weights[0], 1) if len(weights) >= 2 else None,
            "avg_sleep_hours": None if avg_sleep is None else round(avg_sleep, 1),
            "status_counts": counts,
        },
    }
