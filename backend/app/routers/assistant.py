"""ИИ-ассистент: чат, который знает бюджет и траты текущего пользователя.

Модель работает в Ollama. Адрес и модель задаются переменными окружения
OLLAMA_URL и OLLAMA_MODEL, поэтому Ollama может стоять на другой машине
(например, на ноутбуке, подключённом к серверу через SSH-туннель).
"""
import os
from datetime import date
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Category, Expense, User
from .budgets import _month_bounds, budget_summary

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))

MAX_HISTORY = 20  # сколько последних сообщений диалога отправляем модели
RECENT_LIMIT = 15  # сколько последних операций показываем модели

SYSTEM_PROMPT = """Ты финансовый помощник студента в приложении StudentWallet.
Отвечай на языке пользователя (русский, казахский или английский), коротко и по делу.
Помогай разбираться в тратах, планировать бюджет, находить, где можно сэкономить.
Опирайся только на данные пользователя ниже. Если данных не хватает, так и скажи, не выдумывай цифры.
Ты не добавляешь и не меняешь траты сам: если пользователь просит, объясни, как это сделать в приложении.
Не давай юридических и инвестиционных советов.

Данные пользователя:
{context}"""


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=50)


class ChatReply(BaseModel):
    reply: str


def build_context(db: Session, user: User) -> str:
    """Короткая сводка по бюджету и тратам. Email и пароль в неё не попадают."""
    today = date.today()
    month = today.strftime("%Y-%m")
    first_day, last_day = _month_bounds(month)
    lines = [f"Сегодня {today.isoformat()}. Имя: {user.full_name or 'студент'}. Валюта: {user.currency}."]

    try:
        s = budget_summary(month=month, user=user, db=db)
        lines.append(
            f"Бюджет на {month}: лимит {s.limit}, потрачено {s.spent} ({s.percent_used}%), "
            f"осталось {s.remaining}, дней до конца месяца {s.days_left}, можно тратить в день {s.daily_limit}."
        )
    except HTTPException:
        lines.append(f"Бюджет на {month} не задан.")

    by_category = (
        db.query(Category.name, func.sum(Expense.amount))
        .join(Expense, Expense.category_id == Category.id)
        .filter(
            Expense.user_id == user.id,
            Expense.type == "expense",
            Expense.spent_at >= first_day,
            Expense.spent_at <= last_day,
        )
        .group_by(Category.name)
        .order_by(func.sum(Expense.amount).desc())
        .all()
    )
    if by_category:
        lines.append("Расходы за месяц по категориям: " + ", ".join(f"{n}: {float(t):g}" for n, t in by_category))
    else:
        lines.append("Расходов в этом месяце пока нет.")

    recent = (
        db.query(Expense, Category.name)
        .join(Category, Expense.category_id == Category.id)
        .filter(Expense.user_id == user.id)
        .order_by(Expense.spent_at.desc(), Expense.id.desc())
        .limit(RECENT_LIMIT)
        .all()
    )
    if recent:
        lines.append("Последние операции:")
        for e, cat in recent:
            kind = "расход" if e.type == "expense" else "доход"
            note = f" ({e.note})" if e.note else ""
            lines.append(f"- {e.spent_at.isoformat()} {kind} {float(e.amount):g} {cat}{note}")
    return "\n".join(lines)


def ask_ollama(messages: list[dict]) -> str:
    """Отправляет диалог в Ollama и возвращает текст ответа. Вынесено отдельно, чтобы подменять в тестах."""
    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(status_code=503, detail="AI unavailable")


@router.post("/chat", response_model=ChatReply)
def chat(
    data: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    history = [m.model_dump() for m in data.messages[-MAX_HISTORY:]]
    if history[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="Last message must be from user")
    system = {"role": "system", "content": SYSTEM_PROMPT.format(context=build_context(db, user))}
    return ChatReply(reply=ask_ollama([system, *history]))
