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
    assert guess_category("Magnum Cash&Carry") == "Еда"
    assert guess_category("YANDEX.GO") == "Транспорт"
    assert guess_category("DIGITALOCEAN.COM") == "Подписки"
    assert guess_category("Курсы cumin") == "Другое"  # «cu» внутри слова не считается
    assert guess_category("ИП Неизвестный") == "Другое"


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
