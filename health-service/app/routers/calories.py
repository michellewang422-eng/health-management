from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FoodItem
from app.schemas import CalculateIn, FoodOut
from app.services.calories import calculate

router = APIRouter(tags=["calories"])


# ORM 的 contains / like 会把关键字当"参数"绑定，不会拼进 SQL 文本，所以不会被注入；
# autoescape=True 让用户输入的 % 和 _ 只当普通字符
@router.get("/foods", response_model=List[FoodOut])
def search_foods(q: str = "", db: Session = Depends(get_db)):
    query = db.query(FoodItem)
    q = q.strip()
    if q:
        query = query.filter(
            FoodItem.name.contains(q, autoescape=True) | FoodItem.aliases.contains(q, autoescape=True))
    return query.order_by(FoodItem.name).limit(20).all()


@router.post("/calories/calculate")
def calculate_calories(payload: CalculateIn, db: Session = Depends(get_db)):
    foods = db.query(FoodItem).order_by(FoodItem.id).all()
    return calculate([i.model_dump() for i in payload.items], foods)
