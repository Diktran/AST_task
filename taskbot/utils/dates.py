# dates.py — работа с датами

from datetime import date, timedelta,time,datetime  # даты/смещения
from dateutil import parser as date_parser  # парсер


def normalize_due_date(raw: str) -> str:
    """
    Принимает дату:
    - 2026-02-10
    - 10.02.2026
    - 2026-02-10 15:30
    - 10.02.2026 15:30

    Если время НЕ указано → ставим 18:00
    Возвращает ISO-строку: YYYY-MM-DD HH:MM
    """

    raw = raw.strip()

    formats_with_time = [
        "%Y-%m-%d %H:%M",
        "%d.%m.%Y %H:%M",
    ]

    formats_without_time = [
        "%Y-%m-%d",
        "%d.%m.%Y",
    ]

    # 1️⃣ Пробуем с временем
    for fmt in formats_with_time:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass

    # 2️⃣ Пробуем без времени → добавляем 18:00
    for fmt in formats_without_time:
        try:
            d = datetime.strptime(raw, fmt).date()
            dt = datetime.combine(d, time(hour=18, minute=0))
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass

    raise ValueError("Не удалось распознать дату")



def is_overdue(due_iso: str) -> bool:
    """
    Просрочено ли: due < сегодня
    """
    return date.fromisoformat(due_iso) < date.today()


def today_iso() -> str:
    d = date.today()
    return datetime.combine(d, time(18, 0)).strftime("%Y-%m-%d %H:%M")


def tomorrow_iso() -> str:
    d = date.today() + timedelta(days=1)
    return datetime.combine(d, time(18, 0)).strftime("%Y-%m-%d %H:%M")


def end_of_week_iso() -> str:
    """
    Конец недели = пятница 18:00
    """
    today = date.today()
    days_until_friday = 4 - today.weekday()  # Monday=0
    if days_until_friday < 0:
        days_until_friday += 7
    d = today + timedelta(days=days_until_friday)
    return datetime.combine(d, time(18, 0)).strftime("%Y-%m-%d %H:%M")

