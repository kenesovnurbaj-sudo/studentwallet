from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .database import get_db
from .models import Category, User
from .security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = decode_access_token(creds.credentials)
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if user.is_blocked:
        raise HTTPException(status_code=403, detail="User is blocked")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role.name != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def visible_category(db: Session, user: User, category_id: int) -> Category:
    """Категория, которую пользователь имеет право использовать: глобальная или своя личная.

    Чужая личная и несуществующая категория дают одинаковый ответ 400,
    чтобы нельзя было перебором узнать id чужих категорий.
    """
    category = (
        db.query(Category)
        .filter(Category.id == category_id, or_(Category.user_id.is_(None), Category.user_id == user.id))
        .first()
    )
    if category is None:
        raise HTTPException(status_code=400, detail="Unknown category")
    return category
