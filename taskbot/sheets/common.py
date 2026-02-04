# taskbot/sheets/common.py
# Общие задачи + прогресс теперь в SQL, но зеркалирование в Google через outbox

from __future__ import annotations

from typing import List
from taskbot.config import STATUS_TODO, STATUS_DONE, STATUS_ARCHIVE
from taskbot.sheets.tasks import TaskRow
from taskbot.storage.sql import common_repo


async def common_tasks_for_user(user_name: str, mode: str) -> List[TaskRow]:
    """
    Возвращаем общие задачи для пользователя.
    Важно: без дублей, DONE считается по common_progress.
    """
    rows = await common_repo.common_tasks_list()

    out: List[TaskRow] = []
    for r in rows:
        tid = int(r["task_id"])
        # пользователь закрыл эту общую задачу?
        done_for_user = await common_repo.common_progress_is_done(tid, user_name)

        # вычисляем статус "для пользователя"
        status_for_user = STATUS_DONE if done_for_user else r["status"]

        # скрываем архив всегда
        if status_for_user == STATUS_ARCHIVE:
            continue

        if mode == "my":
            if status_for_user == STATUS_DONE:
                continue
        elif mode == "done":
            if status_for_user != STATUS_DONE:
                continue
        elif mode == "overdue":
            # просрочку считает handlers через is_overdue по due_str, так что здесь только DONE исключим
            if status_for_user == STATUS_DONE:
                continue

        out.append(
            TaskRow(
                task_id=r["task_id"],
                task=r["task"],
                from_name=r["from_name"],
                due_str=r["due_str"],
                status=status_for_user,
                created_at=r["created_at"],
            )
        )
    return out


async def common_progress_set_done(task_id: str, user_name: str) -> None:
    await common_repo.common_progress_set_done(task_id, user_name)
