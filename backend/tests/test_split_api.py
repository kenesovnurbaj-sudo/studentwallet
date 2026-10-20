"""Тесты делёжки счёта: создание долгов, права доступа, возврат и подтверждение."""
from datetime import date

from tests.conftest import register_and_login

A = "alice@example.com"  # платит за всех
B = "bek@example.com"
C = "dana@example.com"


def setup_users(client):
    return (
        register_and_login(client, A),
        register_and_login(client, B),
        register_and_login(client, C),
    )


def category_id(client, headers) -> int:
    return client.get("/api/categories", headers=headers).json()[0]["id"]


def split_body(cat, mode="equal", amount=10000, participants=None, **extra):
    participants = participants if participants is not None else [{"email": B}, {"email": C}]
    body = {"category_id": cat, "note": "кафе", "split": {"mode": mode, "participants": participants}}
    if amount is not None:
        body["amount"] = amount
    body["split"].update(extra)
    return body


def create_equal(client, a, cat):
    r = client.post("/api/expenses", headers=a, json=split_body(cat))
    assert r.status_code == 201, r.text
    return r.json()


# ---------- создание ----------

def test_equal_split_creates_expense_and_debts(client):
    a, b, c = setup_users(client)
    cat = category_id(client, a)

    expense = create_equal(client, a, cat)
    assert expense["amount"] == 3334  # ваша доля
    assert expense["paid_total"] == 10000  # весь чек

    owed = client.get("/api/debts/owed-to-me", headers=a).json()
    assert sorted(d["debtor"]["email"] for d in owed) == [B, C]
    assert {d["amount"] for d in owed} == {3333}

    # друг видит свой долг у себя
    mine = client.get("/api/debts/i-owe", headers=b).json()
    assert len(mine) == 1
    assert mine[0]["amount"] == 3333
    assert mine[0]["payer"]["email"] == A
    assert mine[0]["note"] == "кафе"
    assert mine[0]["status"] == "pending"


def test_budget_counts_only_my_share(client):
    a, _, _ = setup_users(client)
    cat = category_id(client, a)
    month = date.today().strftime("%Y-%m")
    client.put("/api/budgets", headers=a, json={"month": month, "limit_amount": 20000})

    create_equal(client, a, cat)

    summary = client.get("/api/budget/summary", headers=a).json()
    assert summary["spent"] == 3334  # а не 10000


def test_custom_split(client):
    a, b, _ = setup_users(client)
    cat = category_id(client, a)
    body = split_body(
        cat, mode="custom", participants=[{"email": B, "amount": 2500}, {"email": C, "amount": 6000}]
    )
    expense = client.post("/api/expenses", headers=a, json=body).json()
    assert expense["amount"] == 1500
    assert expense["paid_total"] == 10000
    assert sorted(d["amount"] for d in client.get("/api/debts/owed-to-me", headers=a).json()) == [2500, 6000]


def test_custom_split_more_than_check_rejected(client):
    a, _, _ = setup_users(client)
    cat = category_id(client, a)
    body = split_body(cat, mode="custom", amount=1000, participants=[{"email": B, "amount": 800}, {"email": C, "amount": 300}])
    assert client.post("/api/expenses", headers=a, json=body).status_code == 400


def test_items_split_with_tip(client):
    a, _, _ = setup_users(client)
    cat = category_id(client, a)
    items = [
        {"name": "ланч", "price": 2500, "eaters": [B]},
        {"name": "стейк", "price": 6000, "eaters": [C]},
        {"name": "пицца", "price": 3000, "eaters": ["me", B, C]},
        {"name": "кофе", "price": 1000, "eaters": ["me"]},
    ]
    body = split_body(cat, mode="items", amount=None, items=items, tip_percent=10)
    expense = client.post("/api/expenses", headers=a, json=body).json()

    # чек 12 500 + чаевые 1 250 = 13 750
    assert expense["paid_total"] == 13750
    owed = {d["debtor"]["email"]: d["amount"] for d in client.get("/api/debts/owed-to-me", headers=a).json()}
    assert owed == {B: 3850, C: 7700}
    assert expense["amount"] == 2200
    assert expense["amount"] + sum(owed.values()) == expense["paid_total"]


def test_unknown_friend_rejected(client):
    a, _, _ = setup_users(client)
    cat = category_id(client, a)
    body = split_body(cat, participants=[{"email": "nobody@example.com"}])
    r = client.post("/api/expenses", headers=a, json=body)
    assert r.status_code == 400
    assert "nobody@example.com" in r.json()["detail"]
    assert client.get("/api/expenses", headers=a).json() == []  # ничего не сохранилось


