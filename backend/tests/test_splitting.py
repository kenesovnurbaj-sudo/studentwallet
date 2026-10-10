"""Проверка арифметики деления счёта (без базы и без сервера)."""
import pytest

from app.splitting import (
    ME,
    SplitError,
    compute_split,
    distribute_proportionally,
    from_cents,
    split_evenly,
    to_cents,
)


def c(value) -> int:
    return to_cents(value)


def total_of(result) -> int:
    return result.mine + sum(result.friends.values())


def test_to_cents_and_back():
    assert to_cents(10) == 1000
    assert to_cents(12.34) == 1234
    assert to_cents(0.1 + 0.2) == 30  # плавающая точка не ломает деньги
    assert from_cents(1234) == 12.34


def test_split_evenly_whole_units_remainder_goes_to_payer():
    parts = split_evenly(c(10000), [ME, "a@x.kz", "b@x.kz"])
    assert parts == {ME: c(3334), "a@x.kz": c(3333), "b@x.kz": c(3333)}


def test_split_evenly_with_cents():
    parts = split_evenly(c(10.01), [ME, "a@x.kz"])
    assert sum(parts.values()) == c(10.01)
    assert parts[ME] == c(5.01)


def test_equal_mode():
    r = compute_split("equal", c(10000), [("a@x.kz", None), ("b@x.kz", None)])
    assert r.total == c(10000)
    assert r.mine == c(3334)
    assert r.friends == {"a@x.kz": c(3333), "b@x.kz": c(3333)}
    assert total_of(r) == r.total


def test_equal_mode_too_small_amount():
    with pytest.raises(SplitError):
        compute_split("equal", c(1), [("a@x.kz", None), ("b@x.kz", None)])


def test_custom_mode_rest_stays_with_payer():
    r = compute_split("custom", c(10000), [("a@x.kz", c(2500)), ("b@x.kz", c(6000))])
    assert r.friends == {"a@x.kz": c(2500), "b@x.kz": c(6000)}
    assert r.mine == c(1500)
    assert total_of(r) == c(10000)


def test_custom_mode_friends_more_than_check():
    with pytest.raises(SplitError):
        compute_split("custom", c(1000), [("a@x.kz", c(800)), ("b@x.kz", c(300))])


def test_custom_mode_requires_amount_for_each_friend():
    with pytest.raises(SplitError):
        compute_split("custom", c(1000), [("a@x.kz", c(500)), ("b@x.kz", None)])


def test_items_mode_example_from_cafe():
    items = [
        (c(2500), ["a@x.kz"]),  # бизнес-ланч Алии
        (c(6000), ["b@x.kz"]),  # стейк Ерлана
        (c(3000), ["me", "a@x.kz", "b@x.kz"]),  # пицца на всех
        (c(1000), ["me"]),  # кофе
    ]
    r = compute_split("items", None, [("a@x.kz", None), ("b@x.kz", None)], items=items)
    assert r.total == c(12500)
    assert r.friends == {"a@x.kz": c(3500), "b@x.kz": c(7000)}
    assert r.mine == c(2000)
    assert total_of(r) == r.total


def test_items_tip_is_proportional_and_sums_exactly():
    items = [
        (c(1000), ["me"]),
        (c(3000), ["a@x.kz"]),
    ]
    r = compute_split("items", None, [("a@x.kz", None)], items=items, tip_percent=10)
    # чаевые 400: вам 100, другу 300 (пропорционально 1:3)
    assert r.total == c(4400)
    assert r.mine == c(1100)
    assert r.friends == {"a@x.kz": c(3300)}


def test_items_tip_rounding_never_loses_money():
    items = [
        (c(333), ["me"]),
        (c(333), ["a@x.kz"]),
        (c(334), ["b@x.kz"]),
    ]
    r = compute_split(
        "items", None, [("a@x.kz", None), ("b@x.kz", None)], items=items, tip_percent=7
    )
    assert total_of(r) == r.total


