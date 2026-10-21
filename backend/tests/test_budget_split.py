from datetime import date

from app.budget_split import amounts_from_percents, baseline_percents, validate_ai_percents
from app.routers import ai

NAMES = ["Food", "Housing", "Transport", "Education", "Entertainment", "Subscriptions", "Savings", "Other"]
MONTH = date.today().strftime("%Y-%m")


def test_baseline_sums_to_100_and_skips_unknown_categories():
    p = baseline_percents(NAMES)
    assert round(sum(p.values())) == 100 and p["Food"] == 30
    p2 = baseline_percents(["Food", "Transport", "My custom"])
    assert set(p2) == {"Food", "Transport"} and round(sum(p2.values())) == 100


def test_history_shifts_the_baseline():
    plain = baseline_percents(NAMES)
    mixed = baseline_percents(NAMES, {"Entertainment": 90000, "Food": 10000})
    assert mixed["Entertainment"] > plain["Entertainment"]
    assert round(sum(mixed.values())) == 100


def test_amounts_add_up_exactly():
    for total in (60000, 99999, 1, 12345):
        amounts = amounts_from_percents(baseline_percents(NAMES), total)
        assert sum(amounts.values()) == total


def test_validate_ai_percents():
    ok = validate_ai_percents({"food": 40, "Transport": 20, "Savings": 40}, NAMES)
    assert ok and round(sum(ok.values())) == 100 and "Food" in ok
    assert validate_ai_percents({"Food": 50, "Unknown": 50}, NAMES) is None  # чужая категория
    assert validate_ai_percents({"Food": 10, "Transport": 10}, NAMES) is None  # сумма далека от 100
    assert validate_ai_percents({"Food": -5, "Transport": 105}, NAMES) is None
    assert validate_ai_percents({"Food": "lots"}, NAMES) is None
    assert validate_ai_percents(None, NAMES) is None


def set_budget(client, headers, amount=60000):
    assert client.put("/api/budgets", headers=headers, json={"month": MONTH, "limit_amount": amount}).status_code == 200


def test_split_requires_budget_and_auth(client, auth_headers):
    assert client.get("/api/ai/budget-split").status_code == 401
    assert client.get("/api/ai/budget-split", headers=auth_headers).status_code == 404


def test_split_falls_back_to_rules_when_ai_unavailable(client, auth_headers, monkeypatch):
    monkeypatch.setattr(ai.assistant, "OLLAMA_URL", "http://127.0.0.1:9")
    set_budget(client, auth_headers)
    r = client.get("/api/ai/budget-split", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "rules" and body["total"] == 60000
    assert sum(i["amount"] for i in body["items"]) == 60000
    assert {i["category"] for i in body["items"]} >= {"Food", "Housing", "Savings"}
    assert "Transfers" not in {i["category"] for i in body["items"]}


def test_split_uses_valid_ai_answer(client, auth_headers, monkeypatch):
    monkeypatch.setattr(ai, "ask_ai_for_split", lambda *a: ({"Food": 50, "Savings": 30, "Transport": 20}, "Cook at home."))
    set_budget(client, auth_headers, 100000)
    body = client.get("/api/ai/budget-split", headers=auth_headers).json()
    assert body["source"] == "ai" and body["tip"] == "Cook at home."
    assert {i["category"]: i["amount"] for i in body["items"]} == {"Food": 50000, "Savings": 30000, "Transport": 20000}


def test_split_ignores_bad_ai_answer(client, auth_headers, monkeypatch):
    monkeypatch.setattr(ai, "ask_ai_for_split", lambda *a: ({"Food": 500}, "x"))
    set_budget(client, auth_headers)
    body = client.get("/api/ai/budget-split", headers=auth_headers).json()
    assert body["source"] == "rules" and sum(i["amount"] for i in body["items"]) == 60000


def test_split_uses_history(client, auth_headers, monkeypatch):
    monkeypatch.setattr(ai, "ask_ai_for_split", lambda *a: (None, None))
    cats = {c["name"]: c["id"] for c in client.get("/api/categories", headers=auth_headers).json()}
    today = date.today()
    prev = date(today.year - 1, 12, 15) if today.month == 1 else date(today.year, today.month - 1, 15)
    client.post("/api/expenses", headers=auth_headers, json={"amount": 90000, "category_id": cats["Entertainment"], "spent_at": prev.isoformat()})
    set_budget(client, auth_headers)
    plain = {i["category"]: i["amount"] for i in client.get("/api/ai/budget-split", headers=auth_headers).json()["items"]}
    assert plain["Entertainment"] > 6000  # заметно выше базовых 10% из-за истории


def test_save_split(client, auth_headers):
    cats = {c["name"]: c["id"] for c in client.get("/api/categories", headers=auth_headers).json()}
    body = {"month": MONTH, "items": [{"category_id": cats["Food"], "limit_amount": 20000}, {"category_id": cats["Savings"], "limit_amount": 5000}]}
    assert client.put("/api/budgets/split", headers=auth_headers, json=body).json() == {"saved": 2}
    body["items"][0]["limit_amount"] = 25000  # повторное сохранение обновляет, а не дублирует
    client.put("/api/budgets/split", headers=auth_headers, json=body)
    limits = {b["category_id"]: b["limit_amount"] for b in client.get("/api/budgets", headers=auth_headers, params={"month": MONTH}).json()}
    assert limits == {cats["Food"]: 25000, cats["Savings"]: 5000}


def test_save_split_validation(client, auth_headers):
    cats = {c["name"]: c["id"] for c in client.get("/api/categories", headers=auth_headers).json()}
    item = {"category_id": cats["Food"], "limit_amount": 100}
    assert client.put("/api/budgets/split", headers=auth_headers, json={"month": MONTH, "items": [item, item]}).status_code == 400
    assert client.put("/api/budgets/split", headers=auth_headers, json={"month": MONTH, "items": [{"category_id": 9999, "limit_amount": 1}]}).status_code == 400
    assert client.put("/api/budgets/split", headers=auth_headers, json={"month": MONTH, "items": [{"category_id": cats["Food"], "limit_amount": 0}]}).status_code == 422
    assert client.put("/api/budgets/split", json={"month": MONTH, "items": [item]}).status_code == 401
