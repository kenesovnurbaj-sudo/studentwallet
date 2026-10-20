"""Разбор выписки Kaspi Gold (PDF на английском) в список операций.

Банк не отдаёт ID операций, поэтому дубликаты ищем по сочетанию дата + сумма + тип + описание
(см. routers/imports.py). Здесь только чистые функции: текст -> строки, описание -> категория.
"""
import re
from dataclasses import dataclass
from datetime import date
from io import BytesIO

from pypdf import PdfReader

# Типы операций Kaspi из колонки «Transaction». «Transfer to your» в PDF переносится на две строки.
KINDS = ("Replenishment", "Transfers", "Purchases", "Withdrawals", "Others", "Transfer to your", "Receipts from your", "Credit proceeds")
OWN_ACCOUNT_KINDS = {"Transfer to your", "Receipts from your", "Credit proceeds"}

ROW_RE = re.compile(
    r"^(?P<d>\d{2})\.(?P<m>\d{2})\.(?P<y>\d{2})\s+(?P<sign>[+-])\s*(?P<amount>\d[\d ]*,\d{2})\s*₸\s+"
    r"(?P<kind>" + "|".join(re.escape(k) for k in KINDS) + r")\s+(?P<details>.*)$"
)

# (категория, ключевые слова). Ищем по целым словам без учёта регистра, побеждает первое совпадение.
CATEGORY_RULES = [
    ("Entertainment", ["pixel cyberlounge", "kinoforum", "кино", "cinema"]),
    ("Transport", ["yandex.go", "yandex go", "onay", "taxi", "такси", "indriver"]),
    ("Subscriptions", ["yandex.plus", "digitalocean", "netflix", "spotify", "beeline", "kcell", "tele2", "altel"]),
    ("Food", ["magnum", "cu", "iu market", "supersushi", "cafe", "mangal", "донер", "хинкали", "гастромир", "бравый",
             "zero arbat", "small", "kfc", "burger", "pizza", "sushi", "coffee", "кофе", "market", "маркет"]),
    ("Education", ["university", "университет", "колледж", "книг", "kitap"]),
]
FALLBACK_CATEGORY = "Other"


@dataclass
class ParsedRow:
    date: date
    amount: float
    type: str  # expense | income
    note: str
    kind: str  # исходный тип операции в выписке
    own_account: bool  # перевод между своими счетами: по умолчанию не импортируем


# Человек в выписке записан как «Имя И.» (иногда дальше идёт «, название банка»)
PERSON_RE = re.compile(r"^(?P<name>[^\W\d_][\w'’ʼ-]*) (?P<initial>[^\W\d_])\.(?:[,\s]|$)")


def is_person(note: str) -> bool:
    m = PERSON_RE.match(note.strip())
    return bool(m) and m["name"][0].isupper() and m["initial"].isupper()


def guess_category(note: str, kind: str = "", type_: str = "expense") -> str:
    """Категория по ключевым словам. Переводы людям и пополнения от людей идут в «Переводы»."""
    if is_person(note) or (kind == "Transfers" and type_ == "expense"):
        return "Transfers"
    text = note.lower()
    for category, words in CATEGORY_RULES:
        for word in words:
            if re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text):
                return category
    return FALLBACK_CATEGORY


def parse_statement_text(text: str) -> list[ParsedRow]:
    rows: list[ParsedRow] = []
    for raw in text.replace("\xa0", " ").splitlines():
        m = ROW_RE.match(raw.strip())
        if not m:
            continue
        amount = float(m["amount"].replace(" ", "").replace(",", "."))
        rows.append(
            ParsedRow(
                date=date(2000 + int(m["y"]), int(m["m"]), int(m["d"])),
                amount=amount,
                type="income" if m["sign"] == "+" else "expense",
                note=m["details"].strip()[:255],
                kind=m["kind"],
                own_account=m["kind"] in OWN_ACCOUNT_KINDS,
            )
        )
    return rows


def extract_pdf_text(data: bytes, max_pages: int = 60) -> str:
    reader = PdfReader(BytesIO(data))
    if len(reader.pages) > max_pages:
        raise ValueError("too many pages")
    return "\n".join(page.extract_text() or "" for page in reader.pages)
