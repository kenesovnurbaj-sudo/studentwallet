"""Деление счёта: друзья без аккаунта, чаевые и налог, «я не участвовал», деление из истории, напоминания."""
from datetime import datetime, timedelta

from app.models import ExpenseShare
from app.splitting import compute_split
from tests.conftest import register_and_login

A = "alice@example.com"  # платит за всех
B = "bek@example.com"


def cat_id(client, headers) -> int:
    return client.get("/api/categories", headers=headers).json()[0]["id"]


def split(mode="equal", participants=None, **extra):
    body = {"mode": mode, "participants": participants if participants is not None else [{"name": "Aida"}]}
    body.update(extra)
    return body


# ---------- расчёты ----------

def test_tip_and_tax_are_separate_and_proportional():
    r = compute_split("equal", 1_000_00, [("a@x.kz", None)], tip_percent=10, tax_percent=12, payer_email="me@x.kz")
    assert r.tip == 100_00 and r.tax == 120_00 and r.service == 220_00
    assert r.total == 1_220_00 and r.mine == 610_00 and r.friends == {"a@x.kz": 610_00}


def test_payer_not_taking_part_equal():
    r = compute_split("equal", 10_000_00, [("a@x.kz", None), ("name:aida", None), ("b@x.kz", None)], participate=False)
    assert r.mine == 0 and sum(r.friends.values()) == 10_000_00
    assert sorted(r.friends.values()) == [3_333_00, 3_333_00, 3_334_00]


def test_payer_not_taking_part_custom_must_cover_whole_bill():
    ok = compute_split("custom", 1_000_00, [("a@x.kz", 600_00), ("b@x.kz", 400_00)], participate=False)
    assert ok.mine == 0 and ok.friends == {"a@x.kz": 600_00, "b@x.kz": 400_00}
    try:
        compute_split("custom", 1_000_00, [("a@x.kz", 600_00)], participate=False)
        assert False, "should fail"
    except ValueError as exc:
        assert "whole bill" in str(exc)


def test_payer_not_taking_part_items_rejects_me():
    items = [(500_00, ["a@x.kz"]), (300_00, ["a@x.kz", "name:aida"])]
    r = compute_split("items", None, [("a@x.kz", None), ("name:aida", None)], items, participate=False)
    assert r.mine == 0 and r.friends == {"a@x.kz": 650_00, "name:aida": 150_00}
    try:
        compute_split("items", None, [("a@x.kz", None)], [(100_00, ["me"])], participate=False)
        assert False, "should fail"
    except ValueError as exc:
        assert "did not take part" in str(exc)


# ---------- друзья без аккаунта ----------

def test_guest_friend_creates_debt_without_account(client):
    a = register_and_login(client, A)
    r = client.post("/api/expenses", headers=a, json={"amount": 10000, "category_id": cat_id(client, a), "note": "dinner", "split": split()})
    assert r.status_code == 201, r.text
    assert r.json()["amount"] == 5000 and r.json()["paid_total"] == 10000
    debts = client.get("/api/debts/owed-to-me", headers=a).json()
    assert len(debts) == 1
    d = debts[0]
    assert (d["debtor_name"], d["guest"], d["debtor"], d["amount"]) == ("Aida", True, None, 5000)


def test_guest_and_registered_friend_together_and_preview(client):
    a = register_and_login(client, A)
    register_and_login(client, B)
    body = {"amount": 9000, "split": split(participants=[{"name": "  Aida   K. "}, {"email": B}])}
    preview = client.post("/api/expenses/split-preview", headers=a, json=body).json()
    guest = next(line for line in preview["lines"] if line["guest"])
    friend = next(line for line in preview["lines"] if not line["guest"])
    assert (guest["name"], guest["found"], guest["email"]) == ("Aida K.", True, None)  # лишние пробелы в имени убраны
    assert (friend["email"], friend["found"]) == (B, True)
    assert preview["my_share"] == 3000


def test_participant_needs_exactly_one_of_email_or_name(client):
    a = register_and_login(client, A)
    for participants in ([{"email": B, "name": "Bek"}], [{}], [{"name": "a@b.kz"}]):
        r = client.post("/api/expenses/split-preview", headers=a, json={"amount": 100, "split": split(participants=participants)})
        assert r.status_code == 422, participants


