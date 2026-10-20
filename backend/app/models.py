"""Модели БД. Соответствуют ER-диаграмме из StudentWallet_project_plan.md (8 таблиц)."""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True)  # student | admin


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120), default="")
    currency: Mapped[str] = mapped_column(String(8), default="KZT")
    monthly_income: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    role: Mapped[Role] = relationship()


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    icon: Mapped[str] = mapped_column(String(16), default="")
    # NULL = глобальная категория (видна всем), иначе личная категория пользователя
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    type: Mapped[str] = mapped_column(String(10), default="expense")  # expense | income
    note: Mapped[str] = mapped_column(String(255), default="")
    spent_at: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    source: Mapped[str] = mapped_column(String(10), default="web")  # web | siri
    # Если вы заплатили за друзей: amount = ваша доля, paid_total = весь чек. Иначе NULL.
    paid_total: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    category: Mapped[Category] = relationship()
    shares: Mapped[list["ExpenseShare"]] = relationship(
        foreign_keys="ExpenseShare.expense_id", back_populates="expense", cascade="all, delete-orphan"
    )


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # NULL = общий лимит на месяц
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    limit_amount: Mapped[float] = mapped_column(Numeric(12, 2))
    month: Mapped[str] = mapped_column(String(7))  # формат 2026-10


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    target_amount: Mapped[float] = mapped_column(Numeric(12, 2))
    saved_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    message: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(20))  # 80pct | 100pct | goal
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ApiToken(Base):
    """Токены для Siri/Shortcuts (используются в спринте 5)."""

    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(255))
    label: Mapped[str] = mapped_column(String(60), default="Shortcuts")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MerchantRule(Base):
    """Запомненная пользователем категория для получателя из выписки («ИП NANGO» -> Еда)."""

    __tablename__ = "merchant_rules"
    __table_args__ = (UniqueConstraint("user_id", "note", name="uq_merchant_rule"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    note: Mapped[str] = mapped_column(String(255))  # описание в нижнем регистре
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))


class AppMeta(Base):
    """Служебные отметки, например какие разовые миграции данных уже выполнены."""

    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), default="")


class ExpenseShare(Base):
    """Долг друга по общему счёту: payer заплатил, debtor должен вернуть amount."""

    __tablename__ = "expense_shares"

    id: Mapped[int] = mapped_column(primary_key=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id", ondelete="CASCADE"), index=True)
    payer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    debtor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    # pending - ждёт возврата, marked_paid - друг нажал «Я оплатил», settled - плательщик подтвердил
    status: Mapped[str] = mapped_column(String(12), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    marked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # запись о расходе в бюджете друга, появляется, когда он отметил возврат
    debtor_expense_id: Mapped[int | None] = mapped_column(
        ForeignKey("expenses.id", ondelete="SET NULL"), nullable=True
    )

    expense: Mapped[Expense] = relationship(foreign_keys=[expense_id], back_populates="shares")
    payer: Mapped[User] = relationship(foreign_keys=[payer_id])
    debtor: Mapped[User] = relationship(foreign_keys=[debtor_id])
