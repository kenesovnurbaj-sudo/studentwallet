"""Импорт операций из выписки банка: загрузка PDF, предпросмотр, подтверждение."""
from collections import Counter
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..importer import FALLBACK_CATEGORY, extract_pdf_text, guess_category, parse_statement_text
from ..models import Category, Expense, MerchantRule, User

router = APIRouter(prefix="/api/import", tags=["import"])

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 1000
SOURCE = "import"


class PreviewRow(BaseModel):
    date: date
    amount: float
    type: Literal["expense", "income"]
    note: str
    category_id: int
    duplicate: bool  # такая операция уже импортирована раньше
    own_account: bool  # перевод между своими счетами
    manual_match: bool = False  # есть внесённая вручную запись с той же датой, суммой и типом


class PreviewOut(BaseModel):
    rows: list[PreviewRow]


class CommitRow(BaseModel):
    date: date
    amount: float = Field(gt=0)
    type: Literal["expense", "income"]
    note: str = Field(default="", max_length=255)
    category_id: int


class CommitIn(BaseModel):
    rows: list[CommitRow] = Field(max_length=MAX_ROWS)


class CommitOut(BaseModel):
    imported: int
    skipped_duplicates: int


def _key(d: date, amount: float, type_: str, note: str) -> tuple:
    return (d, round(float(amount), 2), type_, note)


def _imported_counts(db: Session, user: User) -> Counter:
    existing = db.query(Expense).filter(Expense.user_id == user.id, Expense.source == SOURCE).all()
    return Counter(_key(e.spent_at, e.amount, e.type, e.note) for e in existing)


def _manual_counts(db: Session, user: User) -> Counter:
    """Записи, добавленные не импортом (вручную или через Siri): сверяем без описания, оно у каждого своё."""
    manual = db.query(Expense).filter(Expense.user_id == user.id, Expense.source != SOURCE).all()
    return Counter((e.spent_at, round(float(e.amount), 2), e.type) for e in manual)


def _rule_key(note: str) -> str:
    return note.strip().lower()[:255]


def _visible_categories(db: Session, user: User) -> list[Category]:
    return db.query(Category).filter(or_(Category.user_id.is_(None), Category.user_id == user.id)).all()


def _pick_category(r, remembered: dict, visible_ids: set, categories: dict, fallback_id: int) -> int:
    """Приоритет: выбор пользователя из прошлых импортов, затем ключевые слова, затем «Другое»."""
    saved = remembered.get(_rule_key(r.note))
    if saved in visible_ids:
        return saved
    return categories.get(guess_category(r.note, r.kind, r.type), fallback_id)


@router.post("/kaspi", response_model=PreviewOut)
async def preview_kaspi(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Читает PDF-выписку Kaspi Gold и возвращает операции для предпросмотра. В базу ничего не пишет."""
    data = await file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File too large")
    try:
        rows = parse_statement_text(extract_pdf_text(data))
    except Exception:
        raise HTTPException(status_code=422, detail="Could not read statement")
    if not rows:
        raise HTTPException(status_code=422, detail="Could not read statement")
    if len(rows) > MAX_ROWS:
        raise HTTPException(status_code=422, detail="Too many rows")

    categories = {c.name: c.id for c in _visible_categories(db, user) if c.user_id is None}
    fallback_id = categories.get(FALLBACK_CATEGORY) or next(iter(categories.values()))

    remembered = {r.note: r.category_id for r in db.query(MerchantRule).filter(MerchantRule.user_id == user.id)}
    visible_ids = {c.id for c in _visible_categories(db, user)}
    already = _imported_counts(db, user)
    manual = _manual_counts(db, user)
    seen: Counter = Counter()
    seen_manual: Counter = Counter()
    out = []
    for r in rows:
        k = _key(r.date, r.amount, r.type, r.note)
        seen[k] += 1
        mk = k[:3]
        is_dup = seen[k] <= already[k]
        manual_match = False
        if not is_dup:
            seen_manual[mk] += 1
            manual_match = seen_manual[mk] <= manual[mk]
        out.append(
            PreviewRow(
                date=r.date,
                amount=r.amount,
                type=r.type,
                note=r.note,
                category_id=_pick_category(r, remembered, visible_ids, categories, fallback_id),
                duplicate=is_dup,
                own_account=r.own_account,
                manual_match=manual_match,
            )
        )
    return PreviewOut(rows=out)


def remember_choices(db: Session, user: User, rows: list) -> None:
    """Запоминает категорию для описания, если пользователь выбрал не ту, что подставили бы автоматически."""
    globals_by_name = {c.name: c.id for c in _visible_categories(db, user) if c.user_id is None}
    fallback_id = globals_by_name.get(FALLBACK_CATEGORY)
    saved = {r.note: r for r in db.query(MerchantRule).filter(MerchantRule.user_id == user.id)}
    for row in rows:
        key = _rule_key(row.note)
        if not key or row.type != "expense":
            continue
        auto_id = globals_by_name.get(guess_category(row.note), fallback_id)
        rule = saved.get(key)
        if rule is not None:
            rule.category_id = row.category_id
        elif row.category_id != auto_id and row.category_id != globals_by_name.get("Переводы"):
            rule = MerchantRule(user_id=user.id, note=key, category_id=row.category_id)
            db.add(rule)
            saved[key] = rule


@router.post("/commit", response_model=CommitOut)
def commit(
    data: CommitIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Сохраняет подтверждённые операции. Уже импортированные ранее пропускаются, так что повторная загрузка безопасна."""
    allowed = {c.id for c in _visible_categories(db, user)}
    if any(r.category_id not in allowed for r in data.rows):
        raise HTTPException(status_code=400, detail="Unknown category")

    remember_choices(db, user, data.rows)

    already = _imported_counts(db, user)
    seen: Counter = Counter()
    imported = skipped = 0
    for r in data.rows:
        k = _key(r.date, r.amount, r.type, r.note)
        seen[k] += 1
        if seen[k] <= already[k]:
            skipped += 1
            continue
        db.add(
            Expense(
                user_id=user.id,
                category_id=r.category_id,
                amount=r.amount,
                type=r.type,
                note=r.note,
                spent_at=r.date,
                source=SOURCE,
            )
        )
        imported += 1
    db.commit()
    return CommitOut(imported=imported, skipped_duplicates=skipped)
