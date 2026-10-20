"""Начальные данные: роли, глобальные категории и (по желанию) администратор."""
import os

from sqlalchemy.orm import Session

from .models import Category, Role, User
from .security import hash_password

DEFAULT_CATEGORIES = [
    ("Еда", "🍔"),
    ("Транспорт", "🚌"),
    ("Учёба", "📚"),
    ("Развлечения", "🎬"),
    ("Подписки", "📱"),
    ("Переводы", "💸"),
    ("Другое", "🧾"),
]


def seed(db: Session) -> None:
    for name in ("student", "admin"):
        if db.query(Role).filter_by(name=name).first() is None:
            db.add(Role(name=name))
    db.commit()

    # Добавляем только отсутствующие, чтобы новые категории появлялись и в уже работающей базе
    existing = {c.name for c in db.query(Category).filter(Category.user_id.is_(None)).all()}
    for name, icon in DEFAULT_CATEGORIES:
        if name not in existing:
            db.add(Category(name=name, icon=icon, user_id=None))
    db.commit()

    # Администратор создаётся только если заданы переменные окружения:
    # ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=ChangeMe123
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    if admin_email and admin_password and db.query(User).filter_by(email=admin_email).first() is None:
        admin_role = db.query(Role).filter_by(name="admin").one()
        db.add(
            User(
                email=admin_email,
                password_hash=hash_password(admin_password),
                full_name="Administrator",
                role_id=admin_role.id,
            )
        )
        db.commit()
