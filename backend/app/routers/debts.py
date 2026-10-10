from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Expense, ExpenseShare, User
from ..people import brief, display_name
from ..schemas import DebtSummary, MarkPaidIn, ShareOut
from .expenses import _check_category

router = APIRouter(prefix="/api", tags=["debts"])

OPEN_STATUSES = ("pending", "marked_paid")


def _share_out(share: ExpenseShare) -> ShareOut:
    expense = share.expense
    return ShareOut(
        id=share.id,
        amount=float(share.amount),
        status=share.status,
        note=expense.note,
        spent_at=expense.spent_at,
        paid_total=float(expense.paid_total) if expense.paid_total is not None else None,
        payer=brief(share.payer),
        debtor=brief(share.debtor),
        created_at=share.created_at,
        marked_at=share.marked_at,
        settled_at=share.settled_at,
    )


def _get_share(db: Session, user: User, share_id: int, *, as_role: str) -> ExpenseShare:
    """Находит долг. Посторонний человек получает 404, чтобы не узнать, что такой долг есть."""
    share = db.get(ExpenseShare, share_id)
    if share is None or user.id not in (share.payer_id, share.debtor_id):
        raise HTTPException(status_code=404, detail="Долг не найден")
    if as_role == "payer" and share.payer_id != user.id:
        raise HTTPException(status_code=403, detail="Это действие доступно только тому, кто платил за счёт")
    if as_role == "debtor" and share.debtor_id != user.id:
        raise HTTPException(status_code=403, detail="Это действие доступно только тому, кто должен")
    return share


@router.get("/debts/owed-to-me", response_model=list[ShareOut])
def owed_to_me(
    include_settled: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Кто и сколько должен вам."""
    query = db.query(ExpenseShare).filter(ExpenseShare.payer_id == user.id)
    if not include_settled:
        query = query.filter(ExpenseShare.status.in_(OPEN_STATUSES))
    return [_share_out(s) for s in query.order_by(ExpenseShare.id.desc()).all()]


@router.get("/debts/i-owe", response_model=list[ShareOut])
def i_owe(
    include_settled: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Кому и сколько должны вы."""
    query = db.query(ExpenseShare).filter(ExpenseShare.debtor_id == user.id)
    if not include_settled:
        query = query.filter(ExpenseShare.status.in_(OPEN_STATUSES))
    return [_share_out(s) for s in query.order_by(ExpenseShare.id.desc()).all()]


@router.get("/debts/summary", response_model=DebtSummary)
def debt_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owed = (
        db.query(func.coalesce(func.sum(ExpenseShare.amount), 0))
        .filter(ExpenseShare.payer_id == user.id, ExpenseShare.status.in_(OPEN_STATUSES))
        .scalar()
    )
    # Если вы уже нажали «Я оплатил», вы больше не должны, даже пока плательщик не подтвердил.
    owe = (
        db.query(func.coalesce(func.sum(ExpenseShare.amount), 0))
        .filter(ExpenseShare.debtor_id == user.id, ExpenseShare.status == "pending")
        .scalar()
    )
    to_confirm = (
        db.query(func.count(ExpenseShare.id))
        .filter(ExpenseShare.payer_id == user.id, ExpenseShare.status == "marked_paid")
        .scalar()
    )
    return DebtSummary(owed_to_me=round(float(owed), 2), i_owe=round(float(owe), 2), to_confirm=int(to_confirm))


@router.post("/shares/{share_id}/mark-paid", response_model=ShareOut)
def mark_paid(
    share_id: int,
    data: MarkPaidIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Должник нажимает «Я оплатил». Сумма записывается в его расходы, плательщику приходит запрос подтвердить."""
    share = _get_share(db, user, share_id, as_role="debtor")
    if share.status != "pending":
        raise HTTPException(status_code=409, detail="Этот долг уже отмечен как оплаченный")
    _check_category(db, user, data.category_id)

    note = f"Долг: {display_name(share.payer)}"
    if share.expense.note:
        note += f" — {share.expense.note}"
    own_expense = Expense(
        user_id=user.id,
        category_id=data.category_id,
        amount=share.amount,
        type="expense",
        note=note[:255],
        spent_at=date.today(),
        source="web",
    )
    db.add(own_expense)
    db.flush()

    share.debtor_expense_id = own_expense.id
    share.status = "marked_paid"
    share.marked_at = datetime.utcnow()
    db.commit()
    db.refresh(share)
    return _share_out(share)


@router.post("/shares/{share_id}/confirm", response_model=ShareOut)
def confirm(
    share_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Плательщик подтверждает, что деньги получил. Можно и без отметки друга (например, вернул наличными)."""
    share = _get_share(db, user, share_id, as_role="payer")
    if share.status == "settled":
        raise HTTPException(status_code=409, detail="Этот долг уже закрыт")
    share.status = "settled"
    share.settled_at = datetime.utcnow()
    db.commit()
    db.refresh(share)
    return _share_out(share)


@router.post("/shares/{share_id}/reject", response_model=ShareOut)
def reject(
    share_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Плательщик говорит «деньги не пришли»: долг снова открыт, а запись в бюджете друга удаляется."""
    share = _get_share(db, user, share_id, as_role="payer")
    if share.status != "marked_paid":
        raise HTTPException(status_code=409, detail="Отклонять нечего: друг не отмечал возврат")
    if share.debtor_expense_id is not None:
        own_expense = db.get(Expense, share.debtor_expense_id)
        if own_expense is not None:
            db.delete(own_expense)
    share.debtor_expense_id = None
    share.status = "pending"
    share.marked_at = None
    db.commit()
    db.refresh(share)
    return _share_out(share)
