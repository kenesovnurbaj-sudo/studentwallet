"""Мелкие помощники для работы с людьми в долгах."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import User
from .schemas import UserBrief


def display_name(user: User) -> str:
    return user.full_name or user.email.split("@")[0]


def brief(user: User) -> UserBrief:
    return UserBrief(id=user.id, name=display_name(user), email=user.email)


def find_users_by_email(db: Session, emails) -> dict[str, User]:
    """Возвращает {email в нижнем регистре: пользователь} для найденных и не заблокированных."""
    wanted = [e.lower() for e in emails]
    if not wanted:
        return {}
    users = db.query(User).filter(func.lower(User.email).in_(wanted), User.is_blocked.is_(False)).all()
    return {u.email.lower(): u for u in users}
