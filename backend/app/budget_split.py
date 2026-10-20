"""Расчёт предложения по разделению месячного бюджета на категории.

Здесь только чистые функции. Базовая схема работает без ИИ; модель (см. routers/ai.py) может предложить свои
проценты, но результат всегда проверяется и приводится к точной сумме бюджета.
"""

# Типичное распределение для студента, в процентах. Категорий нет в списке пользователя, пропускаем и пересчитываем.
BASELINE = {
    "Food": 30,
    "Housing": 20,
    "Transport": 10,
    "Education": 10,
    "Entertainment": 10,
    "Subscriptions": 5,
    "Savings": 10,
    "Other": 5,
}
HISTORY_WEIGHT = 0.5  # какую долю в смеси занимают реальные траты пользователя за прошлые месяцы


def normalize_percents(raw: dict[str, float]) -> dict[str, float]:
    total = sum(v for v in raw.values() if v > 0)
    if total <= 0:
        return {}
    return {k: v / total * 100 for k, v in raw.items() if v > 0}


def baseline_percents(names: list[str], history: dict[str, float] | None = None) -> dict[str, float]:
    """Базовая схема, а при наличии истории трат смесь «типичное + как тратил сам»."""
    base = normalize_percents({n: BASELINE[n] for n in names if n in BASELINE})
    hist = normalize_percents({n: v for n, v in (history or {}).items() if n in names and n != "Transfers"})
    if not hist:
        return base
    mixed = {n: (1 - HISTORY_WEIGHT) * base.get(n, 0) + HISTORY_WEIGHT * hist.get(n, 0) for n in set(base) | set(hist)}
    return normalize_percents(mixed)


def validate_ai_percents(answer: object, names: list[str]) -> dict[str, float] | None:
    """Проверяет ответ модели: только известные категории, неотрицательные числа, сумма примерно 100."""
    if not isinstance(answer, dict):
        return None
    lower = {n.lower(): n for n in names}
    out: dict[str, float] = {}
    for key, value in answer.items():
        name = lower.get(str(key).strip().lower())
        if name is None or isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            return None
        out[name] = out.get(name, 0) + float(value)
    if not out or not 80 <= sum(out.values()) <= 120:
        return None
    return normalize_percents(out)


def amounts_from_percents(percents: dict[str, float], total: float) -> dict[str, int]:
    """Целые суммы, которые в сумме дают ровно total (метод наибольших остатков)."""
    whole = int(round(total))
    exact = {k: v / 100 * whole for k, v in percents.items()}
    result = {k: int(v) for k, v in exact.items()}
    left = whole - sum(result.values())
    for k in sorted(exact, key=lambda k: exact[k] - result[k], reverse=True)[: max(left, 0)]:
        result[k] += 1
    return result