def test_guest_debt_is_closed_by_payer_and_cannot_be_reminded_in_app(client):
    a = register_and_login(client, A)
    client.post("/api/expenses", headers=a, json={"amount": 10000, "category_id": cat_id(client, a), "split": split()})
    d = client.get("/api/debts/owed-to-me", headers=a).json()[0]
    assert client.post(f"/api/shares/{d['id']}/remind", headers=a).status_code == 400
    assert client.post(f"/api/shares/{d['id']}/confirm", headers=a).json()["status"] == "settled"
    assert client.get("/api/debts/owed-to-me", headers=a).json() == []


# ---------- налог, чаевые, «я не участвовал» через API ----------

def test_tip_tax_and_not_participating_via_api(client):
    a = register_and_login(client, A)
    body = {"amount": 10000, "category_id": cat_id(client, a), "note": "birthday",
            "split": split(participants=[{"name": "Aida"}, {"name": "Miras"}], tip_percent=10, tax_percent=12, i_participate=False)}
    preview = client.post("/api/expenses/split-preview", headers=a, json={"amount": 10000, "split": body["split"]}).json()
    assert (preview["tip"], preview["tax"], preview["service"], preview["total"], preview["my_share"]) == (1000, 1200, 2200, 12200, 0)
    e = client.post("/api/expenses", headers=a, json=body).json()
    assert e["amount"] == 0 and e["paid_total"] == 12200
    assert sorted(d["amount"] for d in client.get("/api/debts/owed-to-me", headers=a).json()) == [6100, 6100]
    # в бюджет ничего не попадает
    month = e["spent_at"][:7]
    client.put("/api/budgets", headers=a, json={"month": month, "limit_amount": 50000})
    assert client.get(f"/api/budget/summary?month={month}", headers=a).json()["spent"] == 0


# ---------- деление уже сохранённой траты ----------

