from datetime import date, timedelta

import pytest

from app.expense_parser import parse_expense_text
from app.routers import ai

TODAY = date(2026, 10, 20)


@pytest.mark.parametrize(
    "text, amount, note",
    [
        ("lunch at canteen 2500", 2500, "lunch at canteen"),
        ("2500 lunch at canteen", 2500, "lunch at canteen"),
        ("taxi 15 000 ₸", 15000, "taxi"),
        ("bought headphones for 15,000 tg", 15000, "bought headphones for"),
        ("coffee 1.5k", 1500, "coffee"),
        ("coffee 2,50", 2.5, "coffee"),
        ("2 coffees for 1500", 1500, "2 coffees for"),
        ("обед в столовой 2500 тенге", 2500, "обед в столовой"),
        ("lunch 2500 market", 2500, "lunch market"),
        ("taxi to university yesterday 1 800 ₸", 1800, "taxi to university"),
    ],
)
def test_amount_and_note(text, amount, note):
    parsed = parse_expense_text(text, TODAY)
    assert parsed is not None and parsed.amount == amount and parsed.note == note


def test_no_amount_returns_none():
    assert parse_expense_text("lunch at canteen", TODAY) is None


def test_dates():
    assert parse_expense_text("lunch 2500 yesterday", TODAY).spent_at == TODAY - timedelta(days=1)
    assert parse_expense_text("вчера такси 1200", TODAY).spent_at == TODAY - timedelta(days=1)
    assert parse_expense_text("lunch 2500 on 15.10", TODAY).spent_at == date(2026, 10, 15)
    # дата не принимается за сумму
    p = parse_expense_text("lunch 2500 on 20 october", TODAY)
    assert p.amount == 2500


def test_income_detected():
    assert parse_expense_text("scholarship 50000", TODAY).type == "income"
    assert parse_expense_text("lunch 2500", TODAY).type == "expense"


def test_endpoint_rules_without_ai(client, auth_headers, monkeypatch):
    def boom(text, names):
        raise AssertionError("AI must not be asked when rules know the category")

    monkeypatch.setattr(ai, "pick_category_with_ai", boom)
    r = client.post("/api/ai/parse-expense", headers=auth_headers, json={"text": "lunch at canteen 2500"})
    assert r.status_code == 200
    body = r.json()
    assert (body["amount"], body["category"], body["source"], body["type"]) == (2500, "Food", "rules", "expense")


def test_endpoint_asks_ai_when_rules_unsure(client, auth_headers, monkeypatch):
    monkeypatch.setattr(ai, "pick_category_with_ai", lambda text, names: "Education" if "Education" in names else None)
    r = client.post("/api/ai/parse-expense", headers=auth_headers, json={"text": "printing lab report 600"})
    body = r.json()
    assert (body["category"], body["source"]) == ("Education", "ai")


def test_endpoint_falls_back_when_ai_unavailable(client, auth_headers, monkeypatch):
    monkeypatch.setattr(ai.assistant, "OLLAMA_URL", "http://127.0.0.1:9")
    r = client.post("/api/ai/parse-expense", headers=auth_headers, json={"text": "printing lab report 600"})
    assert r.status_code == 200
    assert (r.json()["category"], r.json()["source"]) == ("Other", "rules")


def test_endpoint_errors(client, auth_headers):
    assert client.post("/api/ai/parse-expense", headers=auth_headers, json={"text": "lunch"}).status_code == 422
    assert client.post("/api/ai/parse-expense", json={"text": "lunch 100"}).status_code == 401