def test_cannot_split_with_yourself(client):
    a, _, _ = setup_users(client)
    cat = category_id(client, a)
    body = split_body(cat, participants=[{"email": A.upper()}])
    assert client.post("/api/expenses", headers=a, json=body).status_code == 400


def test_amount_required_without_split_and_in_non_items_modes(client):
    a, _, _ = setup_users(client)
    cat = category_id(client, a)
    assert client.post("/api/expenses", headers=a, json={"category_id": cat}).status_code == 422
    assert client.post("/api/expenses", headers=a, json=split_body(cat, amount=None)).status_code == 422


def test_income_cannot_be_split(client):
    a, _, _ = setup_users(client)
    cat = category_id(client, a)
    body = split_body(cat)
    body["type"] = "income"
    assert client.post("/api/expenses", headers=a, json=body).status_code == 400


def test_service_percent_applies_to_equal_split(client):
    a, _, _ = setup_users(client)
    cat = category_id(client, a)
    body = split_body(cat, tip_percent=10)
    expense = client.post("/api/expenses", headers=a, json=body).json()
    assert expense["paid_total"] == 11000
    assert expense["amount"] == 3668
    owed = [d["amount"] for d in client.get("/api/debts/owed-to-me", headers=a).json()]
    assert owed == [3666, 3666]


# ---------- предпросмотр ----------

