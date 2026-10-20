"""ИИ-функции для ввода трат: разбор фразы вроде «lunch at canteen 2500»."""
import json
import os
from datetime import date
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..expense_parser import parse_expense_text
from ..importer import FALLBACK_CATEGORY, guess_category
from ..models import Category, User
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
