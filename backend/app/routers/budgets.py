import calendar
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Budget, Expense, User
from ..schemas import BudgetOut, BudgetSet, BudgetSummary

router = APIRouter(prefix="/api", tags=["budgets"])

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


def _current_month() -> str:
    return date.today().strftime("%Y-%m")


def _month_bounds(month: str) -> tuple[date, date]:
    year, mon = int(month[:4]), int(month[5:7])
    last_day = calendar.monthrange(year, mon)[1]
    return date(year, mon, 1), date(year, mon, last_day)


@router.get("/budgets", response_model=list[BudgetOut])
def list_budgets(
    month: str = Query(default_factory=_current_month, pattern=MONTH_PATTERN),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(Budget).filter(Budget.user_id == user.id, Budget.month == month).all()


@router.put("/budgets", response_model=BudgetOut)
def set_budget(
    data: BudgetSet,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Создаёт или обновляет лимит на месяц (общий или по категории)."""
    budget = (
        db.query(Budget)
        .filter(
            Budget.user_id == user.id,
            Budget.month == data.month,
            Budget.category_id.is_(None) if data.category_id is None else Budget.category_id == data.category_id,
        )
        .first()
    )
    if budget is None:
        budget = Budget(user_id=user.id, month=data.month, category_id=data.category_id, limit_amount=data.limit_amount)
        db.add(budget)
    else:
        budget.limit_amount = data.limit_amount
    db.commit()
    db.refresh(budget)
    return budget


@router.get("/budget/summary", response_model=BudgetSummary)
def budget_summary(
    month: str = Query(default_factory=_current_month, pattern=MONTH_PATTERN),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Остаток общего бюджета месяца и дневной лимит. Этот эндпоинт вызывает Siri/Shortcuts."""
    budget = (
        db.query(Budget)
        .filter(Budget.user_id == user.id, Budget.month == month, Budget.category_id.is_(None))
        .first()
    )
    if budget is None:
        raise HTTPException(status_code=404, detail="No budget set for this month")

    first_day, last_day = _month_bounds(month)
    spent = (
        db.query(func.coalesce(func.sum(Expense.amount), 0))
        .filter(
            Expense.user_id == user.id,
            Expense.type == "expense",
            Expense.spent_at >= first_day,
            Expense.spent_at <= last_day,
        )
        .scalar()
    )
    limit = float(budget.limit_amount)
    spent = float(spent)
    remaining = limit - spent

    today = date.today()
    if today < first_day:
        days_left = (last_day - first_day).days + 1
    elif today > last_day:
        days_left = 0
    else:
        days_left = (last_day - today).days + 1
    daily_limit = remaining / days_left if days_left > 0 and remaining > 0 else 0.0

    return BudgetSummary(
        month=month,
        limit=round(limit, 2),
        spent=round(spent, 2),
        remaining=round(remaining, 2),
        percent_used=round(spent / limit * 100, 1),
        days_left=days_left,
        daily_limit=round(daily_limit, 2),
    )
