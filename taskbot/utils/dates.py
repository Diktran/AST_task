# dates.py — работа с датами

from datetime import date  # сравнение дат
from dateutil import parser as date_parser  # гибкий парсер дат


def normalize_due_date(input_text: str) -> str:
    """
    Приводим ввод срока к формату YYYY-MM-DD.
    Поддерживает:
      - 2026-02-05
      - 05.02.2026
      - 5 Feb 2026
    """
    # dayfirst=True => "05.02.2026" = 5 февраля
    d = date_parser.parse(input_text, dayfirst=True).date()
    return d.isoformat()  # YYYY-MM-DD


def is_overdue(due_iso: str) -> bool:
    """
    Просрочено ли: due < сегодня.
    due_iso — строка YYYY-MM-DD.
    """
    return date.fromisoformat(due_iso) < date.today()
