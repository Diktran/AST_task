# tasks.py — работа с задачами в листах (личные + "Общие")
# - TaskID порядковый (через Meta)
# - CRUD: update text/due, set status, delete
# - monthly archive: DONE задачам, у которых due < cutoff, ставим ARCHIVE

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

import gspread

from taskbot.sheets.schema import ensure_worksheet_exists, ensure_headers
from taskbot.sheets.client import gs_to_thread
from taskbot.config import TASK_HEADERS, STATUS_TODO, STATUS_DONE, STATUS_ARCHIVE


# ---- Meta sheet for sequence ----
META_SHEET = "Meta"
META_HEADERS = ["Key", "Value"]
TASK_SEQ_KEY = "TASK_SEQ"


@dataclass
class TaskRow:
    task_id: str
    task: str
    from_name: str
    due_str: str
    status: str
    created_at: str


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _meta_ws_sync():
    ws = ensure_worksheet_exists(META_SHEET)
    ensure_headers(ws, META_HEADERS)
    return ws


def _meta_get_value_sync(ws, key: str) -> Optional[str]:
    values = ws.get_all_values()
    for row in values[1:]:
        if len(row) >= 2 and row[0].strip() == key:
            return row[1].strip()
    return None


def _meta_set_value_sync(ws, key: str, value: str) -> None:
    values = ws.get_all_values()
    for idx, row in enumerate(values[1:], start=2):
        if len(row) >= 1 and row[0].strip() == key:
            ws.update(f"A{idx}:B{idx}", [[key, value]])
            return
    ws.append_row([key, value], value_input_option="RAW")


def next_task_id_sync() -> str:
    ws = _meta_ws_sync()
    current = _meta_get_value_sync(ws, TASK_SEQ_KEY)
    try:
        cur_int = int(current) if current else 0
    except ValueError:
        cur_int = 0
    new_val = cur_int + 1
    _meta_set_value_sync(ws, TASK_SEQ_KEY, str(new_val))
    return str(new_val)


def _tasks_ws_sync(sheet_name: str):
    ws = ensure_worksheet_exists(sheet_name)
    ensure_headers(ws, TASK_HEADERS)
    return ws


def _find_row_by_task_id_sync(ws, task_id: str) -> Optional[int]:
    try:
        cell = ws.find(task_id)
        return cell.row
    except gspread.exceptions.CellNotFound:
        return None


# ---------------- CRUD sync ----------------

def task_append_sync(sheet_name: str, row: TaskRow) -> str:
    ws = _tasks_ws_sync(sheet_name)

    task_id = (row.task_id or "").strip()
    if not task_id:
        task_id = next_task_id_sync()

    ws.append_row(
        [task_id, row.task, row.from_name, row.due_str, row.status, row.created_at],
        value_input_option="RAW",
    )
    return task_id


def tasks_list_sync(sheet_name: str) -> List[TaskRow]:
    ws = _tasks_ws_sync(sheet_name)

    values = ws.get_all_values()
    if len(values) <= 1:
        return []

    result: List[TaskRow] = []
    for row in values[1:]:
        while len(row) < len(TASK_HEADERS):
            row.append("")
        task_id, task, from_name, due_str, status, created_at = row[:6]
        if not task_id.strip():
            continue
        result.append(
            TaskRow(
                task_id=task_id.strip(),
                task=task.strip(),
                from_name=from_name.strip(),
                due_str=due_str.strip(),
                status=(status.strip() or STATUS_TODO),
                created_at=created_at.strip(),
            )
        )
    return result


def task_set_status_sync(sheet_name: str, task_id: str, status: str) -> bool:
    ws = _tasks_ws_sync(sheet_name)
    row_idx = _find_row_by_task_id_sync(ws, task_id)
    if row_idx is None:
        return False
    status_col_idx = TASK_HEADERS.index("Status") + 1
    ws.update_cell(row_idx, status_col_idx, status)
    return True


