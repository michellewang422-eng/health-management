from datetime import date, datetime
# Literal["a", "b"]：这个字段只能是列出来的几个值之一
from typing import Literal, Optional

# Field(ge=, le=)：限制数字范围（ge = 大于等于，le = 小于等于）
# model_validator：校验"多个字段之间的关系"（单个字段的 Field 做不到）
from pydantic import BaseModel, ConfigDict, Field, model_validator


# ProfileIn：用户"可以编辑"的那些字段（建档和更新都用它）。
# 必填项不给默认值（不传就 422），选填项默认 None。
# 请求进来时 Pydantic 会自动按这里的规则检查，不合法直接返回 422，
# 路由函数里的代码根本不会被执行——这就是"服务端校验是真正的防线"。
class ProfileIn(BaseModel):
    # ---- 必填 ----
    age: int = Field(ge=18, le=100)
    gender: Literal["male", "female"]
    height_cm: float = Field(ge=100, le=250)
    weight_kg: float = Field(ge=30, le=300)
    # ---- 选填 ----
    baseline_glucose_mgdl: Optional[float] = Field(default=None, ge=40, le=600)
    baseline_cholesterol_mgdl: Optional[float] = Field(default=None, ge=80, le=500)
    baseline_systolic: Optional[int] = Field(default=None, ge=70, le=250)
    baseline_diastolic: Optional[int] = Field(default=None, ge=40, le=150)
    goal_type: Literal["lose_weight", "maintain", "gain_weight"] = "maintain"
    goal_note: Optional[str] = Field(default=None, max_length=200)
    cycle_days: int = Field(default=30, ge=7, le=365)   # 没填就是 30 天
    start_date: Optional[date] = None                   # 没填就是建档当天

    # mode="after"：等上面每个字段各自校验通过之后，再检查字段之间的关系
    @model_validator(mode="after")
    def check_blood_pressure(self):
        s, d = self.baseline_systolic, self.baseline_diastolic
        # (s is None) != (d is None)：一个有、一个没有 = 只填了一半
        if (s is None) != (d is None):
            raise ValueError("血压必须同时提供收缩压和舒张压")
        if s is not None and s <= d:
            raise ValueError("收缩压必须大于舒张压")
        return self


# ProfileCreate：建档时多一个 user_id（谁的档案）。
# 更新时不需要它，因为 user_id 已经在 URL 里：PUT /profiles/{user_id}
class ProfileCreate(ProfileIn):
    user_id: int = Field(ge=1)


# ProfileOut：返回给前端的完整数据，多了数据库生成的 id 和时间戳
class ProfileOut(ProfileCreate):
    id: int
    start_date: date          # 返回时一定有值（覆盖掉父类的 Optional）
    created_at: datetime
    updated_at: datetime

    # from_attributes=True：允许直接从 SQLAlchemy 对象的属性读取数据（见 User-management-service 的同名设置）
    model_config = ConfigDict(from_attributes=True)
