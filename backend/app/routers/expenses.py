from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, visible_category
from ..models import Expense, User
from ..schemas import ExpenseCreate, ExpenseOut, ExpenseUpdate

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


def _get_own_expense(db: Session, user: User, expense_id: int) -> Expense:
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    if expense.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your expense")
    return expense


@router.get("", response_model=list[ExpenseOut])
def list_expenses(
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Expense).filter(Expense.user_id == user.id)
    if date_from:
        query = query.filter(Expense.spent_at >= date_from)
    if date_to:
        query = query.filter(Expense.spent_at <= date_to)
    if category_id:
        query = query.filter(Expense.category_id == category_id)
    return query.order_by(Expense.spent_at.desc(), Expense.id.desc()).all()


@router.post("", response_model=ExpenseOut, status_code=201)
def create_expense(
    data: ExpenseCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    visible_category(db, user, data.category_id)
    expense = Expense(user_id=user.id, **data.model_dump())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.put("/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int,
    data: ExpenseUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expense = _get_own_expense(db, user, expense_id)
    changes = data.model_dump(exclude_unset=True)
    if "category_id" in changes and changes["category_id"] is not None:
        visible_category(db, user, changes["category_id"])
    for field, value in changes.items():
        if value is not None:
            setattr(expense, field, value)
    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/{expense_id}", status_code=204)
def delete_expense(
    expense_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expense = _get_own_expense(db, user, expense_id)
    db.delete(expense)
    db.commit()
