# archiver.py — ежемесячная архивация DONE задач

from datetime import date
from taskbot.sheets.users import users_get_map
from taskbot.sheets.tasks import tasks_archive_done_before
from taskbot.config import COMMON_SHEET


def first_day_of_current_month_iso() -> str:
    today = date.today()
    return date(today.year, today.month, 1).isoformat()


async def run_monthly_archive_once() -> int:
    """
    Архивируем DONE задачи у всех пользователей и в COMMON_SHEET,
    у которых due < 1 число текущего месяца.
    Возвращаем сколько всего пометили ARCHIVE.
    """
    cutoff = first_day_of_current_month_iso()
    users_map = await users_get_map()

    total = 0
    for sheet in list(users_map.keys()) + [COMMON_SHEET]:
        total += await tasks_archive_done_before(sheet, cutoff)

    return total
