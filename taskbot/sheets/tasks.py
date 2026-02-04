# taskbot/sheets/tasks.py
# Теперь: читаем/пишем в SQL, а в Google пишем через outbox (воркер)

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from taskbot.config import STATUS_TODO, STATUS_DONE
from taskbot.storage.sql import tasks_repo


@dataclass
class TaskRow:
    task_id: str
    task: str
    from_name: str
    due_str: str
    status: str
    created_at: str


def now_iso() -> str:
    # handlers это использует; точное значение не критично
    # (created_at в SQL будет нормальный datetime)
    from datetime import datetime
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


async def task_append(sheet_name: str, row: TaskRow) -> str:
    """
    Создаём задачу в SQL.
    Возвращаем task_id (порядковый номер).
    """
    task_id = await tasks_repo.task_create(
        assignee_name=sheet_name,
        task_text=row.task,
        from_name=row.from_name,
        due_str=row.due_str,
        status=row.status or STATUS_TODO,
        created_at=row.created_at,
    )
    return str(task_id)


async def tasks_list(sheet_name: str) -> List[TaskRow]:
    rows = await tasks_repo.tasks_list(sheet_name)
    return [TaskRow(**r) for r in rows]


async def task_set_done(sheet_name: str, task_id: str) -> bool:
    return await tasks_repo.task_set_status(sheet_name, task_id, STATUS_DONE)


async def task_set_todo(sheet_name: str, task_id: str) -> bool:
    return await tasks_repo.task_set_status(sheet_name, task_id, STATUS_TODO)


async def task_set_status(sheet_name: str, task_id: str, status: str) -> bool:
    return await tasks_repo.task_set_status(sheet_name, task_id, status)


async def task_update_text(sheet_name: str, task_id: str, new_text: str) -> bool:
    return await tasks_repo.task_update_text(sheet_name, task_id, new_text)


async def task_update_due(sheet_name: str, task_id: str, due_str: str) -> bool:
    return await tasks_repo.task_update_due(sheet_name, task_id, due_str)


async def task_delete(sheet_name: str, task_id: str) -> bool:
    return await tasks_repo.task_delete(sheet_name, task_id)