def plain_expense(client, headers, amount=9000, **extra):
    r = client.post("/api/expenses", headers=headers, json={"amount": amount, "category_id": cat_id(client, headers), "note": "lunch", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_split_existing_expense(client):
    a = register_and_login(client, A)
    register_and_login(client, B)
    e = plain_expense(client, a, 9000)
    r = client.post(f"/api/expenses/{e['id']}/split", headers=a, json=split(participants=[{"name": "Aida"}, {"email": B}]))
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["id"], body["amount"], body["paid_total"]) == (e["id"], 3000, 9000)
    assert sorted(d["amount"] for d in client.get("/api/debts/owed-to-me", headers=a).json()) == [3000, 3000]
    assert len(client.get("/api/expenses", headers=a).json()) == 1  # новая запись не создаётся


def test_split_existing_with_tip_and_not_participating(client):
    a = register_and_login(client, A)
    e = plain_expense(client, a, 10000)
    r = client.post(f"/api/expenses/{e['id']}/split", headers=a, json=split(tip_percent=10, i_participate=False))
    assert (r.json()["amount"], r.json()["paid_total"]) == (0, 11000)


def test_split_existing_rules(client):
    a = register_and_login(client, A)
    b = register_and_login(client, B)
    e = plain_expense(client, a)
    income = plain_expense(client, a, type="income")
    assert client.post(f"/api/expenses/{income['id']}/split", headers=a, json=split()).status_code == 400
    assert client.post(f"/api/expenses/{e['id']}/split", headers=b, json=split()).status_code == 403  # чужая трата
    assert client.post("/api/expenses/9999/split", headers=a, json=split()).status_code == 404
    assert client.post(f"/api/expenses/{e['id']}/split", json=split()).status_code == 401
    assert client.post(f"/api/expenses/{e['id']}/split", headers=a, json=split()).status_code == 200
    assert client.post(f"/api/expenses/{e['id']}/split", headers=a, json=split()).status_code == 409  # уже разделена


def test_split_existing_unknown_registered_friend_changes_nothing(client):
    a = register_and_login(client, A)
    e = plain_expense(client, a, 9000)
    r = client.post(f"/api/expenses/{e['id']}/split", headers=a, json=split(participants=[{"email": "nobody@example.com"}]))
    assert r.status_code == 400 and "Not found on the site" in r.json()["detail"]
    again = client.get("/api/expenses", headers=a).json()[0]
    assert again["amount"] == 9000 and again["paid_total"] is None


def test_cannot_split_expense_that_records_a_debt_payment(client):
    a = register_and_login(client, A)
    b = register_and_login(client, B)
    client.post("/api/expenses", headers=a, json={"amount": 6000, "category_id": cat_id(client, a), "split": split(participants=[{"email": B}])})
    share = client.get("/api/debts/i-owe", headers=b).json()[0]
    client.post(f"/api/shares/{share['id']}/mark-paid", headers=b, json={"category_id": cat_id(client, b)})
    own = next(x for x in client.get("/api/expenses", headers=b).json())
    assert client.post(f"/api/expenses/{own['id']}/split", headers=b, json=split()).status_code == 409


# ---------- напоминания ----------

def make_registered_debt(client):
    a = register_and_login(client, A)
    b = register_and_login(client, B)
    client.post("/api/expenses", headers=a, json={"amount": 6000, "category_id": cat_id(client, a), "note": "taxi", "split": split(participants=[{"email": B}])})
    return a, b, client.get("/api/debts/owed-to-me", headers=a).json()[0]


def test_remind_registered_friend_and_cooldown(client, db_session):
    a, b, d = make_registered_debt(client)
    assert d["reminded_at"] is None and d["remind_count"] == 0
    assert client.get("/api/debts/summary", headers=b).json()["reminded"] == 0

    r = client.post(f"/api/shares/{d['id']}/remind", headers=a)
    assert r.status_code == 200 and r.json()["remind_count"] == 1 and r.json()["reminded_at"]
    seen = client.get("/api/debts/i-owe", headers=b).json()[0]
    assert seen["remind_count"] == 1 and seen["reminded_at"]
    assert client.get("/api/debts/summary", headers=b).json()["reminded"] == 1

    assert client.post(f"/api/shares/{d['id']}/remind", headers=a).status_code == 429  # слишком часто

    share = db_session.get(ExpenseShare, d["id"])  # прошло 13 часов
    share.reminded_at = datetime.utcnow() - timedelta(hours=13)
    db_session.commit()
    assert client.post(f"/api/shares/{d['id']}/remind", headers=a).json()["remind_count"] == 2


def test_remind_permissions_and_states(client):
    a, b, d = make_registered_debt(client)
    assert client.post(f"/api/shares/{d['id']}/remind", headers=b).status_code == 403  # должник не напоминает себе
    assert client.post(f"/api/shares/{d['id']}/remind").status_code == 401
    other = register_and_login(client, "stranger@example.com")
    assert client.post(f"/api/shares/{d['id']}/remind", headers=other).status_code == 404
    client.post(f"/api/shares/{d['id']}/confirm", headers=a)  # долг закрыт
    assert client.post(f"/api/shares/{d['id']}/remind", headers=a).status_code == 409


# ---------- миграция базы, созданной до этой версии ----------

def test_ensure_schema_upgrades_old_sqlite_database():
    import sqlalchemy as sa
    from sqlalchemy import create_engine, text

    import app.models  # noqa: F401  (метаданные таблиц)
    from app import database

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=sa.pool.StaticPool)
    with eng.begin() as c:
        c.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        c.execute(text("CREATE TABLE expenses (id INTEGER PRIMARY KEY, user_id INT, amount NUMERIC)"))
        c.execute(text(
            "CREATE TABLE expense_shares (id INTEGER NOT NULL PRIMARY KEY, expense_id INTEGER NOT NULL, payer_id INTEGER NOT NULL, "
            "debtor_id INTEGER NOT NULL, amount NUMERIC(12,2) NOT NULL, status VARCHAR(12) NOT NULL, created_at DATETIME NOT NULL, "
            "marked_at DATETIME, settled_at DATETIME, debtor_expense_id INTEGER)"
        ))
        for name in ("expense_id", "payer_id", "debtor_id"):
            c.execute(text(f"CREATE INDEX ix_expense_shares_{name} ON expense_shares ({name})"))
        c.execute(text("INSERT INTO users VALUES (1),(2)"))
        c.execute(text("INSERT INTO expenses VALUES (1,1,100)"))
        c.execute(text("INSERT INTO expense_shares (id,expense_id,payer_id,debtor_id,amount,status,created_at) VALUES (1,1,1,2,50,'pending','2026-10-01 10:00:00')"))

    database.ensure_schema(eng)
    database.ensure_schema(eng)  # повторный запуск безопасен

    with eng.begin() as c:
        assert c.execute(text("SELECT id, debtor_id, debtor_name, remind_count FROM expense_shares")).fetchall() == [(1, 2, None, 0)]
        c.execute(text("INSERT INTO expense_shares (expense_id,payer_id,debtor_id,debtor_name,amount,status,created_at,remind_count) VALUES (1,1,NULL,'Aida',50,'pending','2026-10-02',0)"))
        assert c.execute(text("SELECT count(*) FROM expense_shares")).scalar() == 2
