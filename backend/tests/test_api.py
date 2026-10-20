from datetime import date

from tests.conftest import register_and_login


def first_category_id(client, headers) -> int:
    return client.get("/api/categories", headers=headers).json()[0]["id"]


# ---------- auth ----------

def test_register_and_login(client):
    r = client.post("/api/auth/register", json={"email": "a@example.com", "password": "password123"})
    assert r.status_code == 201
    assert r.json()["role"] == "student"

    r = client.post("/api/auth/login", json={"email": "a@example.com", "password": "password123"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "a@example.com"


def test_duplicate_email_rejected(client):
    body = {"email": "dup@example.com", "password": "password123"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    assert client.post("/api/auth/register", json=body).status_code == 409


def test_short_password_rejected(client):
    r = client.post("/api/auth/register", json={"email": "b@example.com", "password": "123"})
    assert r.status_code == 422


def test_wrong_password_rejected(client):
    client.post("/api/auth/register", json={"email": "c@example.com", "password": "password123"})
    r = client.post("/api/auth/login", json={"email": "c@example.com", "password": "wrongpass1"})
    assert r.status_code == 401


def test_protected_route_requires_token(client):
    assert client.get("/api/expenses").status_code == 401


# ---------- expenses ----------

def test_expense_crud(client, auth_headers):
    cat = first_category_id(client, auth_headers)

    r = client.post("/api/expenses", headers=auth_headers, json={"amount": 1500, "category_id": cat, "note": "обед"})
    assert r.status_code == 201
    expense_id = r.json()["id"]

    assert len(client.get("/api/expenses", headers=auth_headers).json()) == 1

    r = client.put(f"/api/expenses/{expense_id}", headers=auth_headers, json={"amount": 2000})
    assert r.status_code == 200
    assert r.json()["amount"] == 2000

    assert client.delete(f"/api/expenses/{expense_id}", headers=auth_headers).status_code == 204
    assert client.get("/api/expenses", headers=auth_headers).json() == []


def test_negative_amount_rejected(client, auth_headers):
    cat = first_category_id(client, auth_headers)
    r = client.post("/api/expenses", headers=auth_headers, json={"amount": -5, "category_id": cat})
    assert r.status_code == 422


def test_cannot_touch_other_users_expense(client, auth_headers):
    cat = first_category_id(client, auth_headers)
    expense_id = client.post(
        "/api/expenses", headers=auth_headers, json={"amount": 100, "category_id": cat}
    ).json()["id"]

    other = register_and_login(client, "other@example.com")
    assert client.put(f"/api/expenses/{expense_id}", headers=other, json={"amount": 1}).status_code == 403
    assert client.delete(f"/api/expenses/{expense_id}", headers=other).status_code == 403
    assert client.get("/api/expenses", headers=other).json() == []


def test_expense_filter_by_category(client, auth_headers):
    cats = client.get("/api/categories", headers=auth_headers).json()
    client.post("/api/expenses", headers=auth_headers, json={"amount": 100, "category_id": cats[0]["id"]})
    client.post("/api/expenses", headers=auth_headers, json={"amount": 200, "category_id": cats[1]["id"]})
    r = client.get(f"/api/expenses?category_id={cats[1]['id']}", headers=auth_headers)
    assert [e["amount"] for e in r.json()] == [200]


# ---------- categories ----------

def test_personal_category_visible_only_to_owner(client, auth_headers):
    r = client.post("/api/categories", headers=auth_headers, json={"name": "Кофе", "icon": "☕"})
    assert r.status_code == 201
    assert "Кофе" in [c["name"] for c in client.get("/api/categories", headers=auth_headers).json()]

    other = register_and_login(client, "other@example.com")
    assert "Кофе" not in [c["name"] for c in client.get("/api/categories", headers=other).json()]


# ---------- budget ----------

def test_budget_summary(client, auth_headers):
    cat = first_category_id(client, auth_headers)
    month = date.today().strftime("%Y-%m")

    assert client.get("/api/budget/summary", headers=auth_headers).status_code == 404

    r = client.put("/api/budgets", headers=auth_headers, json={"month": month, "limit_amount": 10000})
    assert r.status_code == 200

    client.post("/api/expenses", headers=auth_headers, json={"amount": 2500, "category_id": cat})
    client.post(
        "/api/expenses", headers=auth_headers, json={"amount": 9999, "category_id": cat, "type": "income"}
    )  # доходы в расход не входят

    s = client.get("/api/budget/summary", headers=auth_headers).json()
    assert s["limit"] == 10000
    assert s["spent"] == 2500
    assert s["remaining"] == 7500
    assert s["percent_used"] == 25.0
    assert s["days_left"] >= 1
    assert s["daily_limit"] > 0


def test_budget_update_does_not_duplicate(client, auth_headers):
    month = date.today().strftime("%Y-%m")
    client.put("/api/budgets", headers=auth_headers, json={"month": month, "limit_amount": 5000})
    client.put("/api/budgets", headers=auth_headers, json={"month": month, "limit_amount": 7000})
    budgets = client.get(f"/api/budgets?month={month}", headers=auth_headers).json()
    assert len(budgets) == 1
    assert budgets[0]["limit_amount"] == 7000


def test_invalid_month_rejected(client, auth_headers):
    r = client.put("/api/budgets", headers=auth_headers, json={"month": "2026-13", "limit_amount": 100})
    assert r.status_code == 422


# ---------- admin ----------

def test_admin_routes_forbidden_for_student(client, auth_headers):
    assert client.get("/api/admin/users", headers=auth_headers).status_code == 403


def test_admin_can_list_and_block_users(client, admin_headers):
    student = client.post("/api/auth/register", json={"email": "s@example.com", "password": "password123"}).json()
    assert len(client.get("/api/admin/users", headers=admin_headers).json()) == 2

    r = client.patch(f"/api/admin/users/{student['id']}/block", headers=admin_headers)
    assert r.status_code == 200

    r = client.post("/api/auth/login", json={"email": "s@example.com", "password": "password123"})
    assert r.status_code == 403


def test_assistant_requires_auth(client):
    assert client.post("/api/assistant/chat", json={"messages": [{"role": "user", "content": "hi"}]}).status_code == 401


def test_assistant_reply_gets_user_context(client, auth_headers, monkeypatch):
    from app.routers import assistant

    cat = first_category_id(client, auth_headers)
    client.post("/api/expenses", headers=auth_headers, json={"amount": 1500, "category_id": cat, "note": "обед"})
    client.put("/api/budgets", headers=auth_headers, json={"month": date.today().strftime("%Y-%m"), "limit_amount": 60000})

    sent = {}

    def fake_ollama(messages):
        sent["messages"] = messages
        return "Ответ ассистента"

    monkeypatch.setattr(assistant, "ask_ollama", fake_ollama)
    resp = client.post(
        "/api/assistant/chat", headers=auth_headers, json={"messages": [{"role": "user", "content": "Как мои траты?"}]}
    )
    assert resp.status_code == 200
    assert resp.json() == {"reply": "Ответ ассистента"}
    system = sent["messages"][0]
    assert system["role"] == "system"
    assert "1500" in system["content"] and "60000" in system["content"] and "обед" in system["content"]
    assert "student@example.com" not in system["content"]


def test_assistant_unavailable_returns_503(client, auth_headers, monkeypatch):
    from app.routers import assistant

    monkeypatch.setattr(assistant, "OLLAMA_URL", "http://127.0.0.1:9")  # там никого нет
    resp = client.post(
        "/api/assistant/chat", headers=auth_headers, json={"messages": [{"role": "user", "content": "привет"}]}
    )
    assert resp.status_code == 503


def test_assistant_last_message_must_be_user(client, auth_headers):
    resp = client.post(
        "/api/assistant/chat", headers=auth_headers, json={"messages": [{"role": "assistant", "content": "привет"}]}
    )
    assert resp.status_code == 400
