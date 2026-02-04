# taskbot/sheets/users.py
# ВАЖНО: теперь это НЕ Google Sheets, а SQL (название файла оставляем, чтобы handlers не менять)

from __future__ import annotations
from taskbot.storage.sql.users_repo import (
    users_get_map,
    users_list,
    users_upsert,
    users_get_by_telegram_id,
    users_get_by_name,
    users_delete_by_telegram_id,
    users_delete_by_name,
)

__all__ = [
    "users_get_map",
    "users_list",
    "users_upsert",
    "users_get_by_telegram_id",
    "users_get_by_name",
    "users_delete_by_telegram_id",
    "users_delete_by_name",
]
