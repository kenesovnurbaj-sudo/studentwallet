"""Регрессионные тесты на баги из QA-отчёта (Sprint review, октябрь 2026)."""
from datetime import timedelta

import jwt

from app.clock import current_month, today
from tests.conftest import register_and_login


def first_category_id(client, headers) -> int:
    return client.get("/api/categories", headers=headers).json()[0]["id"]


# ---------- HIGH: длинный пароль ронял сервер с 500 ----------

def test_long_cyrillic_password_rejected_on_register(client):
    # 40 кириллических символов = 80 байт, больше лимита bcrypt (72 байта)
    password = "пароль1" + "я" * 33
    r = client.post("/api/auth/register", json={"email": "ru@example.com", "password": password})
    assert r.status_code == 422


def test_long_password_on_login_is_401_not_500(client):
    client.post("/api/auth/register", json={"email": "long@example.com", "password": "password123"})
    r = client.post("/api/auth/login", json={"email": "long@example.com", "password": "ж" * 200})
    assert r.status_code == 401


def test_cyrillic_password_within_limit_works(client):
    password = "пароль2026"  # 6 * 2 + 4 = 16 байт
    body = {"email": "cyr@example.com", "password": password}
    assert client.post("/api/auth/register", json=body).status_code == 201
    assert client.post("/api/auth/login", json=body).status_code == 200


# ---------- HIGH: публичный JWT-ключ по умолчанию ----------

def test_token_signed_with_old_default_key_rejected(client, auth_headers):
    me = client.get("/api/auth/me", headers=auth_headers).json()
    forged = jwt.encode({"sub": str(me["id"])}, "dev-secret-change-me", algorithm="HS256")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_secret_key_is_not_the_public_default():
    from app.security import SECRET_KEY

    assert SECRET_KEY != "dev-secret-change-me"
    assert len(SECRET_KEY) >= 32


# ---------- HIGH + LOW: 0.001 сохранялся как 0 и ломал summary ----------

def test_budget_with_three_decimals_rejected(client, auth_headers):
    r = client.put("/api/budgets", headers=auth_headers, json={"month": current_month(), "limit_amount": 0.001})
    assert r.status_code == 422
    assert client.get("/api/budget/summary", headers=auth_headers).status_code == 404


def test_expense_with_three_decimals_rejected(client, auth_headers):
    cat = first_category_id(client, auth_headers)
    r = client.post("/api/expenses", headers=auth_headers, json={"amount": 0.001, "category_id": cat})
    assert r.status_code == 422


def test_amount_with_two_decimals_saved_exactly(client, auth_headers):
    cat = first_category_id(client, auth_headers)
    r = client.post("/api/expenses", headers=auth_headers, json={"amount": 1499.99, "category_id": cat})
    assert r.status_code == 201
    assert r.json()["amount"] == 1499.99


