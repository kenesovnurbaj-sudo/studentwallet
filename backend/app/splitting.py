"""Деление общего счёта между друзьями.

Здесь только арифметика, без базы и без FastAPI, поэтому её легко проверять тестами.
Все суммы внутри считаются в целых «копейках» (сотых долях), чтобы не терять деньги на округлении.

Три режима:
  equal  - поровну между вами и друзьями
  custom - вы вводите сумму каждого друга, остаток остаётся вам
  items  - по блюдам: у каждой позиции отмечено, кто её ел

Во всех режимах можно добавить процент обслуживания: он ложится сверху чека
и делится пропорционально тому, сколько заказал каждый.
"""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

ME = "me"  # так в позициях обозначается плательщик


class SplitError(ValueError):
    """Ошибка в данных деления. Текст показывается пользователю."""


@dataclass
class SplitResult:
    total: int  # сумма всего чека
    mine: int  # доля плательщика
    friends: dict[str, int] = field(default_factory=dict)  # email -> доля друга
    service: int = 0  # сколько из total составляет обслуживание (процент к чеку)


def to_cents(value) -> int:
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_cents(cents: int) -> float:
    return round(cents / 100, 2)


def _norm(email: str) -> str:
    return email.strip().lower()


def split_evenly(total: int, keys: list[str], lead: str = ME) -> dict[str, int]:
    """Делит сумму поровну. Если не делится нацело, остаток достаётся lead (плательщику).

    Целая сумма делится целыми единицами валюты: 10 000 на троих = 3 334 + 3 333 + 3 333.
    Если у суммы есть копейки, делим копейками.
    """
    unit = 100 if total % 100 == 0 else 1
    base, extra = divmod(total // unit, len(keys))
    out = {key: base * unit for key in keys}
    out[lead if lead in out else keys[0]] += extra * unit
    return out


def distribute_proportionally(amount: int, weights: dict[str, int]) -> dict[str, int]:
    """Делит amount пропорционально весам так, чтобы сумма долей точно равнялась amount."""
    total_weight = sum(weights.values())
    parts: dict[str, int] = {}
    remainders = []
    for index, (key, weight) in enumerate(weights.items()):
        quotient, remainder = divmod(amount * weight, total_weight)
        parts[key] = quotient
        remainders.append((remainder, -index, key))  # при равенстве раньше идёт тот, кто выше в списке
    leftover = amount - sum(parts.values())
    for _, _, key in sorted(remainders, reverse=True)[:leftover]:
        parts[key] += 1
    return parts


def _items_base(items: list[tuple[int, list[str]]], friends: list[str]) -> dict[str, int]:
    """Сколько заказал каждый (без обслуживания). Блюдо на нескольких делится между ними поровну."""
    if not items:
        raise SplitError("Добавьте хотя бы одну позицию из чека")

    known = {ME, *friends}
    base = {ME: 0, **{email: 0 for email in friends}}

    for price, eaters in items:
        keys: list[str] = []
        for eater in eaters:
            eater = ME if eater.strip().lower() == ME else _norm(eater)
            if eater not in known:
                raise SplitError(f"В позиции указан участник, которого нет в списке: {eater}")
            if eater not in keys:
                keys.append(eater)
        if not keys:
            raise SplitError("У каждой позиции должен быть хотя бы один человек")
        for key, cents in split_evenly(price, keys).items():
            base[key] += cents
    return base


def _add_service(base: dict[str, int], percent: float) -> dict[str, int]:
    """Добавляет обслуживание (чаевые) в процентах. Делится пропорционально заказу каждого.

    Если все суммы целые (без тиынов), обслуживание тоже округляется до целых.
    """
    unit = 100 if all(value % 100 == 0 for value in base.values()) else 1
    subtotal = sum(base.values())
    service = int(
        (Decimal(subtotal) * Decimal(str(percent)) / 100 / unit).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    totals = dict(base)
    if service:
        parts = distribute_proportionally(service, {key: value // unit for key, value in base.items()})
        for key, part in parts.items():
            totals[key] += part * unit
    return totals


def compute_split(
    mode: str,
    amount: int | None,
    friends: list[tuple[str, int | None]],
    items: list[tuple[int, list[str]]] | None = None,
    tip_percent: float = 0,  # обслуживание, % к чеку (во всех режимах)
    payer_email: str = "",
) -> SplitResult:
    """Главная функция.

    amount  - сумма чека без обслуживания, в копейках (для items не нужна, считается из позиций)
    friends - список (email, сумма в копейках или None); сумма нужна только для custom
    items   - для items: список (цена в копейках, [кто ел: "me" или email])
    """
    emails: list[str] = []
    custom_amounts: dict[str, int] = {}
    for raw_email, friend_amount in friends:
        email = _norm(raw_email)
        if email == _norm(payer_email):
            raise SplitError("Себя добавлять не нужно: ваша доля считается автоматически")
        if email in emails:
            raise SplitError(f"Друг указан дважды: {email}")
        emails.append(email)
        if friend_amount is not None:
            custom_amounts[email] = friend_amount

    if not emails:
        raise SplitError("Добавьте хотя бы одного друга")

    if mode == "items":
        base = _items_base(items or [], emails)
    else:
        if amount is None or amount <= 0:
            raise SplitError("Укажите сумму чека")
        if mode == "equal":
            base = split_evenly(amount, [ME, *emails])
            if any(base[e] <= 0 for e in emails):
                raise SplitError("Сумма слишком мала, чтобы поделить на всех")
        elif mode == "custom":
            missing = [e for e in emails if e not in custom_amounts]
            if missing:
                raise SplitError(f"Укажите сумму для: {', '.join(missing)}")
            owed = sum(custom_amounts.values())
            if owed > amount:
                raise SplitError("Сумма долей друзей больше суммы чека")
            base = {ME: amount - owed, **{e: custom_amounts[e] for e in emails}}
        else:
            raise SplitError("Неизвестный способ деления")

    totals = _add_service(base, tip_percent)
    result = SplitResult(
        total=sum(totals.values()),
        mine=totals[ME],
        friends={e: totals[e] for e in emails if totals[e] > 0},
        service=sum(totals.values()) - sum(base.values()),
    )
    if len(result.friends) == 0:
        raise SplitError("Никто, кроме вас, не должен по этому счёту")
    return result