def task_set_done_sync(sheet_name: str, task_id: str) -> bool:
    return task_set_status_sync(sheet_name, task_id, STATUS_DONE)


def task_set_todo_sync(sheet_name: str, task_id: str) -> bool:
    return task_set_status_sync(sheet_name, task_id, STATUS_TODO)


def task_update_text_sync(sheet_name: str, task_id: str, new_text: str) -> bool:
    ws = _tasks_ws_sync(sheet_name)
    row_idx = _find_row_by_task_id_sync(ws, task_id)
    if row_idx is None:
        return False
    task_col_idx = TASK_HEADERS.index("Task") + 1
    ws.update_cell(row_idx, task_col_idx, new_text)
    return True


def task_update_due_sync(sheet_name: str, task_id: str, new_due_iso: str) -> bool:
    ws = _tasks_ws_sync(sheet_name)
    row_idx = _find_row_by_task_id_sync(ws, task_id)
    if row_idx is None:
        return False
    due_col_idx = TASK_HEADERS.index("Due") + 1
    ws.update_cell(row_idx, due_col_idx, new_due_iso)
    return True


def task_delete_sync(sheet_name: str, task_id: str) -> bool:
    ws = _tasks_ws_sync(sheet_name)
    row_idx = _find_row_by_task_id_sync(ws, task_id)
    if row_idx is None:
        return False
    ws.delete_rows(row_idx)
    return True


# ---------------- ARCHIVE sync ----------------

def tasks_archive_done_before_sync(sheet_name: str, cutoff_iso: str) -> int:
    """
    Помечаем ARCHIVE все задачи со статусом DONE, у которых due < cutoff_iso.
    cutoff_iso = 'YYYY-MM-01' (первое число текущего месяца)
    """
    ws = _tasks_ws_sync(sheet_name)

    values = ws.get_all_values()
    if len(values) <= 1:
        return 0

    status_col_idx = TASK_HEADERS.index("Status") + 1
    due_col_idx = TASK_HEADERS.index("Due") + 1

    archived = 0

    for row_idx in range(2, len(values) + 1):
        row = values[row_idx - 1]
        while len(row) < len(TASK_HEADERS):
            row.append("")

        due_iso = (row[due_col_idx - 1] or "").strip()
        status = (row[status_col_idx - 1] or "").strip()

        if status == STATUS_DONE and due_iso and due_iso < cutoff_iso:
            ws.update_cell(row_idx, status_col_idx, STATUS_ARCHIVE)
            archived += 1

    return archived


# ---------------- async wrappers ----------------

async def task_append(sheet_name: str, row: TaskRow) -> str:
    return await gs_to_thread(task_append_sync, sheet_name, row)


async def tasks_list(sheet_name: str) -> List[TaskRow]:
    return await gs_to_thread(tasks_list_sync, sheet_name)


async def task_set_status(sheet_name: str, task_id: str, status: str) -> bool:
    return await gs_to_thread(task_set_status_sync, sheet_name, task_id, status)


async def task_set_done(sheet_name: str, task_id: str) -> bool:
    return await gs_to_thread(task_set_done_sync, sheet_name, task_id)


async def task_set_todo(sheet_name: str, task_id: str) -> bool:
    return await gs_to_thread(task_set_todo_sync, sheet_name, task_id)


async def task_update_text(sheet_name: str, task_id: str, new_text: str) -> bool:
    return await gs_to_thread(task_update_text_sync, sheet_name, task_id, new_text)


async def task_update_due(sheet_name: str, task_id: str, new_due_iso: str) -> bool:
    return await gs_to_thread(task_update_due_sync, sheet_name, task_id, new_due_iso)


async def task_delete(sheet_name: str, task_id: str) -> bool:
    return await gs_to_thread(task_delete_sync, sheet_name, task_id)


async def tasks_archive_done_before(sheet_name: str, cutoff_iso: str) -> int:
    return await gs_to_thread(tasks_archive_done_before_sync, sheet_name, cutoff_iso)
