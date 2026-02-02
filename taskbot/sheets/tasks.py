# tasks.py — работа с задачами в листах (личные + "Общие")
# ВАЖНО:
# - TaskID теперь порядковый номер (1,2,3...) через лист Meta
# - task_append(...) возвращает назначенный task_id
# - есть функции для админ-редактирования/удаления

from __future__ import annotations

from dataclasses import dataclass  # структура задачи
from typing import List, Optional  # типы
from datetime import datetime  # время

import gspread  # исключения/поиск

from taskbot.sheets.schema import ensure_worksheet_exists, ensure_headers  # листы/заголовки
from taskbot.sheets.client import gs_to_thread  # async вызов
from taskbot.config import TASK_HEADERS, STATUS_TODO, STATUS_DONE  # константы


# ---- служебный лист для счётчика ----
META_SHEET = "Meta"                 # имя листа
META_HEADERS = ["Key", "Value"]     # заголовки
TASK_SEQ_KEY = "TASK_SEQ"           # ключ для порядкового номера


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


# ---------------- META helpers (порядковый номер) ----------------

def _meta_ws_sync():
    """Получаем лист Meta и гарантируем заголовки."""
    ws = ensure_worksheet_exists(META_SHEET)
    ensure_headers(ws, META_HEADERS)
    return ws


def _meta_get_value_sync(ws, key: str) -> Optional[str]:
    """Читаем значение по ключу из Meta."""
    values = ws.get_all_values()
    for row in values[1:]:
        if len(row) >= 2 and row[0].strip() == key:
            return row[1].strip()
    return None


def _meta_set_value_sync(ws, key: str, value: str) -> None:
    """Записываем значение по ключу в Meta (update если ключ существует, иначе append)."""
    values = ws.get_all_values()
    for idx, row in enumerate(values[1:], start=2):  # start=2 потому что 1 строка — заголовки
        if len(row) >= 1 and row[0].strip() == key:
            ws.update(f"A{idx}:B{idx}", [[key, value]])
            return
    ws.append_row([key, value], value_input_option="RAW")


def next_task_id_sync() -> str:
    """
    Возвращаем следующий TaskID как строку числа:
    - читаем TASK_SEQ
    - увеличиваем на 1
    - сохраняем обратно
    """
    ws = _meta_ws_sync()
    current = _meta_get_value_sync(ws, TASK_SEQ_KEY)

    try:
        cur_int = int(current) if current else 0
    except ValueError:
        cur_int = 0

    new_val = cur_int + 1
    _meta_set_value_sync(ws, TASK_SEQ_KEY, str(new_val))
    return str(new_val)


# ---------------- Tasks helpers ----------------

def _tasks_ws_sync(sheet_name: str):
    """Получаем лист задач и гарантируем заголовки."""
    ws = ensure_worksheet_exists(sheet_name)
    ensure_headers(ws, TASK_HEADERS)
    return ws


def _find_row_by_task_id_sync(ws, task_id: str) -> Optional[int]:
    """
    Ищем строку по task_id.
    Возвращаем индекс строки в Google Sheets (>=2), либо None.
    """
    try:
        cell = ws.find(task_id)
        return cell.row
    except gspread.exceptions.CellNotFound:
        return None


# ---------------- CRUD (sync) ----------------

def task_append_sync(sheet_name: str, row: TaskRow) -> str:
    """
    Синхронно добавляем задачу.
    Если task_id пустой -> назначаем порядковый.
    Возвращаем фактический task_id.
    """
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
    """Синхронно читаем все задачи из листа."""
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
    """Синхронно ставим статус TODO/DONE по task_id."""
    ws = _tasks_ws_sync(sheet_name)
    row_idx = _find_row_by_task_id_sync(ws, task_id)
    if row_idx is None:
        return False

    status_col_idx = TASK_HEADERS.index("Status") + 1
    ws.update_cell(row_idx, status_col_idx, status)
    return True


def task_set_done_sync(sheet_name: str, task_id: str) -> bool:
    """DONE."""
    return task_set_status_sync(sheet_name, task_id, STATUS_DONE)


def task_set_todo_sync(sheet_name: str, task_id: str) -> bool:
    """TODO."""
    return task_set_status_sync(sheet_name, task_id, STATUS_TODO)


def task_update_text_sync(sheet_name: str, task_id: str, new_text: str) -> bool:
    """Обновляем текст задачи (колонка Task)."""
    ws = _tasks_ws_sync(sheet_name)
    row_idx = _find_row_by_task_id_sync(ws, task_id)
    if row_idx is None:
        return False

    task_col_idx = TASK_HEADERS.index("Task") + 1
    ws.update_cell(row_idx, task_col_idx, new_text)
    return True


def task_update_due_sync(sheet_name: str, task_id: str, new_due_iso: str) -> bool:
    """Обновляем срок (колонка Due)."""
    ws = _tasks_ws_sync(sheet_name)
    row_idx = _find_row_by_task_id_sync(ws, task_id)
    if row_idx is None:
        return False

    due_col_idx = TASK_HEADERS.index("Due") + 1
    ws.update_cell(row_idx, due_col_idx, new_due_iso)
    return True


def task_delete_sync(sheet_name: str, task_id: str) -> bool:
    """Удаляем строку задачи по task_id."""
    ws = _tasks_ws_sync(sheet_name)
    row_idx = _find_row_by_task_id_sync(ws, task_id)
    if row_idx is None:
        return False

    ws.delete_rows(row_idx)
    return True


# ---------------- async wrappers ----------------

async def task_append(sheet_name: str, row: TaskRow) -> str:
    """Async append, возвращает task_id."""
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
