from datetime import date

from fastapi import APIRouter, Depends
# func.count / func.avg / func.sum 对应 SQL 的 COUNT / AVG / SUM
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DailyLog
from app.routers.profiles import get_profile_or_404
from app.services.report import build_report, cycle_info

router = APIRouter(prefix="/profiles", tags=["report"])


@router.get("/{user_id}/report")
def read_report(user_id: int, db: Session = Depends(get_db)):
    profile = get_profile_or_404(db, user_id)
    cycle = cycle_info(profile, date.today())
    start, end = cycle["start_date"], cycle["end_date"]
    # 只统计周期内的记录（开始前、结束后的不算）
    in_cycle = (DailyLog.user_id == user_id, DailyLog.log_date.between(start, end))

    logs = db.query(DailyLog).filter(*in_cycle).order_by(DailyLog.log_date).all()
    # SQL 聚合：SELECT COUNT(id), AVG(calories_in), SUM(exercise_minutes), AVG(sleep_hours) ...
    # AVG 会自动跳过 NULL（没填的天不进分母）
    count, avg_cal, total_min, avg_sleep = (
        db.query(func.count(DailyLog.id), func.avg(DailyLog.calories_in),
                 func.sum(DailyLog.exercise_minutes), func.avg(DailyLog.sleep_hours))
        .filter(*in_cycle).one()
    )
    aggregates = {"logged_days": count, "avg_calories": avg_cal,
                  "total_exercise_minutes": total_min, "avg_sleep_hours": avg_sleep}
    return build_report(profile, logs, date.today(), aggregates)
