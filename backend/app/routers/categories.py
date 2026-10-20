from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Category, User
from ..schemas import CategoryCreate, CategoryOut

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Глобальные категории и личные категории текущего пользователя."""
    return (
        db.query(Category)
        .filter(or_(Category.user_id.is_(None), Category.user_id == user.id))
        .order_by(Category.id)
        .all()
    )


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(
    data: CategoryCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Дубликат: такое же имя среди глобальных или своих категорий, без учёта регистра.
    # Сравниваем в Python: lower() в SQLite не работает с кириллицей ("Еда" != "еда").
    wanted = data.name.casefold()
    visible = db.query(Category.name).filter(or_(Category.user_id.is_(None), Category.user_id == user.id))
    if any(name.casefold() == wanted for (name,) in visible):
        raise HTTPException(status_code=409, detail="Category already exists")

    category = Category(name=data.name, icon=data.icon, user_id=user.id)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category
