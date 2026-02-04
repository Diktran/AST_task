# taskbot/sheets/mirror_apply.py
# Применение событий из outbox в Google Sheets
# ВНИМАНИЕ: Google — только зеркало. Если что-то не удалось — это не ломает SQL.

from __future__ import annotations

import json
import gspread

from taskbot.sheets.mirror_client import spreadsheet, to_thread
from taskbot.sheets.mirror_schema import ensure_base_structure
from taskbot.config import USERS_SHEET, COMMON_SHEET, TASK_HEADERS, USERS_HEADERS, COMMON_PROGRESS_SHEET


def _ws(name: str) -> gspread.Worksheet:
    return spreadsheet().worksheet(name)


def _find_row_by_task_id(ws: gspread.Worksheet, task_id: str) -> int | None:
    """
    Ищем ячейку с task_id и возвращаем номер строки.
    """
    try:
        cell = ws.find(str(task_id))
        return cell.row
    except gspread.exceptions.CellNotFound:
        return None


def _update_cell_by_header(ws: gspread.Worksheet, row: int, header: str, value: str) -> None:
    col = TASK_HEADERS.index(header) + 1
    ws.update_cell(row, col, value)


def _append_task_row(ws: gspread.Worksheet, payload: dict) -> None:
    ws.append_row(
        [str(payload["task_id"]), payload["task"], payload["from_name"], payload.get("due", ""), payload["status"], ""],
        value_input_option="RAW",
    )


def _upsert_user_in_users_sheet(name: str, telegram_id: int) -> None:
    ws = _ws(USERS_SHEET)
    # простая логика: ищем строку по name
    values = ws.get_all_values()
    for i, row in enumerate(values[1:], start=2):
        if len(row) >= 1 and row[0] == name:
            ws.update(f"A{i}:B{i}", [[name, str(telegram_id)]])
            return
    ws.append_row([name, str(telegram_id)], value_input_option="RAW")


def _delete_user_from_users_sheet(name: str) -> None:
    ws = _ws(USERS_SHEET)
    values = ws.get_all_values()
    for i, row in enumerate(values[1:], start=2):
        if len(row) >= 1 and row[0] == name:
            ws.delete_rows(i)
            return


async def apply_events(events: list[tuple[int, str, str]]) -> None:
    """
    events: [(outbox_id, event_type, payload_json), ...]
    """
    # Сначала убедимся, что структура есть.
    # В идеале сюда надо передать список пользователей из SQL (мы сделаем это в worker)
    # поэтому здесь ensure_base_structure вызывать не будем — он вызывается в worker.
    ss = spreadsheet()

    for outbox_id, etype, payload_json in events:
        payload = json.loads(payload_json)

        if etype == "USER_UPSERT":
            await to_thread(_upsert_user_in_users_sheet, payload["name"], int(payload["telegram_id"]))

        elif etype == "USER_DELETE":
            await to_thread(_delete_user_from_users_sheet, payload["name"])

        elif etype == "TASK_CREATED":
            ws = await to_thread(ss.worksheet, payload["sheet"])
            await to_thread(_append_task_row, ws, payload)

        elif etype == "TASK_STATUS":
            ws = await to_thread(ss.worksheet, payload["sheet"])
            row = await to_thread(_find_row_by_task_id, ws, payload["task_id"])
            if row:
                await to_thread(_update_cell_by_header, ws, row, "Status", payload["status"])

        elif etype == "TASK_TEXT":
            ws = await to_thread(ss.worksheet, payload["sheet"])
            row = await to_thread(_find_row_by_task_id, ws, payload["task_id"])
            if row:
                await to_thread(_update_cell_by_header, ws, row, "Task", payload["task"])

        elif etype == "TASK_DUE":
            ws = await to_thread(ss.worksheet, payload["sheet"])
            row = await to_thread(_find_row_by_task_id, ws, payload["task_id"])
            if row:
                await to_thread(_update_cell_by_header, ws, row, "Due", payload["due"])

        elif etype == "TASK_DELETE":
            ws = await to_thread(ss.worksheet, payload["sheet"])
            row = await to_thread(_find_row_by_task_id, ws, payload["task_id"])
            if row and row > 1:
                await to_thread(ws.delete_rows, row)

        elif etype == "COMMON_CREATED":
            ws = await to_thread(ss.worksheet, COMMON_SHEET)
            await to_thread(_append_task_row, ws, {"sheet": COMMON_SHEET, **payload})

        elif etype == "COMMON_PROGRESS":
            # progress пишем в отдельный лист как лог (TaskID, User, Status, UpdatedAt)
            ws = await to_thread(ss.worksheet, COMMON_PROGRESS_SHEET)
            await to_thread(ws.append_row, [str(payload["task_id"]), payload["user"], payload["status"], ""], "RAW")

        elif etype == "TASK_ARCHIVE_BATCH":
            # Для простоты: ничего не делаем батчем.
            # ARCHIVE уже прилетит как TASK_STATUS от конкретных задач при изменении.
            # (или можно реализовать отдельный проход по листам — по желанию)
            pass

        else:
            # неизвестное событие — пропустим
            pass
