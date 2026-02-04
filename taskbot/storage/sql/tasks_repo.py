# taskbot/storage/sql/tasks_repo.py
# Личные задачи в SQL

from __future__ import annotations

import json
from datetime import datetime
from sqlalchemy import select, update, delete
from taskbot.config import STATUS_TODO, STATUS_DONE, STATUS_ARCHIVE
from taskbot.storage.sql.db import SessionLocal
from taskbot.storage.sql.models import Task
from taskbot.storage.sql.outbox import outbox_add


def _parse_due_str(due_str: str | None) -> datetime | None:
    """
    due_str приходит из handlers как "YYYY-MM-DD HH:MM" (или пусто).
    """
    if not due_str:
        return None
    due_str = due_str.strip()
    try:
        if " " in due_str:
            return datetime.strptime(due_str, "%Y-%m-%d %H:%M")
        return datetime.strptime(due_str, "%Y-%m-%d")
    except Exception:
        return None


def _due_to_str(due_at: datetime | None) -> str:
    if not due_at:
        return ""
    return due_at.strftime("%Y-%m-%d %H:%M")


async def task_create(assignee_name: str, task_text: str, from_name: str, due_str: str, status: str, created_at: str) -> int:
    """
    Создаём задачу. Возвращаем порядковый id (task_id).
    created_at игнорируем как строку — записываем норм datetime.
    """
    due_at = _parse_due_str(due_str)

    async with SessionLocal() as session:
        t = Task(
            assignee_name=assignee_name,
            task_text=task_text,
            from_name=from_name,
            due_at=due_at,
            status=status or STATUS_TODO,
            created_at=datetime.utcnow(),
        )
        session.add(t)
        await session.commit()
        await session.refresh(t)
        task_id = int(t.id)

    await outbox_add("TASK_CREATED", {
        "sheet": assignee_name,
        "task_id": task_id,
        "task": task_text,
        "from_name": from_name,
        "due": _due_to_str(due_at),
        "status": status or STATUS_TODO,
    })
    return task_id


async def tasks_list(assignee_name: str) -> list[dict]:
    """
    Возвращаем список задач как dict (потом мапим на TaskRow в tasks.py)
    """
    async with SessionLocal() as session:
        res = await session.execute(
            select(Task).where(Task.assignee_name == assignee_name).order_by(Task.id.desc())
        )
        rows = res.scalars().all()

    out: list[dict] = []
    for t in rows:
        out.append({
            "task_id": str(t.id),
            "task": t.task_text,
            "from_name": t.from_name,
            "due_str": _due_to_str(t.due_at),
            "status": t.status,
            "created_at": t.created_at.isoformat() + "Z",
        })
    return out


async def task_set_status(assignee_name: str, task_id: str, status: str) -> bool:
    """
    Меняем статус по id.
    """
    try:
        tid = int(task_id)
    except ValueError:
        return False

    async with SessionLocal() as session:
        res = await session.execute(select(Task).where(Task.assignee_name == assignee_name, Task.id == tid))
        t = res.scalar_one_or_none()
        if not t:
            return False
        t.status = status
        await session.commit()

    await outbox_add("TASK_STATUS", {"sheet": assignee_name, "task_id": tid, "status": status})
    return True


async def task_update_text(assignee_name: str, task_id: str, new_text: str) -> bool:
    try:
        tid = int(task_id)
    except ValueError:
        return False

    async with SessionLocal() as session:
        res = await session.execute(select(Task).where(Task.assignee_name == assignee_name, Task.id == tid))
        t = res.scalar_one_or_none()
        if not t:
            return False
        t.task_text = new_text
        await session.commit()

    await outbox_add("TASK_TEXT", {"sheet": assignee_name, "task_id": tid, "task": new_text})
    return True


async def task_update_due(assignee_name: str, task_id: str, due_str: str) -> bool:
    try:
        tid = int(task_id)
    except ValueError:
        return False

    due_at = _parse_due_str(due_str)

    async with SessionLocal() as session:
        res = await session.execute(select(Task).where(Task.assignee_name == assignee_name, Task.id == tid))
        t = res.scalar_one_or_none()
        if not t:
            return False
        t.due_at = due_at
        await session.commit()

    await outbox_add("TASK_DUE", {"sheet": assignee_name, "task_id": tid, "due": _due_to_str(due_at)})
    return True


async def task_delete(assignee_name: str, task_id: str) -> bool:
    try:
        tid = int(task_id)
    except ValueError:
        return False

    async with SessionLocal() as session:
        res = await session.execute(select(Task).where(Task.assignee_name == assignee_name, Task.id == tid))
        t = res.scalar_one_or_none()
        if not t:
            return False
        await session.execute(delete(Task).where(Task.assignee_name == assignee_name, Task.id == tid))
        await session.commit()

    await outbox_add("TASK_DELETE", {"sheet": assignee_name, "task_id": tid})
    return True


async def archive_done_before(cutoff: datetime) -> int:
    """
    В начале месяца: DONE с due_at < cutoff -> ARCHIVE.
    """
    async with SessionLocal() as session:
        res = await session.execute(select(Task).where(Task.status == STATUS_DONE, Task.due_at.is_not(None), Task.due_at < cutoff))
        tasks = res.scalars().all()
        if not tasks:
            return 0

        for t in tasks:
            t.status = STATUS_ARCHIVE
        await session.commit()

    # в outbox кинем одно событие-обновление пачкой (проще воркеру)
    await outbox_add("TASK_ARCHIVE_BATCH", {
        "cutoff": cutoff.isoformat(),
        "type": "personal",
    })
    return len(tasks)
