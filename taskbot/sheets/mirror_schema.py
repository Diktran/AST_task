# taskbot/sheets/mirror_schema.py
# Создание листов/заголовков в Google (для зеркала)

from __future__ import annotations

import gspread

from taskbot.sheets.mirror_client import spreadsheet, to_thread
from taskbot.config import USERS_SHEET, USERS_HEADERS, TASK_HEADERS, COMMON_SHEET, COMMON_PROGRESS_SHEET, COMMON_PROGRESS_HEADERS


def _ensure_ws(name: str) -> gspread.Worksheet:
    ss = spreadsheet()
    try:
        return ss.worksheet(name)
    except gspread.WorksheetNotFound:
        return ss.add_worksheet(title=name, rows=2000, cols=20)


def _ensure_headers(ws: gspread.Worksheet, headers: list[str]) -> None:
    values = ws.row_values(1)
    if values != headers:
        ws.update("A1", [headers])


async def ensure_base_structure(user_sheet_names: list[str]) -> None:
    """
    Создаём Users, Общие, CommonProgress и листы пользователей (как витрину).
    """
    # Users
    ws_users = await to_thread(_ensure_ws, USERS_SHEET)
    await to_thread(_ensure_headers, ws_users, USERS_HEADERS)

    # Общие
    ws_common = await to_thread(_ensure_ws, COMMON_SHEET)
    await to_thread(_ensure_headers, ws_common, TASK_HEADERS)

    # Прогресс общих
    ws_prog = await to_thread(_ensure_ws, COMMON_PROGRESS_SHEET)
    await to_thread(_ensure_headers, ws_prog, COMMON_PROGRESS_HEADERS)

    # Листы пользователей
    for name in user_sheet_names:
        ws = await to_thread(_ensure_ws, name)
        await to_thread(_ensure_headers, ws, TASK_HEADERS)
