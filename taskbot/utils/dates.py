# dates.py — работа с датами

from datetime import date, timedelta  # даты и смещения
from dateutil import parser as date_parser  # гибкий парсер дат


def normalize_due_date(input_text: str) -> str:
    """
    Приводим ввод срока к формату YYYY-MM-DD.
    Поддерживает:
      - 2026-02-05
      - 05.02.2026
      - 5 Feb 2026
    """
    d = date_parser.parse(input_text, dayfirst=True).date()
    return d.isoformat()


def is_overdue(due_iso: str) -> bool:
    """
    Проверяем, просрочена ли задача.
    Просрочено, если due < сегодня.
    """
    return date.fromisoformat(due_iso) < date.today()


def today_iso() -> str:
    """Сегодня (YYYY-MM-DD)."""
    return date.today().isoformat()


def tomorrow_iso() -> str:
    """Завтра (YYYY-MM-DD)."""
    return (date.today() + timedelta(days=1)).isoformat()


def end_of_week_iso() -> str:
    """
    Конец недели = ПЯТНИЦА.

    ISO weekday:
      Пн = 1
      ...
      Пт = 5
      Сб = 6
      Вс = 7

    Логика:
    - Если сегодня Пн–Пт → ближайшая пятница этой недели
    - Если сегодня Сб или Вс → пятница СЛЕДУЮЩЕЙ недели
    """
    today = date.today()
    weekday = today.isoweekday()  # 1..7

    if weekday <= 5:
        # Сколько дней до ближайшей пятницы
        days_until_friday = 5 - weekday
    else:
        # Сб/Вс → пятница следующей недели
        days_until_friday = (7 - weekday) + 5

    return (today + timedelta(days=days_until_friday)).isoformat()
