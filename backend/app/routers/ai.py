"""ИИ-функции для ввода трат: разбор фразы вроде «lunch at canteen 2500»."""
import json
import os
from datetime import date
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..expense_parser import parse_expense_text
from ..importer import FALLBACK_CATEGORY, guess_category
from ..budget_split import amounts_from_percents, baseline_percents, validate_ai_percents
from ..models import Budget, Category, Expense, User
from .budgets import MONTH_PATTERN, _current_month
from . import assistant

router = APIRouter(prefix="/api/ai", tags=["ai"])

CATEGORY_TIMEOUT = float(os.getenv("OLLAMA_CATEGORY_TIMEOUT", "30"))


class ParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=300)


class ParseResult(BaseModel):
    amount: float
    type: Literal["expense", "income"]
    category_id: int
    category: str
    note: str
    spent_at: date
    source: Literal["rules", "ai"]  # чем определена категория


def pick_category_with_ai(text: str, names: list[str]) -> str | None:
    """Просит модель выбрать одну категорию из списка. Вынесено отдельно, чтобы подменять в тестах.
    Любая ошибка или ответ не из списка даёт None, тогда остаётся категория по правилам."""
    prompt = (
        "Classify the student's expense into exactly one of these categories: " + ", ".join(names) + ". "
        'Reply only with JSON like {"category": "<name>"}.'
    )
    try:
        resp = httpx.post(
            f"{assistant.OLLAMA_URL}/api/chat",
            json={
                "model": assistant.OLLAMA_MODEL,
                "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": text}],
                "stream": False,
                "format": "json",
            },
            timeout=CATEGORY_TIMEOUT,
        )
        resp.raise_for_status()
        answer = json.loads(resp.json()["message"]["content"]).get("category", "")
    except (httpx.HTTPError, KeyError, ValueError, AttributeError, TypeError):
        return None
    by_lower = {n.lower(): n for n in names}
    return by_lower.get(str(answer).strip().lower())


@router.post("/parse-expense", response_model=ParseResult)
def parse_expense(
    data: ParseRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Находит в фразе сумму, дату, тип и категорию. В базу ничего не пишет: пользователь подтверждает в форме."""
    parsed = parse_expense_text(data.text)
    if parsed is None:
        raise HTTPException(status_code=422, detail="Could not find an amount")

    visible = db.query(Category).filter(or_(Category.user_id.is_(None), Category.user_id == user.id)).all()
    by_name = {c.name: c for c in visible}
    fallback = by_name.get(FALLBACK_CATEGORY) or visible[0]

    name, source = guess_category(parsed.note), "rules"
    category = by_name.get(name, fallback)
    if parsed.type == "expense" and category.name == FALLBACK_CATEGORY:
        ai_name = pick_category_with_ai(parsed.note, [c.name for c in visible])
        if ai_name and ai_name != FALLBACK_CATEGORY:
            category, source = by_name[ai_name], "ai"

    return ParseResult(
        amount=parsed.amount,
        type=parsed.type,
        category_id=category.id,
        category=category.name,
        note=parsed.note,
        spent_at=parsed.spent_at,
        source=source,
    )


SPLIT_TIMEOUT = float(os.getenv("OLLAMA_SPLIT_TIMEOUT", "90"))
DEFAULT_TIP = "A typical student split. Adjust the numbers to your own life before applying."


class SplitItem(BaseModel):
    category_id: int
    category: str
    icon: str
    percent: float
    amount: int


class SplitSuggestion(BaseModel):
    month: str
    total: int
    source: Literal["ai", "rules"]
    tip: str
    items: list[SplitItem]


def ask_ai_for_split(total: int, names: list[str], baseline: dict[str, float], history: dict[str, float]):
    """Возвращает (проценты, совет) от модели или (None, None). Вынесено отдельно, чтобы подменять в тестах."""
    system = (
        "You are a budgeting assistant for a student. Split the monthly budget into percentages across the given "
        'categories. Reply only with JSON: {"split": {"<category>": <percent>, ...}, "tip": "<one short sentence>"}. '
        "Percentages must add up to 100. Use only the given category names."
    )
    user = (
        f"Monthly budget: {total} KZT.\nCategories: {', '.join(names)}.\n"
        f"A typical student split (percent): {json.dumps({k: round(v) for k, v in baseline.items()})}.\n"
        + (f"This student's past spending by category (KZT): {json.dumps({k: round(v) for k, v in history.items()})}.\n" if history else "")
        + "Suggest a split that fits this student."
    )
    try:
        resp = httpx.post(
            f"{assistant.OLLAMA_URL}/api/chat",
            json={
                "model": assistant.OLLAMA_MODEL,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "stream": False,
                "format": "json",
            },
            timeout=SPLIT_TIMEOUT,
        )
        resp.raise_for_status()
        data = json.loads(resp.json()["message"]["content"])
        tip = data.get("tip")
        return data.get("split"), (tip.strip()[:300] if isinstance(tip, str) else None)
    except (httpx.HTTPError, KeyError, ValueError, AttributeError, TypeError):
        return None, None


def _previous_months(month: str, count: int) -> tuple[date, date]:
    year, mon = int(month[:4]), int(month[5:7])
    end = date(year, mon, 1)
    start_mon = mon - count
    start_year = year + (start_mon - 1) // 12
    start_mon = (start_mon - 1) % 12 + 1
    return date(start_year, start_mon, 1), end


@router.get("/budget-split", response_model=SplitSuggestion)
def suggest_budget_split(
    month: str = Query(default_factory=_current_month, pattern=MONTH_PATTERN),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Предлагает, как разделить общий бюджет месяца по категориям. В базу ничего не пишет."""
    budget = (
        db.query(Budget)
        .filter(Budget.user_id == user.id, Budget.month == month, Budget.category_id.is_(None))
        .first()
    )
    if budget is None:
        raise HTTPException(status_code=404, detail="No budget set for this month")
    total = int(round(float(budget.limit_amount)))

    visible = db.query(Category).filter(or_(Category.user_id.is_(None), Category.user_id == user.id)).all()
    by_name = {c.name: c for c in visible}
    names = [n for n in by_name if n != "Transfers"]  # переводы людям не категория для планирования

    start, end = _previous_months(month, 3)
    rows = (
        db.query(Category.name, func.sum(Expense.amount))
        .join(Expense, Expense.category_id == Category.id)
        .filter(Expense.user_id == user.id, Expense.type == "expense", Expense.spent_at >= start, Expense.spent_at < end)
        .group_by(Category.name)
        .all()
    )
    history = {n: float(t) for n, t in rows if n in names}

    baseline = baseline_percents(names, history)
    if not baseline:  # у пользователя нет ни одной стандартной категории
        raise HTTPException(status_code=422, detail="No categories to split between")

    percents, source, tip = baseline, "rules", DEFAULT_TIP
    ai_split, ai_tip = ask_ai_for_split(total, names, baseline, history)
    checked = validate_ai_percents(ai_split, names)
    if checked:
        percents, source, tip = checked, "ai", ai_tip or "Suggested by WALL·E based on your budget and past spending."

    amounts = amounts_from_percents(percents, total)
    items = [
        SplitItem(
            category_id=by_name[n].id, category=n, icon=by_name[n].icon,
            percent=round(percents[n], 1), amount=amounts[n],
        )
        for n in sorted(amounts, key=lambda n: -amounts[n])
        if amounts[n] > 0
    ]
    return SplitSuggestion(month=month, total=total, source=source, tip=tip, items=items)
