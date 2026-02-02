# users.py — регистрация пользователей, поиск и удаление

from typing import Dict, Optional, Tuple  # типы

from taskbot.sheets.schema import ensure_worksheet_exists, ensure_headers  # листы/заголовки
from taskbot.config import USERS_SHEET, TASK_HEADERS  # имена листов/заголовки задач
from taskbot.sheets.client import gs_to_thread  # async обёртка


def users_get_map_sync() -> Dict[str, int]:
    """
    Синхронно читаем Users и возвращаем {Name: TelegramID}.
    """
    ws = ensure_worksheet_exists(USERS_SHEET)  # получаем/создаём лист Users
    ensure_headers(ws, ["Name", "TelegramID"])  # гарантируем заголовки

    values = ws.get_all_values()  # читаем все строки
    result: Dict[str, int] = {}   # итоговый словарь

    for row in values[1:]:  # пропускаем заголовок
        if len(row) < 2:  # если строка неполная
            continue
        name = row[0].strip()  # имя листа
        tid_raw = row[1].strip()  # TelegramID строкой
        if not name or not tid_raw:
            continue
        try:
            result[name] = int(tid_raw)  # записываем
        except ValueError:
            continue

    return result


def users_get_by_telegram_id_sync(telegram_id: int) -> Optional[str]:
    """
    Синхронно ищем пользователя по TelegramID и возвращаем Name (имя вкладки).
    Если не найден — None.
    """
    ws = ensure_worksheet_exists(USERS_SHEET)  # Users лист
    ensure_headers(ws, ["Name", "TelegramID"])  # заголовки

    values = ws.get_all_values()  # все строки

    for row in values[1:]:  # пропускаем заголовок
        if len(row) < 2:
            continue
        name = row[0].strip()
        tid_raw = row[1].strip()
        if not name or not tid_raw:
            continue
        try:
            if int(tid_raw) == telegram_id:
                return name  # нашли
        except ValueError:
            continue

    return None  # не нашли


def users_get_by_name_sync(name: str) -> Optional[int]:
    """
    Синхронно ищем TelegramID по Name (имени вкладки).
    Если не найден — None.
    """
    ws = ensure_worksheet_exists(USERS_SHEET)
    ensure_headers(ws, ["Name", "TelegramID"])

    values = ws.get_all_values()

    for row in values[1:]:
        if len(row) < 2:
            continue
        n = row[0].strip()
        tid_raw = row[1].strip()
        if n == name and tid_raw:
            try:
                return int(tid_raw)
            except ValueError:
                return None

    return None


def users_upsert_sync(name: str, telegram_id: int) -> None:
    """
    Синхронно добавляем/обновляем пользователя.
    ВАЖНО: тут нет логики запретов — запреты делаются на уровне handlers.py.

    Также создаём личный лист name и ставим заголовки задач.
    """
    ws = ensure_worksheet_exists(USERS_SHEET)  # Users лист
    ensure_headers(ws, ["Name", "TelegramID"])  # заголовки Users

    values = ws.get_all_values()  # читаем все строки

    # ищем строку по name
    for idx, row in enumerate(values[1:], start=2):
        if len(row) >= 1 and row[0].strip() == name:
            ws.update(f"A{idx}:B{idx}", [[name, str(telegram_id)]])  # обновляем
            break
    else:
        ws.append_row([name, str(telegram_id)], value_input_option="RAW")  # добавляем

    # создаём/получаем личный лист и ставим заголовки задач
    ws_personal = ensure_worksheet_exists(name)
    ensure_headers(ws_personal, TASK_HEADERS)


def users_delete_by_telegram_id_sync(telegram_id: int) -> Optional[str]:
    """
    Синхронно удаляем регистрацию пользователя по TelegramID.
    Возвращаем Name (имя вкладки), если удалили. Если не нашли — None.

    ВАЖНО: мы удаляем только строку из Users.
    Лист с задачами (вкладка) НЕ удаляется, чтобы не потерять данные.
    """
    ws = ensure_worksheet_exists(USERS_SHEET)  # Users лист
    ensure_headers(ws, ["Name", "TelegramID"])  # заголовки

    values = ws.get_all_values()  # все строки

    for idx, row in enumerate(values[1:], start=2):  # idx = номер строки в Sheets
        if len(row) < 2:
            continue
        name = row[0].strip()
        tid_raw = row[1].strip()
        if not tid_raw:
            continue
        try:
            if int(tid_raw) == telegram_id:
                ws.delete_rows(idx)  # удаляем строку регистрации
                return name  # возвращаем имя вкладки
        except ValueError:
            continue

    return None  # не нашли


# --- Async обёртки (чтобы вызывать из aiogram) ---

async def users_get_map() -> Dict[str, int]:
    return await gs_to_thread(users_get_map_sync)


async def users_get_by_telegram_id(telegram_id: int) -> Optional[str]:
    return await gs_to_thread(users_get_by_telegram_id_sync, telegram_id)


async def users_get_by_name(name: str) -> Optional[int]:
    return await gs_to_thread(users_get_by_name_sync, name)


async def users_upsert(name: str, telegram_id: int) -> None:
    await gs_to_thread(users_upsert_sync, name, telegram_id)


async def users_delete_by_telegram_id(telegram_id: int) -> Optional[str]:
    return await gs_to_thread(users_delete_by_telegram_id_sync, telegram_id)
