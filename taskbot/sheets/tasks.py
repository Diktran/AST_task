# tasks.py — работа с задачами в листах (личные + "Общие")

from dataclasses import dataclass  # структура задачи
from typing import List  # типы
import uuid  # генерация ID
from datetime import datetime  # время

import gspread  # исключения/поиск

from taskbot.sheets.schema import ensure_worksheet_exists, ensure_headers  # листы/заголовки
from taskbot.sheets.client import gs_to_thread  # async вызов
from taskbot.config import TASK_HEADERS, STATUS_TODO, STATUS_DONE  # константы


@dataclass
class TaskRow:
    """Одна строка задачи."""
    task_id: str
    task: str
    from_name: str
    due_str: str
    status: str
    created_at: str


def now_iso() -> str:
    """UTC время в ISO."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def task_append_sync(sheet_name: str, row: TaskRow) -> None:
    """Синхронно добавляем задачу в лист."""
    ws = ensure_worksheet_exists(sheet_name)
    ensure_headers(ws, TASK_HEADERS)
    ws.append_row(
        [row.task_id, row.task, row.from_name, row.due_str, row.status, row.created_at],
        value_input_option="RAW",
    )


def tasks_list_sync(sheet_name: str) -> List[TaskRow]:
    """Синхронно читаем все задачи из листа."""
    ws = ensure_worksheet_exists(sheet_name)
    ensure_headers(ws, TASK_HEADERS)

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


def task_set_done_sync(sheet_name: str, task_id: str) -> bool:
    """Синхронно ставим DONE по task_id (для ЛИЧНЫХ задач)."""
    ws = ensure_worksheet_exists(sheet_name)
    ensure_headers(ws, TASK_HEADERS)

    try:
        cell = ws.find(task_id)
    except gspread.exceptions.CellNotFound:
        return False

    row_idx = cell.row
    status_col_idx = TASK_HEADERS.index("Status") + 1
    ws.update_cell(row_idx, status_col_idx, STATUS_DONE)
    return True


async def task_append(sheet_name: str, row: TaskRow) -> None:
    await gs_to_thread(task_append_sync, sheet_name, row)


async def tasks_list(sheet_name: str) -> List[TaskRow]:
    return await gs_to_thread(tasks_list_sync, sheet_name)


async def task_set_done(sheet_name: str, task_id: str) -> bool:
    return await gs_to_thread(task_set_done_sync, sheet_name, task_id)
