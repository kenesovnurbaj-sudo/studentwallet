from datetime import date

from app.importer import guess_category, parse_statement_text
from app.routers import imports
from tests.conftest import register_and_login

# Синтетический текст в формате выписки Kaspi Gold (без реальных данных)
SAMPLE = """Date Amount Transaction Details
20.10.26 + 3 200,00 ₸   Replenishment      Иван И.
20.10.26 - 13 650,00 ₸   Purchases      ИП DANTE
19.10.26 - 4 466,00 ₸   Purchases      Magnum Cash&Carry
18.10.26 - 680,00 ₸   Transfers      Сара Т.
16.10.26 - 680,00 ₸   Transfers      Сара Т.
16.10.26 - 680,00 ₸   Transfers      Сара Т.
10.10.26 - 39 705,00 ₸   Transfer to your      Pay for Kaspi Credit
03.10.26 - 10 003,00 ₸   Transfers      To card Optima Bank OJSC*4566
(- 21,96 USD)
Page footer without a transaction
"""


def test_parse_rows():
    rows = parse_statement_text(SAMPLE)
    assert len(rows) == 8
    income = rows[0]
    assert (income.type, income.amount, income.date) == ("income", 3200.0, date(2026, 10, 20))
    assert rows[1].type == "expense" and rows[1].amount == 13650.0
    assert rows[7].amount == 10003.0  # валютная строка (- 21,96 USD) не мешает
    own = [r for r in rows if r.own_account]
    assert len(own) == 1 and own[0].note == "Pay for Kaspi Credit"


def test_guess_category():
    assert guess_category("Magnum Cash&Carry") == "Food"
    assert guess_category("YANDEX.GO") == "Transport"
    assert guess_category("DIGITALOCEAN.COM") == "Subscriptions"
    assert guess_category("Курсы cumin") == "Other"  # «cu» внутри слова не считается
    assert guess_category("ИП Неизвестный") == "Other"


def test_preview_and_commit_with_duplicates(client, auth_headers, monkeypatch):
    monkeypatch.setattr(imports, "extract_pdf_text", lambda data: SAMPLE)

    resp = client.post("/api/import/kaspi", headers=auth_headers, files={"file": ("s.pdf", b"%PDF-fake")})
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert len(rows) == 8
    assert not any(r["duplicate"] for r in rows)

    payload = {"rows": [{k: r[k] for k in ("date", "amount", "type", "note", "category_id")} for r in rows]}
    first = client.post("/api/import/commit", headers=auth_headers, json=payload).json()
    assert first == {"imported": 8, "skipped_duplicates": 0}
    assert len(client.get("/api/expenses", headers=auth_headers).json()) == 8

    # Повторная загрузка того же файла ничего не добавляет, а две одинаковые операции в один день сохраняются обе
    again = client.post("/api/import/kaspi", headers=auth_headers, files={"file": ("s.pdf", b"%PDF-fake")}).json()
    assert all(r["duplicate"] for r in again["rows"])
    second = client.post("/api/import/commit", headers=auth_headers, json=payload).json()
    assert second == {"imported": 0, "skipped_duplicates": 8}
    assert len(client.get("/api/expenses", headers=auth_headers).json()) == 8


def test_unreadable_file_rejected(client, auth_headers):
    resp = client.post("/api/import/kaspi", headers=auth_headers, files={"file": ("x.pdf", b"not a pdf")})
    assert resp.status_code == 422


def test_import_is_per_user_and_requires_auth(client, auth_headers):
    assert client.post("/api/import/commit", json={"rows": []}).status_code == 401
    other = register_and_login(client, "other@example.com")
    row = {"date": "2026-10-01", "amount": 100, "type": "expense", "note": "x", "category_id": 1}
    client.post("/api/import/commit", headers=auth_headers, json={"rows": [row]})
    assert client.post("/api/import/commit", headers=other, json={"rows": [row]}).json()["imported"] == 1


def test_commit_rejects_foreign_category(client, auth_headers):
    row = {"date": "2026-10-01", "amount": 100, "type": "expense", "note": "x", "category_id": 9999}
    assert client.post("/api/import/commit", headers=auth_headers, json={"rows": [row]}).status_code == 400


def test_manual_entry_is_flagged(client, auth_headers, monkeypatch):
    monkeypatch.setattr(imports, "extract_pdf_text", lambda data: SAMPLE)
    cat = client.get("/api/categories", headers=auth_headers).json()[0]["id"]
    client.post(
        "/api/expenses",
        headers=auth_headers,
        json={"amount": 13650, "category_id": cat, "type": "expense", "spent_at": "2026-10-20", "note": "ужин"},
    )
    rows = client.post("/api/import/kaspi", headers=auth_headers, files={"file": ("s.pdf", b"x")}).json()["rows"]
    flagged = [r for r in rows if r["manual_match"]]
    assert len(flagged) == 1 and flagged[0]["note"] == "ИП DANTE"
    assert not flagged[0]["duplicate"]


