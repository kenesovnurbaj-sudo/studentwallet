"""Прогноз расходов за месяц и предупреждения «тратите слишком быстро» (история 7).

Чистая функция без БД: принимает лимит, уже потраченное и сегодняшнюю дату, поэтому легко тестируется.
Прогноз линейный: средний расход в день с начала месяца, умноженный на длину месяца. Если в начале месяца была
крупная разовая трата, прогноз будет завышен, поэтому первые дни месяца прогнозом не считаем.
"""
import calendar
import math
from dataclasses import dataclass, field
from datetime import date, timedelta

MIN_DAYS_FOR_FORECAST = 3
WATCH_SHARE = 0.8  # предупреждение при 80% бюджета (как в плане проекта)
PROJECTION_WATCH = 0.9  # «близко к лимиту», если прогноз выше 90% лимита


@dataclass
class Alert:
    code: str  # exceeded | run_out | used_80 | on_track | not_enough_data | month_finished
    level: str  # ok | watch | danger | exceeded | info
    message: str


@dataclass
class Forecast:
    month: str
    limit: float
    spent: float
    days_in_month: int
    days_elapsed: int
    daily_average: float | None
    projected_total: float | None
    run_out_date: date | None
    days_early: int | None
    safe_daily_limit: float | None
    level: str  # ok | watch | danger | exceeded | info
    alerts: list[Alert] = field(default_factory=list)


def _money(value: float) -> str:
    return f"₸{value:,.0f}"


def build_forecast(month: str, limit: float, spent: float, today: date) -> Forecast:
    year, mon = int(month[:4]), int(month[5:7])
    days_in_month = calendar.monthrange(year, mon)[1]
    first_day, last_day = date(year, mon, 1), date(year, mon, days_in_month)

    if today < first_day:
        elapsed = 0
    elif today > last_day:
        elapsed = days_in_month
    else:
        elapsed = today.day
    in_month = first_day <= today <= last_day
    days_left = days_in_month - elapsed + 1 if in_month else 0

    f = Forecast(
        month=month, limit=round(limit, 2), spent=round(spent, 2), days_in_month=days_in_month, days_elapsed=elapsed,
        daily_average=None, projected_total=None, run_out_date=None, days_early=None, safe_daily_limit=None, level="ok",
    )
    if in_month and spent < limit and days_left > 0:
        f.safe_daily_limit = round((limit - spent) / days_left, 2)

    # 1. Бюджет уже исчерпан
    if spent >= limit:
        over = spent - limit
        text = f"You have used your whole budget: {_money(spent)} of {_money(limit)}."
        if over > 0:
            text = f"You are over your budget by {_money(over)}: {_money(spent)} of {_money(limit)}."
        f.level = "exceeded"
        f.alerts.append(Alert("exceeded", "exceeded", text))
        return f

    # 2. Месяц закончился или ещё не начался
    if today > last_day:
        f.alerts.append(Alert("month_finished", "info", f"The month is over: you spent {_money(spent)} of {_money(limit)}."))
        f.level = "info"
        return f
    if elapsed < MIN_DAYS_FOR_FORECAST:
        f.level = "info"
        f.alerts.append(Alert("not_enough_data", "info", "Not enough data yet for a forecast. Check back after a few days of spending."))
        if spent / limit >= WATCH_SHARE:
            f.level = "watch"
            f.alerts.insert(0, Alert("used_80", "watch", f"You have already spent {spent / limit:.0%} of your budget."))
        return f

    # 3. Прогноз по темпу трат
    f.daily_average = round(spent / elapsed, 2)
    f.projected_total = round(spent / elapsed * days_in_month, 2)

    if f.projected_total > limit and f.daily_average > 0:
        run_out_day = max(math.ceil(limit / f.daily_average), elapsed + 1)
        f.run_out_date = first_day + timedelta(days=run_out_day - 1)
        f.days_early = max(days_in_month - run_out_day, 0)
        f.level = "danger"
        when = f"{f.run_out_date.strftime('%b')} {f.run_out_date.day}"
        early = f", {f.days_early} {'day' if f.days_early == 1 else 'days'} before the month ends" if f.days_early else ""
        tip = f" Try to keep spending under {_money(f.safe_daily_limit)} per day." if f.safe_daily_limit else ""
        f.alerts.append(Alert("run_out", "danger", f"At this pace your budget runs out on {when}{early}.{tip}"))
    elif f.projected_total >= PROJECTION_WATCH * limit:
        f.level = "watch"
        f.alerts.append(
            Alert("run_out", "watch", f"You are close to the limit: projected spending is {_money(f.projected_total)} of {_money(limit)}.")
        )
    elif spent == 0:
        f.alerts.append(Alert("on_track", "ok", "No spending recorded yet this month."))
    else:
        f.alerts.append(Alert("on_track", "ok", f"You are on track: projected spending is {_money(f.projected_total)} of {_money(limit)}."))

    if spent / limit >= WATCH_SHARE:
        f.level = "danger" if f.level == "danger" else "watch"
        f.alerts.append(Alert("used_80", "watch", f"You have already spent {spent / limit:.0%} of your budget."))
    return f
