"""Разовые миграции данных. Каждая выполняется один раз на базу и отмечается в app_meta."""
from sqlalchemy.orm import Session

from .importer import is_person
from .models import AppMeta, Category, Expense, MerchantRule

PEOPLE_TO_TRANSFERS = "people_to_transfers_v1"


def move_people_to_transfers(db: Session) -> int:
    """Все записи с описанием «Имя Ф.» переносит в категорию «Переводы» (старые тоже). Возвращает число изменённых."""
    if db.get(AppMeta, PEOPLE_TO_TRANSFERS) is not None:
        return 0
    transfers = db.query(Category).filter(Category.user_id.is_(None), Category.name == "Переводы").first()
    if transfers is None:
        return 0  # категории ещё нет, попробуем при следующем запуске

    changed = 0
    for e in db.query(Expense).filter(Expense.category_id != transfers.id):
        if e.note and is_person(e.note):
            e.category_id = transfers.id
            changed += 1
    # Запомненные ранее исправления для людей больше не нужны: человек всегда идёт в «Переводы»
    for rule in db.query(MerchantRule):
        if is_person(rule.note.title()) or is_person(rule.note):
            db.delete(rule)
    db.add(AppMeta(key=PEOPLE_TO_TRANSFERS, value=str(changed)))
    db.commit()
    return changed
