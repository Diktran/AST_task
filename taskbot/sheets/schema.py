# schema.py — создание структуры таблицы при старте

from taskbot.sheets.client import spreadsheet, gs_to_thread  # доступ к таблице и to_thread
from taskbot.config import (
    USERS_SHEET, COMMON_SHEET, COMMON_PROGRESS_SHEET,
    TASK_HEADERS, COMMON_PROGRESS_HEADERS
)
import gspread  # для исключений


def ensure_worksheet_exists(name: str):
    """
    Возвращаем лист по имени, если нет — создаём.
    """
    ss = spreadsheet()
    try:
        return ss.worksheet(name)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=name, rows=2000, cols=20)


def ensure_headers(ws, headers):
    """
    Устанавливаем заголовки в первую строку, если они отличаются.
    """
    first_row = ws.row_values(1)
    if first_row != headers:
        ws.update("A1", [headers])


def ensure_base_structure_sync() -> None:
    """
    Синхронно создаём базовую структуру:
      - Users
      - Общие
      - CommonProgress
    """
    # Users
    ws_users = ensure_worksheet_exists(USERS_SHEET)
    ensure_headers(ws_users, ["Name", "TelegramID"])

    # Общие
    ws_common = ensure_worksheet_exists(COMMON_SHEET)
    ensure_headers(ws_common, TASK_HEADERS)

    # CommonProgress
    ws_prog = ensure_worksheet_exists(COMMON_PROGRESS_SHEET)
    ensure_headers(ws_prog, COMMON_PROGRESS_HEADERS)


async def ensure_base_structure() -> None:
    """
    Асинхронный вызов создания структуры (через to_thread).
    """
    await gs_to_thread(ensure_base_structure_sync)
