from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DailyLog
from app.routers.profiles import get_profile_or_404
from app.schemas import LogIn, LogOut
from app.services.scoring import build_log_out

# 日志属于某个用户的档案，所以路径挂在 /profiles/{user_id}/logs 下
router = APIRouter(prefix="/profiles", tags=["logs"])


def get_log_or_404(db: Session, user_id: int, log_date: date) -> DailyLog:
    log = db.query(DailyLog).filter_by(user_id=user_id, log_date=log_date).first()
    if not log:
        raise HTTPException(status_code=404, detail="当天没有记录")
    return log


# PUT = "放在这里"：这天没有记录就新建，有就覆盖。这种"有则改、无则增"叫 upsert。
# 同一天提交两次不会报错，也不会出现两行
@router.put("/{user_id}/logs/{log_date}", response_model=LogOut)
def upsert_log(user_id: int, log_date: date, payload: LogIn, db: Session = Depends(get_db)):
    profile = get_profile_or_404(db, user_id)
    if log_date > date.today():
        raise HTTPException(status_code=422, detail="不能记录未来的日期")

    log = db.query(DailyLog).filter_by(user_id=user_id, log_date=log_date).first()
    if log is None:
        log = DailyLog(user_id=user_id, log_date=log_date)
        db.add(log)
    for key, value in payload.model_dump().items():
        setattr(log, key, value)
    db.commit()
    db.refresh(log)
    return build_log_out(profile, log)    # 附上 targets / scores / points


# Query(alias="from")：URL 里写 ?from=...，但 from 是 Python 关键字不能当变量名，
# 所以变量叫 from_，用 alias 告诉 FastAPI 对外的名字是 from
@router.get("/{user_id}/logs", response_model=List[LogOut])
def list_logs(
    user_id: int,
    from_: Optional[date] = Query(default=None, alias="from"),
    to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    profile = get_profile_or_404(db, user_id)
    query = db.query(DailyLog).filter(DailyLog.user_id == user_id)
    if from_ is not None:
        query = query.filter(DailyLog.log_date >= from_)   # 包含起始日
    if to is not None:
        query = query.filter(DailyLog.log_date <= to)      # 包含结束日
    logs = query.order_by(DailyLog.log_date).all()          # 从早到晚
    return [build_log_out(profile, log) for log in logs]


@router.delete("/{user_id}/logs/{log_date}", status_code=204)
def delete_log(user_id: int, log_date: date, db: Session = Depends(get_db)):
    get_profile_or_404(db, user_id)
    log = get_log_or_404(db, user_id, log_date)
    db.delete(log)
    db.commit()
