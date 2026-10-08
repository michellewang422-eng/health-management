from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import HealthProfile
from app.schemas import ProfileCreate, ProfileIn, ProfileOut
from app.services.user_client import UserServiceUnavailable, get_user_checker

# prefix="/profiles"：这个 router 里所有路径都自动加上 /profiles 前缀
router = APIRouter(prefix="/profiles", tags=["profiles"])


# 按 user_id 找档案，找不到就直接抛 404。其它接口（读/改/删，以及后面的标准、日志）都会复用它
def get_profile_or_404(db: Session, user_id: int) -> HealthProfile:
    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="健康档案不存在")
    return profile


# status_code=201：创建成功用 201 Created（而不是默认的 200）
@router.post("", response_model=ProfileOut, status_code=201)
def create_profile(
    payload: ProfileCreate,
    db: Session = Depends(get_db),
    user_exists=Depends(get_user_checker),
):
    # 第 1 关：问 User-management-service 这个用户存不存在。
    # 两个库是两个文件，数据库没法用外键帮我们拦住"没有主人的档案"，只能由代码来保证
    try:
        found = user_exists(payload.user_id)
    except UserServiceUnavailable:
        raise HTTPException(status_code=502, detail="用户服务暂时不可用")
    if not found:
        raise HTTPException(status_code=404, detail="用户不存在，请先注册")

    # 第 2 关：一个用户只能有一份档案（数据库的 UNIQUE 是最后防线，这里提前给出友好提示）
    if db.query(HealthProfile).filter(HealthProfile.user_id == payload.user_id).first():
        raise HTTPException(status_code=409, detail="该用户已建过健康档案")

    # exclude_none：值是 None 的字段不传给模型，这样 start_date 没传时，
    # 模型里 default=date.today 才会生效
    profile = HealthProfile(**payload.model_dump(exclude_none=True))
    db.add(profile)
    db.commit()
    db.refresh(profile)   # 把数据库生成的 id、时间戳读回对象
    return profile


@router.get("/{user_id}", response_model=ProfileOut)
def read_profile(user_id: int, db: Session = Depends(get_db)):
    return get_profile_or_404(db, user_id)


# PUT = 整条替换：请求里的每个字段都会写进去
@router.put("/{user_id}", response_model=ProfileOut)
def update_profile(user_id: int, payload: ProfileIn, db: Session = Depends(get_db)):
    profile = get_profile_or_404(db, user_id)
    for key, value in payload.model_dump().items():
        if key == "start_date" and value is None:
            continue                  # 没传开始日期 = 保持原来的
        setattr(profile, key, value)  # 选填项传 None = 清空
    db.commit()
    db.refresh(profile)
    return profile


# 204 No Content：成功了，但没有内容要返回
@router.delete("/{user_id}", status_code=204)
def delete_profile(user_id: int, db: Session = Depends(get_db)):
    profile = get_profile_or_404(db, user_id)
    db.delete(profile)
    db.commit()
