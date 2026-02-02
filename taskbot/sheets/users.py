# users.py — регистрация в Users, список регистраций, удаление

from typing import Dict, Optional, List, Tuple

from taskbot.sheets.schema import ensure_worksheet_exists, ensure_headers
from taskbot.config import USERS_SHEET, TASK_HEADERS
from taskbot.sheets.client import gs_to_thread


def users_get_map_sync() -> Dict[str, int]:
    ws = ensure_worksheet_exists(USERS_SHEET)
    ensure_headers(ws, ["Name", "TelegramID"])

    values = ws.get_all_values()
    out: Dict[str, int] = {}

    for row in values[1:]:
        if len(row) < 2:
            continue
        name = row[0].strip()
        tid_raw = row[1].strip()
        if not name or not tid_raw:
            continue
        try:
            out[name] = int(tid_raw)
        except ValueError:
            continue

    return out


def users_list_sync() -> List[Tuple[str, int]]:
    ws = ensure_worksheet_exists(USERS_SHEET)
    ensure_headers(ws, ["Name", "TelegramID"])

    values = ws.get_all_values()
    out: List[Tuple[str, int]] = []

    for row in values[1:]:
        if len(row) < 2:
            continue
        name = row[0].strip()
        tid_raw = row[1].strip()
        if not name or not tid_raw:
            continue
        try:
            out.append((name, int(tid_raw)))
        except ValueError:
            continue

    return out


def users_get_by_telegram_id_sync(telegram_id: int) -> Optional[str]:
    ws = ensure_worksheet_exists(USERS_SHEET)
    ensure_headers(ws, ["Name", "TelegramID"])

    values = ws.get_all_values()

    for row in values[1:]:
        if len(row) < 2:
            continue
        name = row[0].strip()
        tid_raw = row[1].strip()
        if not name or not tid_raw:
            continue
        try:
            if int(tid_raw) == telegram_id:
                return name
        except ValueError:
            continue

    return None


def users_get_by_name_sync(name: str) -> Optional[int]:
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
    ws = ensure_worksheet_exists(USERS_SHEET)
    ensure_headers(ws, ["Name", "TelegramID"])

    values = ws.get_all_values()

    for idx, row in enumerate(values[1:], start=2):
        if len(row) >= 1 and row[0].strip() == name:
            ws.update(f"A{idx}:B{idx}", [[name, str(telegram_id)]])
            break
    else:
        ws.append_row([name, str(telegram_id)], value_input_option="RAW")

    ws_personal = ensure_worksheet_exists(name)
    ensure_headers(ws_personal, TASK_HEADERS)


def users_delete_by_telegram_id_sync(telegram_id: int) -> Optional[str]:
    ws = ensure_worksheet_exists(USERS_SHEET)
    ensure_headers(ws, ["Name", "TelegramID"])

    values = ws.get_all_values()

    for idx, row in enumerate(values[1:], start=2):
        if len(row) < 2:
            continue
        name = row[0].strip()
        tid_raw = row[1].strip()
        if not tid_raw:
            continue
        try:
            if int(tid_raw) == telegram_id:
                ws.delete_rows(idx)
                return name
        except ValueError:
            continue

    return None


def users_delete_by_name_sync(name: str) -> Optional[int]:
    ws = ensure_worksheet_exists(USERS_SHEET)
    ensure_headers(ws, ["Name", "TelegramID"])

    values = ws.get_all_values()

    for idx, row in enumerate(values[1:], start=2):
        if len(row) < 2:
            continue
        n = row[0].strip()
        tid_raw = row[1].strip()
        if n == name:
            try:
                tid = int(tid_raw) if tid_raw else 0
            except ValueError:
                tid = 0
            ws.delete_rows(idx)
            return tid if tid else None

    return None


# --- async wrappers ---

async def users_get_map() -> Dict[str, int]:
    return await gs_to_thread(users_get_map_sync)


async def users_list() -> List[Tuple[str, int]]:
    return await gs_to_thread(users_list_sync)


async def users_get_by_telegram_id(telegram_id: int) -> Optional[str]:
    return await gs_to_thread(users_get_by_telegram_id_sync, telegram_id)


async def users_get_by_name(name: str) -> Optional[int]:
    return await gs_to_thread(users_get_by_name_sync, name)


async def users_upsert(name: str, telegram_id: int) -> None:
    await gs_to_thread(users_upsert_sync, name, telegram_id)


async def users_delete_by_telegram_id(telegram_id: int) -> Optional[str]:
    return await gs_to_thread(users_delete_by_telegram_id_sync, telegram_id)


async def users_delete_by_name(name: str) -> Optional[int]:
    return await gs_to_thread(users_delete_by_name_sync, name)