def test_items_unknown_eater_rejected():
    with pytest.raises(SplitError):
        compute_split("items", None, [("a@x.kz", None)], items=[(c(100), ["ghost@x.kz"])])


def test_items_needs_someone_besides_payer():
    with pytest.raises(SplitError):
        compute_split("items", None, [("a@x.kz", None)], items=[(c(100), ["me"])])


def test_items_friend_without_items_has_no_debt():
    items = [(c(500), ["me"]), (c(700), ["a@x.kz"])]
    r = compute_split("items", None, [("a@x.kz", None), ("b@x.kz", None)], items=items)
    assert "b@x.kz" not in r.friends


def test_cannot_add_yourself_or_duplicate():
    with pytest.raises(SplitError):
        compute_split("equal", c(100), [("Me@X.kz", None)], payer_email="me@x.kz")
    with pytest.raises(SplitError):
        compute_split("equal", c(100), [("a@x.kz", None), ("A@x.kz", None)])


def test_no_friends_rejected():
    with pytest.raises(SplitError):
        compute_split("equal", c(100), [])


def test_distribute_proportionally_is_exact():
    for amount in (1, 7, 99, 1001):
        parts = distribute_proportionally(amount, {ME: 3, "a": 5, "b": 11})
        assert sum(parts.values()) == amount


def test_service_percent_in_equal_mode():
    r = compute_split("equal", c(10000), [("a@x.kz", None), ("b@x.kz", None)], tip_percent=10)
    # обслуживание 1 000 делится пропорционально: 3 334 / 3 333 / 3 333
    assert r.total == c(11000)
    assert r.mine == c(3668)
    assert r.friends == {"a@x.kz": c(3666), "b@x.kz": c(3666)}
    assert total_of(r) == r.total


def test_service_percent_in_custom_mode():
    r = compute_split("custom", c(10000), [("a@x.kz", c(2500)), ("b@x.kz", c(6000))], tip_percent=10)
    assert r.total == c(11000)
    assert r.mine == c(1650)
    assert r.friends == {"a@x.kz": c(2750), "b@x.kz": c(6600)}
    assert total_of(r) == r.total


def test_zero_service_percent_changes_nothing():
    r = compute_split("equal", c(9000), [("a@x.kz", None), ("b@x.kz", None)], tip_percent=0)
    assert r.total == c(9000)


# ---------- обслуживание (процент к чеку) ----------

def test_service_in_equal_mode():
    r = compute_split("equal", c(9000), [("a@x.kz", None), ("b@x.kz", None)], tip_percent=10)
    assert r.service == c(900)
    assert r.total == c(9900)
    assert r.mine == c(3300)
    assert r.friends == {"a@x.kz": c(3300), "b@x.kz": c(3300)}


def test_service_in_custom_mode_is_proportional():
    # друзья заказали на 2000 и 6000, ваш остаток 2000; обслуживание 10% = 1000
    r = compute_split("custom", c(10000), [("a@x.kz", c(2000)), ("b@x.kz", c(6000))], tip_percent=10)
    assert r.total == c(11000)
    assert r.friends == {"a@x.kz": c(2200), "b@x.kz": c(6600)}
    assert r.mine == c(2200)
    assert total_of(r) == r.total


def test_service_in_items_mode_reports_amount():
    items = [(c(1000), ["me"]), (c(3000), ["a@x.kz"])]
    r = compute_split("items", None, [("a@x.kz", None)], items=items, tip_percent=10)
    assert r.service == c(400)


def test_zero_service_changes_nothing():
    r = compute_split("equal", c(9000), [("a@x.kz", None), ("b@x.kz", None)], tip_percent=0)
    assert r.service == 0
    assert r.total == c(9000)


def test_service_never_loses_money_with_odd_numbers():
    r = compute_split("equal", c(1000), [("a@x.kz", None), ("b@x.kz", None)], tip_percent=7.5)
    assert total_of(r) == r.total
