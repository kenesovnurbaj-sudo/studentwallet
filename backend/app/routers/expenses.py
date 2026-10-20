from datetime import date
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, visible_category
from ..models import Category, Expense, ExpenseShare, User
from ..people import display_name, find_users_by_email
from ..schemas import (
    BulkCategoryChange,
    BulkCategoryResult,
    ExpenseCreate,
    ExpenseOut,
    ExpenseUpdate,
    SplitIn,
    SplitLine,
    SplitPreviewIn,
    SplitPreviewOut,
)
from ..splitting import SplitError, SplitResult, compute_split, from_cents, to_cents
from .imports import remember_choices

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


def _get_own_expense(db: Session, user: User, expense_id: int) -> Expense:
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    if expense.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your expense")
    return expense


def _compute(user: User, amount: float | None, split: SplitIn) -> SplitResult:
    friends = [(p.email, to_cents(p.amount) if p.amount is not None else None) for p in split.participants]
    items = [(to_cents(i.price), i.eaters) for i in split.items]
    try:
        return compute_split(
            split.mode,
            to_cents(amount) if amount is not None else None,
            friends,
            items,
            split.tip_percent,
            payer_email=user.email,
        )
    except SplitError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/split-preview", response_model=SplitPreviewOut)
def split_preview(
    data: SplitPreviewIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Показывает, кто сколько должен, ничего не сохраняя. Сайт вызывает его, пока вы заполняете форму."""
    result = _compute(user, data.amount, data.split)
    found = find_users_by_email(db, result.friends.keys())
    lines = [
        SplitLine(
            email=email,
            name=display_name(found[email]) if email in found else email,
            amount=from_cents(cents),
            found=email in found,
        )
        for email, cents in result.friends.items()
    ]
    return SplitPreviewOut(total=from_cents(result.total), service=from_cents(result.service), my_share=from_cents(result.mine), lines=lines)


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

    if data.split is None:
        expense = Expense(
            user_id=user.id,
            category_id=data.category_id,
            amount=data.amount,
            type=data.type,
            note=data.note,
            spent_at=data.spent_at,
            source=data.source,
        )
        db.add(expense)
        db.commit()
        db.refresh(expense)
        return expense

    # Вы заплатили за друзей: ваша доля идёт в ваши расходы, доли друзей становятся их долгами вам.
    if data.type != "expense":
        raise HTTPException(status_code=400, detail="Only expenses can be split")
    result = _compute(user, data.amount, data.split)
    friends = find_users_by_email(db, result.friends.keys())
    missing = [email for email in result.friends if email not in friends]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Not found on the site: {', '.join(missing)}. Ask your friends to register",
        )

    expense = Expense(
        user_id=user.id,
        category_id=data.category_id,
        amount=from_cents(result.mine),
        paid_total=from_cents(result.total),
        type="expense",
        note=data.note,
        spent_at=data.spent_at,
        source=data.source,
    )
    db.add(expense)
    db.flush()  # нужен id траты для долгов
    for email, cents in result.friends.items():
        db.add(
            ExpenseShare(
                expense_id=expense.id,
                payer_id=user.id,
                debtor_id=friends[email].id,
                amount=from_cents(cents),
            )
        )
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
    visible_category(db, user, data.category_id)
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
    if expense.shares:
        # Сумма и тип связаны с долгами друзей, поэтому у разделённой траты их менять нельзя.
        amount_changed = changes.get("amount") is not None and abs(float(expense.amount) - float(changes["amount"])) > 0.005
        type_changed = changes.get("type") is not None and changes["type"] != expense.type
        if amount_changed or type_changed:
            raise HTTPException(
                status_code=409,
                detail="The amount of a split expense cannot be changed. Delete it and create it again",
            )
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
    if any(share.status != "pending" for share in expense.shares):
        raise HTTPException(
            status_code=409,
            detail="This expense cannot be deleted: friends have already marked it as paid or paid it back",
        )
    db.delete(expense)
    db.commit()