def test_person_transfers_go_to_transfers_category():
    assert guess_category("Сара Т.", "Transfers", "expense") == "Transfers"
    assert guess_category("From card of other banks", "Replenishment", "income") == "Other"
    assert guess_category("Magnum Cash&Carry", "Purchases", "expense") == "Food"


def test_remembers_user_category_for_merchant(client, auth_headers, monkeypatch):
    monkeypatch.setattr(imports, "extract_pdf_text", lambda data: SAMPLE)
    cats = {c["name"]: c["id"] for c in client.get("/api/categories", headers=auth_headers).json()}

    def preview():
        return client.post("/api/import/kaspi", headers=auth_headers, files={"file": ("s.pdf", b"x")}).json()["rows"]

    rows = preview()
    dante = next(r for r in rows if r["note"] == "ИП DANTE")
    assert dante["category_id"] == cats["Other"]
    assert next(r for r in rows if r["note"] == "Сара Т.")["category_id"] == cats["Transfers"]

    # пользователь исправил категорию и импортировал
    payload = {"rows": [{k: dante[k] for k in ("date", "amount", "type", "note")} | {"category_id": cats["Food"]}]}
    assert client.post("/api/import/commit", headers=auth_headers, json=payload).status_code == 200

    # при следующей загрузке выбор подставляется сам, у другого пользователя он не появляется
    assert next(r for r in preview() if r["note"] == "ИП DANTE")["category_id"] == cats["Food"]
    other = register_and_login(client, "other2@example.com")
    r2 = client.post("/api/import/kaspi", headers=other, files={"file": ("s.pdf", b"x")}).json()["rows"]
    assert next(r for r in r2 if r["note"] == "ИП DANTE")["category_id"] == cats["Other"]


def test_person_detected_by_name_and_initial():
    from app.importer import is_person

    for note in ("Сара Т.", "Ақерке Ж.", "Мəдина Д.", "Mubariz S.", "Гулжан Р., Bank CenterCredit"):
        assert is_person(note), note
    for note in ("ИП DANTE", "MIRAS STORE", "Magnum Cash&Carry", "iU Market Байзакова", "ТОО Tumar-life clinic", "Pay for Kaspi Credit"):
        assert not is_person(note), note
    # пополнение от человека тоже «Переводы», даже если банк назвал его не переводом
    assert guess_category("Айдар С.", "Replenishment", "income") == "Transfers"
    assert guess_category("Айдар С.", "Purchases", "expense") == "Transfers"


def test_migration_moves_existing_people_to_transfers(db_session):
    from app.migrations import move_people_to_transfers
    from app.models import Category, Expense, User, Role
    from app.security import hash_password

    role = db_session.query(Role).filter_by(name="student").one()
    user = User(email="m@example.com", password_hash=hash_password("password123"), role_id=role.id)
    db_session.add(user)
    db_session.commit()
    cats = {c.name: c.id for c in db_session.query(Category).filter(Category.user_id.is_(None))}

    def add(note, cat):
        e = Expense(user_id=user.id, category_id=cats[cat], amount=100, note=note)
        db_session.add(e)
        db_session.commit()
        return e

    person, old_income, shop = add("Сара Т.", "Other"), add("Айдар С.", "Food"), add("ИП DANTE", "Other")

    assert move_people_to_transfers(db_session) == 2
    db_session.refresh(person), db_session.refresh(old_income), db_session.refresh(shop)
    assert person.category_id == old_income.category_id == cats["Transfers"]
    assert shop.category_id == cats["Other"]

    # Разовая миграция: ручное исправление после неё не откатывается
    person.category_id = cats["Food"]
    db_session.commit()
    assert move_people_to_transfers(db_session) == 0
    db_session.refresh(person)
    assert person.category_id == cats["Food"]


def test_person_ignores_remembered_category(client, auth_headers, monkeypatch):
    from app.models import MerchantRule

    monkeypatch.setattr(imports, "extract_pdf_text", lambda data: SAMPLE)
    cats = {c["name"]: c["id"] for c in client.get("/api/categories", headers=auth_headers).json()}
    row = {"date": "2026-10-18", "amount": 680, "type": "expense", "note": "Сара Т.", "category_id": cats["Food"]}
    client.post("/api/import/commit", headers=auth_headers, json={"rows": [row]})
    rows = client.post("/api/import/kaspi", headers=auth_headers, files={"file": ("s.pdf", b"x")}).json()["rows"]
    assert next(r for r in rows if r["note"] == "Сара Т.")["category_id"] == cats["Transfers"]


def test_default_categories_renamed_in_place(db_session):
    from app.migrations import rename_default_categories_to_english
    from app.models import Category

    food = db_session.query(Category).filter_by(name="Food", user_id=None).one()
    food.name = "Еда"  # имитируем старую базу
    db_session.commit()
    assert rename_default_categories_to_english(db_session) == 1
    db_session.refresh(food)
    assert food.name == "Food"  # тот же id, записи не потеряли категорию
    assert db_session.query(Category).filter_by(name="Еда").count() == 0
