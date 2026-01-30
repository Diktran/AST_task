# common.py — общие задачи без дублей
#   - задачи лежат в листе "Общие"
#   - персональный прогресс лежит в "CommonProgress"

from typing import List, Set, Tuple  # типы
from taskbot.config import (
    COMMON_SHEET, COMMON_PROGRESS_SHEET,
    COMMON_PROGRESS_HEADERS,
    STATUS_TODO, STATUS_DONE,
)
from taskbot.sheets.schema import ensure_worksheet_exists, ensure_headers  # листы/заголовки
from taskbot.sheets.client import gs_to_thread  # async
from taskbot.sheets.tasks import TaskRow, tasks_list_sync, now_iso  # задача + чтение задач синхронно
from taskbot.utils.dates import is_overdue  # просрочка


def common_progress_done_set_sync() -> Set[Tuple[str, str]]:
    """
    Синхронно читаем CommonProgress и делаем set {(TaskID, Name)} где DONE.
    """
    ws = ensure_worksheet_exists(COMMON_PROGRESS_SHEET)
    ensure_headers(ws, COMMON_PROGRESS_HEADERS)

    values = ws.get_all_values()
    done_set: Set[Tuple[str, str]] = set()

    for row in values[1:]:
        while len(row) < 4:
            row.append("")
        task_id, name, status, _done_at = row[:4]
        if task_id.strip() and name.strip() and status.strip().upper() == STATUS_DONE:
            done_set.add((task_id.strip(), name.strip()))

    return done_set


def common_progress_set_done_sync(task_id: str, name: str) -> None:
    """
    Синхронно записываем DONE для (task_id, name) в CommonProgress.
    """
    ws = ensure_worksheet_exists(COMMON_PROGRESS_SHEET)
    ensure_headers(ws, COMMON_PROGRESS_HEADERS)

    values = ws.get_all_values()

    # ищем существующую запись
    for idx, row in enumerate(values[1:], start=2):
        while len(row) < 2:
            row.append("")
        if row[0].strip() == task_id and row[1].strip() == name:
            ws.update(f"A{idx}:D{idx}", [[task_id, name, STATUS_DONE, now_iso()]])
            return

    # если не нашли — добавляем
    ws.append_row([task_id, name, STATUS_DONE, now_iso()], value_input_option="RAW")


def common_tasks_for_user_sync(user_name: str, mode: str) -> List[TaskRow]:
    """
    Синхронно возвращаем общие задачи как “персональный вид” для user_name.
    mode: my / done / overdue / all
    """
    # читаем все общие задачи из листа "Общие"
    common_tasks = tasks_list_sync(COMMON_SHEET)

    # читаем прогресс DONE
    done_set = common_progress_done_set_sync()

    result: List[TaskRow] = []
    for t in common_tasks:
        personal_status = STATUS_DONE if (t.task_id, user_name) in done_set else STATUS_TODO

        view = TaskRow(
            task_id=t.task_id,
            task=t.task,
            from_name=t.from_name,
            due_str=t.due_str,
            status=personal_status,
            created_at=t.created_at,
        )

        if mode == "my" and view.status == STATUS_DONE:
            continue
        if mode == "done" and view.status != STATUS_DONE:
            continue
        if mode == "overdue":
            if view.status == STATUS_DONE:
                continue
            if not view.due_str or not is_overdue(view.due_str):
                continue

        result.append(view)

    return result


async def common_tasks_for_user(user_name: str, mode: str) -> List[TaskRow]:
    return await gs_to_thread(common_tasks_for_user_sync, user_name, mode)


async def common_progress_set_done(task_id: str, name: str) -> None:
    await gs_to_thread(common_progress_set_done_sync, task_id, name)