def test_summary_survives_zero_limit_from_old_database(client, auth_headers, db_session):
    from app.models import Budget, User

    user = db_session.query(User).filter_by(email="student@example.com").one()
    db_session.add(Budget(user_id=user.id, month=current_month(), category_id=None, limit_amount=0))
    db_session.commit()
    r = client.get("/api/budget/summary", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["percent_used"] == 0.0


# ---------- MEDIUM: трата с датой из будущего ----------

def test_future_date_rejected_on_create(client, auth_headers):
    cat = first_category_id(client, auth_headers)
    tomorrow = (today() + timedelta(days=1)).isoformat()
    r = client.post(
        "/api/expenses", headers=auth_headers, json={"amount": 100, "category_id": cat, "spent_at": tomorrow}
    )
    assert r.status_code == 422


def test_future_date_rejected_on_update(client, auth_headers):
    cat = first_category_id(client, auth_headers)
    expense_id = client.post(
        "/api/expenses", headers=auth_headers, json={"amount": 100, "category_id": cat}
    ).json()["id"]
    tomorrow = (today() + timedelta(days=1)).isoformat()
    r = client.put(f"/api/expenses/{expense_id}", headers=auth_headers, json={"spent_at": tomorrow})
    assert r.status_code == 422


def test_today_and_past_dates_accepted(client, auth_headers):
    cat = first_category_id(client, auth_headers)
    for day in (today(), today() - timedelta(days=30)):
        r = client.post(
            "/api/expenses",
            headers=auth_headers,
            json={"amount": 100, "category_id": cat, "spent_at": day.isoformat()},
        )
        assert r.status_code == 201


# ---------- MEDIUM: бюджет на несуществующую или чужую категорию ----------

def test_budget_for_unknown_category_rejected(client, auth_headers):
    r = client.put(
        "/api/budgets",
        headers=auth_headers,
        json={"month": current_month(), "limit_amount": 1000, "category_id": 99999},
    )
    assert r.status_code == 400


def test_budget_for_other_users_category_rejected(client, auth_headers):
    other = register_and_login(client, "other@example.com")
    foreign_cat = client.post("/api/categories", headers=other, json={"name": "Чужая"}).json()["id"]
    r = client.put(
        "/api/budgets",
        headers=auth_headers,
        json={"month": current_month(), "limit_amount": 1000, "category_id": foreign_cat},
    )
    assert r.status_code == 400


def test_budget_for_own_and_global_category_allowed(client, auth_headers):
    own = client.post("/api/categories", headers=auth_headers, json={"name": "Кофе"}).json()["id"]
    glob = first_category_id(client, auth_headers)
    for cat in (own, glob):
        r = client.put(
            "/api/budgets",
            headers=auth_headers,
            json={"month": current_month(), "limit_amount": 1000, "category_id": cat},
        )
        assert r.status_code == 200


# ---------- LOW: пустые и повторяющиеся категории ----------

def test_blank_category_name_rejected(client, auth_headers):
    for name in ("", "   ", "\t"):
        r = client.post("/api/categories", headers=auth_headers, json={"name": name})
        assert r.status_code == 422, name


def test_category_name_is_trimmed(client, auth_headers):
    r = client.post("/api/categories", headers=auth_headers, json={"name": "  Спорт   зал "})
    assert r.status_code == 201
    assert r.json()["name"] == "Спорт зал"


def test_duplicate_category_rejected_case_insensitive(client, auth_headers):
    assert client.post("/api/categories", headers=auth_headers, json={"name": "Кофе"}).status_code == 201
    assert client.post("/api/categories", headers=auth_headers, json={"name": "кофе"}).status_code == 409
    # совпадение с глобальной категорией "Еда"
    assert client.post("/api/categories", headers=auth_headers, json={"name": "ЕДА"}).status_code == 409


def test_same_category_name_allowed_for_different_users(client, auth_headers):
    assert client.post("/api/categories", headers=auth_headers, json={"name": "Кофе"}).status_code == 201
    other = register_and_login(client, "other@example.com")
    assert client.post("/api/categories", headers=other, json={"name": "Кофе"}).status_code == 201


# ---------- LOW: пароль из пробелов, нет максимальной суммы ----------

def test_password_of_spaces_rejected(client):
    r = client.post("/api/auth/register", json={"email": "sp@example.com", "password": " " * 10})
    assert r.status_code == 422


def test_password_without_digit_or_letter_rejected(client):
    for password in ("onlyletters", "12345678"):
        r = client.post("/api/auth/register", json={"email": "pw@example.com", "password": password})
        assert r.status_code == 422, password


def test_huge_amount_rejected(client, auth_headers):
    cat = first_category_id(client, auth_headers)
    r = client.post("/api/expenses", headers=auth_headers, json={"amount": 10**15, "category_id": cat})
    assert r.status_code == 422
    r = client.put("/api/budgets", headers=auth_headers, json={"month": current_month(), "limit_amount": 10**15})
    assert r.status_code == 422