def test_preview_saves_nothing_and_flags_unknown_friends(client):
    a, _, _ = setup_users(client)
    body = {"amount": 9000, "split": {"mode": "equal", "participants": [{"email": B}, {"email": "ghost@example.com"}]}}
    r = client.post("/api/expenses/split-preview", headers=a, json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 9000
    assert data["my_share"] == 3000
    assert {line["email"]: line["found"] for line in data["lines"]} == {B: True, "ghost@example.com": False}
    assert client.get("/api/expenses", headers=a).json() == []
    assert client.get("/api/debts/owed-to-me", headers=a).json() == []


# ---------- возврат и подтверждение ----------

def test_full_repayment_flow(client):
    a, b, _ = setup_users(client)
    cat_a = category_id(client, a)
    cat_b = category_id(client, b)
    create_equal(client, a, cat_a)
    share_id = client.get("/api/debts/i-owe", headers=b).json()[0]["id"]

    # друг нажимает «Я оплатил»: сумма попадает в его расходы
    r = client.post(f"/api/shares/{share_id}/mark-paid", headers=b, json={"category_id": cat_b})
    assert r.status_code == 200
    assert r.json()["status"] == "marked_paid"
    b_expenses = client.get("/api/expenses", headers=b).json()
    assert len(b_expenses) == 1
    assert b_expenses[0]["amount"] == 3333
    assert b_expenses[0]["note"].startswith("Debt:")
    assert "кафе" in b_expenses[0]["note"]

    summary_a = client.get("/api/debts/summary", headers=a).json()
    assert summary_a["to_confirm"] == 1
    assert summary_a["owed_to_me"] == 6666  # 3333 ещё не подтверждены + 3333 с Даны
    assert client.get("/api/debts/summary", headers=b).json()["i_owe"] == 0

    # плательщик подтверждает
    r = client.post(f"/api/shares/{share_id}/confirm", headers=a)
    assert r.status_code == 200
    assert r.json()["status"] == "settled"
    assert client.get("/api/debts/summary", headers=a).json() == {"owed_to_me": 3333, "i_owe": 0, "to_confirm": 0}
    assert client.get("/api/debts/i-owe", headers=b).json() == []  # закрытые скрыты
    assert len(client.get("/api/debts/i-owe?include_settled=true", headers=b).json()) == 1


def test_reject_reopens_debt_and_removes_friends_expense(client):
    a, b, _ = setup_users(client)
    create_equal(client, a, category_id(client, a))
    share_id = client.get("/api/debts/i-owe", headers=b).json()[0]["id"]
    client.post(f"/api/shares/{share_id}/mark-paid", headers=b, json={"category_id": category_id(client, b)})

    r = client.post(f"/api/shares/{share_id}/reject", headers=a)
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
    assert client.get("/api/expenses", headers=b).json() == []

    # после отклонения друг может отметить возврат заново
    r = client.post(f"/api/shares/{share_id}/mark-paid", headers=b, json={"category_id": category_id(client, b)})
    assert r.status_code == 200
    assert len(client.get("/api/expenses", headers=b).json()) == 1


def test_payer_can_close_debt_paid_in_cash(client):
    a, b, _ = setup_users(client)
    create_equal(client, a, category_id(client, a))
    share_id = client.get("/api/debts/owed-to-me", headers=a).json()[0]["id"]
    assert client.post(f"/api/shares/{share_id}/confirm", headers=a).json()["status"] == "settled"


def test_wrong_state_transitions_conflict(client):
    a, b, _ = setup_users(client)
    create_equal(client, a, category_id(client, a))
    share_id = client.get("/api/debts/i-owe", headers=b).json()[0]["id"]
    cat_b = category_id(client, b)

    assert client.post(f"/api/shares/{share_id}/reject", headers=a).status_code == 409  # отклонять нечего
    assert client.post(f"/api/shares/{share_id}/mark-paid", headers=b, json={"category_id": cat_b}).status_code == 200
    assert client.post(f"/api/shares/{share_id}/mark-paid", headers=b, json={"category_id": cat_b}).status_code == 409
    assert client.post(f"/api/shares/{share_id}/confirm", headers=a).status_code == 200
    assert client.post(f"/api/shares/{share_id}/confirm", headers=a).status_code == 409


# ---------- права доступа ----------

def test_only_right_person_can_act_on_a_share(client):
    a, b, c = setup_users(client)
    create_equal(client, a, category_id(client, a))
    share_id = client.get("/api/debts/i-owe", headers=b).json()[0]["id"]
    cat = category_id(client, b)

    # друг не может сам подтвердить свой возврат
    assert client.post(f"/api/shares/{share_id}/confirm", headers=b).status_code == 403
    # плательщик не может отметить возврат за друга
    assert client.post(f"/api/shares/{share_id}/mark-paid", headers=a, json={"category_id": cat}).status_code == 403
    # посторонний вообще не видит этот долг
    assert client.post(f"/api/shares/{share_id}/confirm", headers=c).status_code == 404
    assert client.post(f"/api/shares/{share_id}/mark-paid", headers=c, json={"category_id": cat}).status_code == 404
    assert client.post("/api/shares/99999/confirm", headers=a).status_code == 404


def test_friend_sees_only_own_debt_not_other_expenses(client):
    a, b, _ = setup_users(client)
    cat = category_id(client, a)
    client.post("/api/expenses", headers=a, json={"amount": 777, "category_id": cat, "note": "секрет"})
    create_equal(client, a, cat)

    assert client.get("/api/expenses", headers=b).json() == []
    debts = client.get("/api/debts/i-owe", headers=b).json()
    assert len(debts) == 1
    assert "секрет" not in str(debts)


def test_debts_require_login(client):
    assert client.get("/api/debts/i-owe").status_code == 401
    assert client.get("/api/debts/summary").status_code == 401
    assert client.post("/api/shares/1/confirm").status_code == 401


# ---------- изменение и удаление разделённой траты ----------

def test_split_expense_amount_cannot_change_but_note_can(client):
    a, _, _ = setup_users(client)
    expense = create_equal(client, a, category_id(client, a))

    r = client.put(f"/api/expenses/{expense['id']}", headers=a, json={"amount": 5000})
    assert r.status_code == 409
    r = client.put(f"/api/expenses/{expense['id']}", headers=a, json={"amount": expense["amount"], "note": "ужин"})
    assert r.status_code == 200
    assert r.json()["note"] == "ужин"


def test_delete_split_expense_removes_pending_debts(client):
    a, b, _ = setup_users(client)
    expense = create_equal(client, a, category_id(client, a))
    assert client.delete(f"/api/expenses/{expense['id']}", headers=a).status_code == 204
    assert client.get("/api/debts/i-owe", headers=b).json() == []
    assert client.get("/api/debts/owed-to-me", headers=a).json() == []


def test_cannot_delete_split_expense_after_friend_paid(client):
    a, b, _ = setup_users(client)
    expense = create_equal(client, a, category_id(client, a))
    share_id = client.get("/api/debts/i-owe", headers=b).json()[0]["id"]
    client.post(f"/api/shares/{share_id}/mark-paid", headers=b, json={"category_id": category_id(client, b)})

    assert client.delete(f"/api/expenses/{expense['id']}", headers=a).status_code == 409
    assert len(client.get("/api/expenses", headers=a).json()) == 1


# ---------- обслуживание ----------

def test_preview_reports_service(client):
    a, _, _ = setup_users(client)
    body = {"amount": 9000, "split": {"mode": "equal", "participants": [{"email": B}, {"email": C}], "tip_percent": 10}}
    data = client.post("/api/expenses/split-preview", headers=a, json=body).json()
    assert data["service"] == 900
    assert data["total"] == 9900
    assert data["my_share"] == 3300
