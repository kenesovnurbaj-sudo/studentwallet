from datetime import date
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Category, Expense, User
from .imports import remember_choices
from ..schemas import BulkCategoryChange, BulkCategoryResult, ExpenseCreate, ExpenseOut, ExpenseUpdate

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


def _check_category(db: Session, user: User, category_id: int) -> None:
    exists = (
        db.query(Category)
        .filter(Category.id == category_id, or_(Category.user_id.is_(None), Category.user_id == user.id))
        .first()
    )
    if exists is None:
        raise HTTPException(status_code=400, detail="Unknown category")


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
    _check_category(db, user, data.category_id)
    expense = Expense(user_id=user.id, **data.model_dump())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.post("/bulk-category", response_model=BulkCategoryResult)
def bulk_change_category(
    data: BulkCategoryChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Меняет категорию сразу у нескольких своих записей. Выбор запоминается для будущих импортов выписки."""
    _check_category(db, user, data.category_id)
    ids = set(data.ids)
    items = db.query(Expense).filter(Expense.id.in_(ids)).all()
    if len(items) != len(ids):
        raise HTTPException(status_code=404, detail="Expense not found")
    if any(e.user_id != user.id for e in items):
        raise HTTPException(status_code=403, detail="Not your expense")
    for e in items:
        e.category_id = data.category_id
    remember_choices(
        db, user, [SimpleNamespace(note=e.note, type=e.type, category_id=data.category_id) for e in items]
    )
    db.commit()
    return BulkCategoryResult(updated=len(items))


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
        _check_category(db, user, changes["category_id"])
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
