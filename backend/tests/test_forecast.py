from datetime import date

from app.forecast import build_forecast

MONTH = "2026-10"  # 31 день


def codes(f):
    return [a.code for a in f.alerts]


def test_on_track():
    f = build_forecast(MONTH, 60000, 10000, date(2026, 10, 10))  # 1000 в день -> 31000 за месяц
    assert f.level == "ok" and codes(f) == ["on_track"]
    assert f.daily_average == 1000 and f.projected_total == 31000


def test_spending_too_fast_gives_run_out_date():
    f = build_forecast(MONTH, 60000, 40000, date(2026, 10, 10))  # 4000 в день -> 124000 за месяц
    assert f.level == "danger" and "run_out" in codes(f)
    assert f.run_out_date == date(2026, 10, 15)  # 4000 * 15 = 60000
    assert f.days_early == 16
    msg = f.alerts[0].message
    assert "Oct 15" in msg and "16 days before the month ends" in msg and "₸" in msg


def test_close_to_limit_is_watch():
    f = build_forecast(MONTH, 60000, 18000, date(2026, 10, 10))  # 1800 в день -> 55800 (93%)
    assert f.level == "watch" and f.run_out_date is None


def test_80_percent_alert_added():
    f = build_forecast(MONTH, 60000, 50000, date(2026, 10, 28))  # 80%+, но темп укладывается
    assert "used_80" in codes(f) and f.level in ("watch", "danger")


def test_budget_exceeded():
    f = build_forecast(MONTH, 60000, 65000, date(2026, 10, 20))
    assert f.level == "exceeded" and codes(f) == ["exceeded"] and "over your budget by ₸5,000" in f.alerts[0].message
    assert build_forecast(MONTH, 60000, 60000, date(2026, 10, 20)).alerts[0].message.startswith("You have used your whole budget")


def test_first_days_have_no_forecast():
    f = build_forecast(MONTH, 60000, 20000, date(2026, 10, 2))  # день 2: крупная покупка не должна давать паническую оценку
    assert f.projected_total is None and codes(f) == ["not_enough_data"] and f.level == "info"


def test_finished_and_future_months():
    done = build_forecast(MONTH, 60000, 30000, date(2026, 11, 5))
    assert codes(done) == ["month_finished"] and done.projected_total is None
    future = build_forecast("2026-12", 60000, 0, date(2026, 10, 20))
    assert future.level == "info" and future.projected_total is None


def test_safe_daily_limit_uses_remaining_days():
    f = build_forecast(MONTH, 60000, 30000, date(2026, 10, 16))  # осталось 16 дней включая сегодня
    assert f.safe_daily_limit == 1875.0


def test_endpoint(client, auth_headers):
    month = date.today().strftime("%Y-%m")
    assert client.get("/api/budget/forecast", headers=auth_headers).status_code == 404
    client.put("/api/budgets", headers=auth_headers, json={"month": month, "limit_amount": 60000})
    r = client.get("/api/budget/forecast", headers=auth_headers)
    assert r.status_code == 200 and r.json()["alerts"] and r.json()["limit"] == 60000
    assert client.get("/api/budget/forecast").status_code == 401


def test_no_spending():
    f = build_forecast(MONTH, 60000, 0, date(2026, 10, 20))
    assert f.level == "ok" and f.alerts[0].message == "No spending recorded yet this month."
