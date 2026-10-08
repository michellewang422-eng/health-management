"""参考标准引擎：根据年龄、性别、身高、体重、目标，算出各种"该达到多少"。

这个文件里全是**纯函数**：同样的输入永远得到同样的输出，不读数据库、不联网。
好处是测试时不用启动 server、不用准备数据库，直接调用函数对比数字就行。

所有"阈值"都集中写在文件开头的常量里：以后想改标准，只改常量，不用动逻辑。
说明：血糖、血压、总胆固醇的分类标准不按年龄性别分组；真正随年龄性别变的是
热量、运动建议、健康体重范围和 HDL。仅供学习参考，不能替代医生诊断。
"""

import math

# ---------- 常量 ----------
ACTIVITY_FACTOR = 1.375          # 每日总消耗 = 基础代谢 × 活动系数（轻度活动）
CALORIE_ADJUST = {"lose_weight": -500, "maintain": 0, "gain_weight": 300}
CALORIE_FLOOR = {"male": 1500, "female": 1200}   # 每日热量的安全下限
WEEKLY_WEIGHT_CHANGE = {"lose_weight": -0.5, "maintain": 0.0, "gain_weight": 0.25}  # kg/周
DAILY_EXERCISE_MINUTES = {"lose_weight": 45, "maintain": 30, "gain_weight": 30}
INTENSITY_FACTOR = {"low": 0.5, "moderate": 1, "high": 2}   # 折算成"中等强度分钟"

BMI_HEALTHY_MIN, BMI_HEALTHY_MAX = 18.5, 24.9
DISCLAIMER = "仅供学习参考，不能替代医生诊断。"


# ---------- 身体指标 ----------
def calc_bmi(weight_kg, height_cm):
    """BMI = 体重(kg) ÷ 身高(m)²，保留 1 位小数。"""
    m = height_cm / 100
    return round(weight_kg / (m * m), 1)


def classify_bmi(bmi):
    # 注意传进来的是已经保留 1 位小数的 BMI，这样判断结果和页面上看到的数字一致
    if bmi < 18.5:
        return "underweight"
    if bmi < 25:
        return "normal"
    if bmi < 30:
        return "overweight"
    return "obese"


def healthy_weight_range(height_cm):
    """BMI 在 18.5 到 24.9 之间对应的体重范围（kg，保留 1 位小数）。"""
    m = height_cm / 100
    return [round(BMI_HEALTHY_MIN * m * m, 1), round(BMI_HEALTHY_MAX * m * m, 1)]


# ---------- 热量 ----------
def calc_bmr(gender, age, height_cm, weight_kg):
    """基础代谢率（Mifflin-St Jeor 公式）：躺着不动一天消耗多少千卡。"""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if gender == "male" else base - 161


def daily_calories(gender, age, height_cm, weight_kg, goal_type):
    """每日建议摄入热量：总消耗按目标加减，不低于安全下限，最后取整到 10 的倍数。"""
    tdee = calc_bmr(gender, age, height_cm, weight_kg) * ACTIVITY_FACTOR
    target = max(tdee + CALORIE_ADJUST[goal_type], CALORIE_FLOOR[gender])
    # 四舍五入到 10 的倍数（避免"假精确"）。不用 round()：它遇到 .5 会"取偶数"，
    # 和我们说的"四舍五入"不一致
    return int(math.floor(target / 10 + 0.5)) * 10


def weekly_weight_change(goal_type):
    """每周目标体重变化（kg）。"""
    return WEEKLY_WEIGHT_CHANGE[goal_type]


# ---------- 运动 ----------
def daily_exercise_minutes(goal_type):
    """每天需要的"中等强度分钟数"。"""
    return DAILY_EXERCISE_MINUTES[goal_type]


def effective_minutes(minutes, intensity):
    """把实际运动时间折算成中等强度分钟：1 分钟高强度 = 2 分钟中等强度。"""
    return minutes * INTENSITY_FACTOR[intensity]


def suggested_exercises(age):
    """按年龄段推荐运动项目。"""
    if age < 40:
        return ["快走", "慢跑", "骑行", "游泳", "力量训练每周 2 天"]
    if age < 65:
        return ["快走", "游泳", "骑行", "力量训练每周 2 天"]
    return ["散步", "太极", "平衡训练", "轻量力量训练"]


# ---------- 原始指标的分类 ----------
def classify_glucose(value):
    """空腹血糖 mg/dL：< 100 正常；100–125 偏高；≥ 126 高。"""
    if value < 100:
        return "normal"
    if value < 126:
        return "elevated"
    return "high"


def classify_blood_pressure(systolic, diastolic):
    """血压 mmHg。判断顺序必须"从重到轻"：先看最严重的，再往下，不然重的会被轻的盖掉。"""
    if systolic > 180 or diastolic > 120:
        return "crisis"
    if systolic >= 140 or diastolic >= 90:
        return "stage2"
    if systolic >= 130 or diastolic >= 80:
        return "stage1"
    if systolic >= 120:          # 走到这里舒张压一定 < 80
        return "elevated"
    return "normal"


def classify_cholesterol(value):
    """总胆固醇 mg/dL：< 200 理想；200–239 边缘偏高；≥ 240 高。"""
    if value < 200:
        return "ideal"
    if value < 240:
        return "borderline"
    return "high"


def hdl_reference(gender):
    """HDL（好胆固醇）参考值：男 ≥ 40，女 ≥ 50 mg/dL。"""
    return ">= 40" if gender == "male" else ">= 50"


# ---------- 拼成一个完整结果 ----------
def build_standards(profile):
    """把上面所有结果拼成一个字典，作为 GET /profiles/{id}/standards 的返回值。

    profile 只要有 age/gender/height_cm/weight_kg/goal_type 和几个 baseline_* 属性
    就行（数据库里的 HealthProfile 对象，或测试里随手造的对象都可以）。
    用户没填的原始指标，对应的评估就是 None，不报错。
    """
    bmi = calc_bmi(profile.weight_kg, profile.height_cm)

    glucose = profile.baseline_glucose_mgdl
    cholesterol = profile.baseline_cholesterol_mgdl
    systolic, diastolic = profile.baseline_systolic, profile.baseline_diastolic

    return {
        "bmi": bmi,
        "bmi_category": classify_bmi(bmi),
        "healthy_weight_kg": healthy_weight_range(profile.height_cm),
        "bmr": round(calc_bmr(profile.gender, profile.age, profile.height_cm, profile.weight_kg)),
        "daily_calories": daily_calories(
            profile.gender, profile.age, profile.height_cm, profile.weight_kg, profile.goal_type
        ),
        "weekly_weight_change_kg": weekly_weight_change(profile.goal_type),
        "exercise": {
            "daily_effective_minutes": daily_exercise_minutes(profile.goal_type),
            "suggested": suggested_exercises(profile.age),
        },
        "reference_ranges": {
            "fasting_glucose_mgdl": "< 100",
            "blood_pressure_mmhg": "< 120/80",
            "total_cholesterol_mgdl": "< 200",
            "hdl_mgdl": hdl_reference(profile.gender),
            "ldl_mgdl": "< 100",
            "triglycerides_mgdl": "< 150",
        },
        "baseline_assessment": {
            "glucose": None if glucose is None else classify_glucose(glucose),
            "blood_pressure": (
                None if systolic is None or diastolic is None
                else classify_blood_pressure(systolic, diastolic)
            ),
            "cholesterol": None if cholesterol is None else classify_cholesterol(cholesterol),
        },
        "disclaimer": DISCLAIMER,
    }
