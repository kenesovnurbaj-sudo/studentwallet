from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..clock import today
from ..database import get_db
from ..deps import get_current_user, visible_category
from ..models import Expense, ExpenseShare, User
from ..people import brief, display_name
from ..schemas import DebtSummary, MarkPaidIn, ShareOut

router = APIRouter(prefix="/api", tags=["debts"])

OPEN_STATUSES = ("pending", "marked_paid")
REMIND_COOLDOWN = timedelta(hours=12)  # не чаще, чтобы не донимать друга


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
        debtor=brief(share.debtor) if share.debtor is not None else None,
        debtor_name=display_name(share.debtor) if share.debtor is not None else (share.debtor_name or "Friend"),
        guest=share.debtor_id is None,
        reminded_at=share.reminded_at,
        remind_count=share.remind_count or 0,
        created_at=share.created_at,
        marked_at=share.marked_at,
        settled_at=share.settled_at,
    )


def _get_share(db: Session, user: User, share_id: int, *, as_role: str) -> ExpenseShare:
    """Находит долг. Посторонний человек получает 404, чтобы не узнать, что такой долг есть."""
    share = db.get(ExpenseShare, share_id)
    if share is None or user.id not in (share.payer_id, share.debtor_id):
        raise HTTPException(status_code=404, detail="Debt not found")
    if as_role == "payer" and share.payer_id != user.id:
        raise HTTPException(status_code=403, detail="Only the person who paid the bill can do this")
    if as_role == "debtor" and share.debtor_id != user.id:
        raise HTTPException(status_code=403, detail="Only the person who owes can do this")
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
    reminded = (
        db.query(func.count(ExpenseShare.id))
        .filter(
            ExpenseShare.debtor_id == user.id,
            ExpenseShare.status == "pending",
            ExpenseShare.reminded_at.isnot(None),
        )
        .scalar()
    )
    return DebtSummary(
        owed_to_me=round(float(owed), 2), i_owe=round(float(owe), 2), to_confirm=int(to_confirm), reminded=int(reminded)
    )


@router.post("/shares/{share_id}/remind", response_model=ShareOut)
def remind(
    share_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Плательщик напоминает другу о долге. Друг видит напоминание у себя в блоке «Debts».

    Друзьям без аккаунта напомнить в приложении нельзя: для них копируется текст сообщения."""
    share = _get_share(db, user, share_id, as_role="payer")
    if share.status != "pending":
        raise HTTPException(status_code=409, detail="Nothing to remind about: this debt is not waiting for payment")
    if share.debtor_id is None:
        raise HTTPException(status_code=400, detail="This friend has no account. Copy the reminder text and send it yourself")
    if share.reminded_at is not None and datetime.utcnow() - share.reminded_at < REMIND_COOLDOWN:
        raise HTTPException(status_code=429, detail="You reminded them recently. Try again in a few hours")
    share.reminded_at = datetime.utcnow()
    share.remind_count = (share.remind_count or 0) + 1
    db.commit()
    db.refresh(share)
    return _share_out(share)


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
        raise HTTPException(status_code=409, detail="This debt is already marked as paid")
    visible_category(db, user, data.category_id)

    note = f"Debt: {display_name(share.payer)}"
    if share.expense.note:
        note += f" — {share.expense.note}"
    own_expense = Expense(
        user_id=user.id,
        category_id=data.category_id,
        amount=share.amount,
        type="expense",
        note=note[:255],
        spent_at=today(),
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
        raise HTTPException(status_code=409, detail="This debt is already settled")
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
        raise HTTPException(status_code=409, detail="Nothing to reject: the friend has not marked it as paid")
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
