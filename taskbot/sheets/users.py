# users.py — регистрация пользователей и получение списка

from typing import Dict  # типы
from taskbot.sheets.schema import ensure_worksheet_exists, ensure_headers  # листы и заголовки
from taskbot.config import USERS_SHEET, TASK_HEADERS  # имена листов
from taskbot.sheets.client import gs_to_thread  # async вызов


def users_get_map_sync() -> Dict[str, int]:
    """
    Синхронно читаем Users и возвращаем {Name: TelegramID}.
    """
    ws = ensure_worksheet_exists(USERS_SHEET)
    ensure_headers(ws, ["Name", "TelegramID"])

    values = ws.get_all_values()
    result: Dict[str, int] = {}

    for row in values[1:]:
        if len(row) < 2:
            continue
        name = row[0].strip()
        tid_raw = row[1].strip()
        if not name or not tid_raw:
            continue
        try:
            result[name] = int(tid_raw)
        except ValueError:
            continue

    return result


def users_upsert_sync(name: str, telegram_id: int) -> None:
    """
    Синхронно вставляем/обновляем Users и создаём личный лист name с заголовками задач.
    """
    ws = ensure_worksheet_exists(USERS_SHEET)
    ensure_headers(ws, ["Name", "TelegramID"])

    values = ws.get_all_values()

    # ищем строку по имени
    for idx, row in enumerate(values[1:], start=2):
        if len(row) >= 1 and row[0].strip() == name:
            ws.update(f"A{idx}:B{idx}", [[name, str(telegram_id)]])
            break
    else:
        ws.append_row([name, str(telegram_id)], value_input_option="RAW")

    # создаём/получаем личный лист и ставим заголовки задач
    ws_personal = ensure_worksheet_exists(name)
    ensure_headers(ws_personal, TASK_HEADERS)


async def users_get_map() -> Dict[str, int]:
    """Асинхронная обёртка."""
    return await gs_to_thread(users_get_map_sync)


async def users_upsert(name: str, telegram_id: int) -> None:
    """Асинхронная обёртка."""
    await gs_to_thread(users_upsert_sync, name, telegram_id)
