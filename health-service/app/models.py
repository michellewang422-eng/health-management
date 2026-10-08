# Column：声明"表里的一列"；Integer/String/Float/Date/DateTime：这一列存什么类型的数据
from datetime import date
# UniqueConstraint：联合唯一约束（多列合起来不能重复）
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, UniqueConstraint
# func.now()：让"数据库自己"在写入时填上当前时间（而不是 Python 填）
from sqlalchemy.sql import func

# Base 来自 database.py。继承它的类 = 登记到"总登记处"，create_all 才知道要建这张表
from app.database import Base


# HealthProfile 这个类 ↔ 数据库里的 health_profiles 这张表
# 一个 HealthProfile 对象 ↔ 表里的一行；类里每个 Column ↔ 表里的一列
class HealthProfile(Base):
    __tablename__ = "health_profiles"

    # primary_key=True：主键，每行的"身份证"，不能重复；SQLite 会自动从 1 开始编号
    id = Column(Integer, primary_key=True)

    # 只存数字，对应 User-management-service 的 users.id。
    # 不设外键：两个服务用的是两个不同的数据库文件，数据库没法跨文件检查，
    # "这个用户是否存在"要靠 PR-03 里的代码去问对方服务。
    # unique=True：一个用户只能有一份档案；index=True：按 user_id 查找更快
    user_id = Column(Integer, unique=True, nullable=False, index=True)

    # ---- 必填：nullable=False 的列，不给值就会报错 ----
    age = Column(Integer, nullable=False)
    gender = Column(String, nullable=False)
    height_cm = Column(Float, nullable=False)
    weight_kg = Column(Float, nullable=False)  # 同时也是"周期起始体重"

    # ---- 选填：不写 nullable=False 就允许为空（NULL，Python 里是 None）----
    baseline_glucose_mgdl = Column(Float)
    baseline_cholesterol_mgdl = Column(Float)
    baseline_systolic = Column(Integer)
    baseline_diastolic = Column(Integer)

    # default=...：Python 这边没给值时，SQLAlchemy 在插入前自动补上
    goal_type = Column(String, nullable=False, default="maintain")
    goal_note = Column(String)
    cycle_days = Column(Integer, nullable=False, default=30)  # 监测周期默认 30 天
    # default=date.today：注意不加括号——传的是"函数本身"，每次插入时才调用，
    # 写成 date.today() 的话，日期会在程序启动那一刻就固定死
    start_date = Column(Date, nullable=False, default=date.today)

    # server_default：由数据库填；onupdate：每次 UPDATE 这一行时自动刷新
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# DailyLog ↔ daily_logs 表：用户每天打一次卡，一人一天一行
class DailyLog(Base):
    __tablename__ = "daily_logs"
    # 联合唯一：(user_id, log_date) 合起来不能重复。
    # user_id 可以重复（一个人有很多天），log_date 也可以重复（很多人同一天），
    # 但"同一个人的同一天"只能有一行
    __table_args__ = (UniqueConstraint("user_id", "log_date"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    log_date = Column(Date, nullable=False)
    weight_kg = Column(Float)                                        # 选填
    # default 是 SQLAlchemy 在 Python 这边补的；server_default 是写进数据库表结构里的默认值。
    # 两个都写，这样绕过 Python、直接用 sqlite3 手写 INSERT 时，没写的列也有默认值
    exercise_minutes = Column(Integer, nullable=False, default=0, server_default="0")
    exercise_intensity = Column(String, nullable=False, default="moderate", server_default="moderate")
    exercise_type = Column(String)                                   # 如"快走"，选填
    calories_in = Column(Integer)                                    # 选填
