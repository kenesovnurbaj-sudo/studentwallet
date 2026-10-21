"""Разбор свободного текста вида «lunch at canteen 2500» в сумму, дату, тип и описание.

Только правила, без ИИ: так функция работает и когда Ollama недоступна. Категорию подбирает importer.guess_category,
а если она не нашлась, роутер при возможности спрашивает модель.
"""
import re
from dataclasses import dataclass
from datetime import date, timedelta

CURRENCY = r"(?:₸|тг|тенге|tenge|kzt|tg)"
SPAN_RE = re.compile(r"\d[\d  .,]*\d(?:\s?[kк](?![a-zа-я]))?|\d(?:\s?[kк](?![a-zа-я]))?", re.IGNORECASE)
DATE_RE = re.compile(r"(?<!\d)(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?(?!\d)")
MONTH_WORDS = set(
    "jan january feb february mar march apr april may jun june jul july aug august sep sept september oct october nov november "
    "dec december янв января фев февраля мар марта апр апреля мая июн июня июл июля авг августа сен сентября окт октября "
    "ноя ноября дек декабря".split()
)
INCOME_WORDS = {"salary", "stipend", "scholarship", "allowance", "received", "income", "зарплата", "стипендия", "получил", "получила", "доход"}


@dataclass
class ParsedText:
    amount: float
    type: str
    note: str
    spent_at: date


def _to_number(span: str) -> float | None:
    text = span.strip().replace(" ", " ")
    mult = 1
    if text[-1].lower() in "kк":
        mult, text = 1000, text[:-1].strip()
    if re.fullmatch(r"\d{1,3}(?:[ ,]\d{3})+", text):  # 15 000 / 15,000
        value = float(re.sub(r"[ ,]", "", text))
    elif re.fullmatch(r"\d+(?:[.,]\d{1,2})?", text):  # 2500 / 2.5 / 2,50
        value = float(text.replace(",", "."))
    else:
        return None
    return value * mult


def parse_expense_text(text: str, today: date | None = None) -> ParsedText | None:
    today = today or date.today()
    original = " ".join(text.split())
    work = original.lower()

    # Дата
    spent_at = today
    if re.search(r"\b(yesterday|вчера)\b", work):
        spent_at = today - timedelta(days=1)
    m = DATE_RE.search(work)
    if m:
        try:
            year = int(m.group(3)) if m.group(3) else today.year
            spent_at = date(year + 2000 if year < 100 else year, int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    # Кандидаты в сумму: без дат и без чисел рядом с названием месяца
    candidates = []  # (value, has_currency, start, end)
    for sm in SPAN_RE.finditer(original):
        value = _to_number(sm.group())
        if not value or value <= 0:
            continue
        if m and DATE_RE.fullmatch(sm.group().strip()):
            continue
        before, after = original[: sm.start()].lower(), original[sm.end():].lower()
        next_word = re.match(r"\s*([a-zа-я]+)", after)
        if next_word and next_word.group(1) in MONTH_WORDS:  # «20 october»: это дата, а не сумма
            continue
        has_cur = bool(re.match(rf"\s*{CURRENCY}(?!\w)", after, re.IGNORECASE)) or bool(re.search(rf"{CURRENCY}\s*$", before, re.IGNORECASE))
        candidates.append((value, has_cur, sm.start(), sm.end()))
    if not candidates:
        return None
    with_cur = [c for c in candidates if c[1]]
    value, _, start, end = max(with_cur or candidates, key=lambda c: c[0])

    # Описание: исходный текст без суммы и слова-валюты
    note = original[:start] + " " + original[end:]
    note = re.sub(rf"\s*{CURRENCY}(?!\w)", " ", note, flags=re.IGNORECASE)
    note = re.sub(r"\b(yesterday|today|вчера|сегодня)\b", " ", note, flags=re.IGNORECASE)
    note = " ".join(note.split()).strip(" -,:;")[:255] or original[:255]

    words = set(re.findall(r"[a-zа-я]+", work))
    return ParsedText(amount=value, type="income" if words & INCOME_WORDS else "expense", note=note, spent_at=spent_at)
