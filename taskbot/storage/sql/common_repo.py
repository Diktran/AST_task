# taskbot/storage/sql/common_repo.py
# Общие задачи + прогресс по ним в SQL

from __future__ import annotations

from datetime import datetime
from sqlalchemy import select
from taskbot.config import STATUS_TODO, STATUS_DONE, STATUS_ARCHIVE
from taskbot.storage.sql.db import SessionLocal
from taskbot.storage.sql.models import CommonTask, CommonProgress
from taskbot.storage.sql.outbox import outbox_add


def _parse_due_str(due_str: str | None) -> datetime | None:
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


async def common_task_create(task_text: str, from_name: str, due_str: str, status: str) -> int:
    due_at = _parse_due_str(due_str)
    async with SessionLocal() as session:
        t = CommonTask(
            task_text=task_text,
            from_name=from_name,
            due_at=due_at,
            status=status or STATUS_TODO,
            created_at=datetime.utcnow(),
        )
        session.add(t)
        await session.commit()
        await session.refresh(t)
        tid = int(t.id)

    await outbox_add("COMMON_CREATED", {
        "task_id": tid,
        "task": task_text,
        "from_name": from_name,
        "due": _due_to_str(due_at),
        "status": status or STATUS_TODO,
    })
    return tid


async def common_tasks_list() -> list[dict]:
    async with SessionLocal() as session:
        res = await session.execute(select(CommonTask).order_by(CommonTask.id.desc()))
        rows = res.scalars().all()

    out = []
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


async def common_progress_set_done(task_id: str, user_name: str) -> None:
    """
    Отмечаем общую задачу DONE для конкретного пользователя.
    """
    tid = int(task_id)
    async with SessionLocal() as session:
        res = await session.execute(
            select(CommonProgress).where(CommonProgress.task_id == tid, CommonProgress.user_name == user_name)
        )
        p = res.scalar_one_or_none()
        if p:
            p.status = STATUS_DONE
            p.updated_at = datetime.utcnow()
        else:
            session.add(CommonProgress(task_id=tid, user_name=user_name, status=STATUS_DONE, updated_at=datetime.utcnow()))
        await session.commit()

    await outbox_add("COMMON_PROGRESS", {"task_id": tid, "user": user_name, "status": STATUS_DONE})


async def common_progress_is_done(task_id: int, user_name: str) -> bool:
    async with SessionLocal() as session:
        res = await session.execute(
            select(CommonProgress).where(CommonProgress.task_id == task_id, CommonProgress.user_name == user_name)
        )
        p = res.scalar_one_or_none()
        return bool(p and p.status == STATUS_DONE)


async def archive_common_done_before(cutoff: datetime) -> int:
    async with SessionLocal() as session:
        res = await session.execute(
            select(CommonTask).where(CommonTask.status == STATUS_DONE, CommonTask.due_at.is_not(None), CommonTask.due_at < cutoff)
        )
        rows = res.scalars().all()
        if not rows:
            return 0
        for t in rows:
            t.status = STATUS_ARCHIVE
        await session.commit()

    await outbox_add("TASK_ARCHIVE_BATCH", {"cutoff": cutoff.isoformat(), "type": "common"})
    return len(rows)
