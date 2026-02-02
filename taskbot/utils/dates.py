# dates.py — работа с датами

from datetime import date, timedelta  # даты/смещения
from dateutil import parser as date_parser  # парсер


def normalize_due_date(input_text: str) -> str:
    """
    Парсим ввод и возвращаем YYYY-MM-DD
    """
    d = date_parser.parse(input_text, dayfirst=True).date()
    return d.isoformat()


def is_overdue(due_iso: str) -> bool:
    """
    Просрочено ли: due < сегодня
    """
    return date.fromisoformat(due_iso) < date.today()


def today_iso() -> str:
    """Сегодня YYYY-MM-DD"""
    return date.today().isoformat()


def tomorrow_iso() -> str:
    """Завтра YYYY-MM-DD"""
    return (date.today() + timedelta(days=1)).isoformat()


def end_of_week_iso() -> str:
    """
    Конец недели = ПЯТНИЦА.
    Если сегодня Сб/Вс -> пятница следующей недели.
    """
    today = date.today()
    weekday = today.isoweekday()  # Пн=1 ... Вс=7

    if weekday <= 5:
        days_until_friday = 5 - weekday
    else:
        days_until_friday = (7 - weekday) + 5

    return (today + timedelta(days=days_until_friday)).isoformat()
