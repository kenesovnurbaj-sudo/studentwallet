"""Текущая дата в часовом поясе пользователей.

Сервер на хостинге обычно работает в UTC, а студенты в Казахстане (UTC+5).
Если брать date.today() сервера, то с 00:00 до 05:00 по Алматы трата «за сегодня»
считалась бы тратой из будущего. Смещение можно поменять через APP_UTC_OFFSET.
"""
import os
from datetime import date, datetime, timedelta, timezone

APP_TZ = timezone(timedelta(hours=float(os.getenv("APP_UTC_OFFSET", "5"))))


def today() -> date:
    return datetime.now(APP_TZ).date()


def current_month() -> str:
    return today().strftime("%Y-%m")
