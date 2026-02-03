# config.py — универсальный конфиг (совместимость со старым кодом и новым)

from __future__ import annotations

import os
from pathlib import Path
from typing import Set

from dotenv import load_dotenv

load_dotenv()


def _parse_ids(value: str) -> Set[int]:
    out: Set[int] = set()
    raw = (value or "").strip()
    if not raw:
        return out
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


# --- Telegram ---
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()

# --- Google Sheets (новые и старые переменные) ---
GOOGLE_SPREADSHEET_ID: str = os.getenv("GOOGLE_SPREADSHEET_ID", "").strip()
GOOGLE_SERVICE_ACCOUNT_JSON: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "service_account.json").strip()

SPREADSHEET_ID: str = os.getenv("SPREADSHEET_ID", "").strip()
SERVICE_ACCOUNT_PATH: str = os.getenv("SERVICE_ACCOUNT_PATH", "").strip()

# Алиасы для совместимости
if not SPREADSHEET_ID and GOOGLE_SPREADSHEET_ID:
    SPREADSHEET_ID = GOOGLE_SPREADSHEET_ID

if not SERVICE_ACCOUNT_PATH and GOOGLE_SERVICE_ACCOUNT_JSON:
    SERVICE_ACCOUNT_PATH = GOOGLE_SERVICE_ACCOUNT_JSON

SERVICE_ACCOUNT_PATH = str(Path(SERVICE_ACCOUNT_PATH).resolve())

# --- Sheets names ---
USERS_SHEET: str = os.getenv("USERS_SHEET", "Users").strip()
COMMON_SHEET: str = os.getenv("COMMON_SHEET", "Общие").strip()

# !!! ВАЖНО: старый schema.py ждёт этот лист:
COMMON_PROGRESS_SHEET: str = os.getenv("COMMON_PROGRESS_SHEET", "CommonProgress").strip()

# --- Headers ---
USERS_HEADERS = ["Name", "TelegramID"]

TASK_HEADERS = ["TaskID", "Task", "From", "Due", "Status", "CreatedAt"]

# Если common.py/schema.py ждут прогресс-хедеры:
COMMON_PROGRESS_HEADERS = ["TaskID", "User", "Status", "UpdatedAt"]

# --- Statuses ---
STATUS_TODO: str = os.getenv("STATUS_TODO", "TODO").strip()
STATUS_DONE: str = os.getenv("STATUS_DONE", "DONE").strip()
STATUS_ARCHIVE: str = os.getenv("STATUS_ARCHIVE", "ARCHIVE").strip()

# --- Access control ---
ALLOWED_TELEGRAM_IDS = _parse_ids(os.getenv("ALLOWED_TELEGRAM_IDS", ""))
ADMIN_TELEGRAM_IDS = _parse_ids(os.getenv("ADMIN_TELEGRAM_IDS", ""))

# --- Warnings ---
if not BOT_TOKEN:
    print("WARNING: BOT_TOKEN is empty (check .env)")
if not SPREADSHEET_ID:
    print("WARNING: SPREADSHEET_ID/GOOGLE_SPREADSHEET_ID is empty (check .env)")
if not SERVICE_ACCOUNT_PATH:
    print("WARNING: SERVICE_ACCOUNT_PATH/GOOGLE_SERVICE_ACCOUNT_JSON is empty (check .env)")
