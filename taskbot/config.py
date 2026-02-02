# config.py — конфигурация проекта (переменные окружения, списки доступа, константы)

import os  # env
from pathlib import Path  # пути
from dotenv import load_dotenv  # .env

load_dotenv()  # читаем .env


def _parse_ids(raw: str) -> set[int]:
    """
    Парсим строку вида "123,456" в set({123,456})
    """
    raw = (raw or "").strip()
    if not raw:
        return set()
    parts = [p.strip() for p in raw.split(",")]
    out: set[int] = set()
    for p in parts:
        if not p:
            continue
        out.add(int(p))
    return out


# --- базовые настройки ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "").strip()

# --- доступ ---
ALLOWED_TELEGRAM_IDS: set[int] = _parse_ids(os.getenv("ALLOWED_TELEGRAM_IDS", ""))
ADMIN_TELEGRAM_IDS: set[int] = _parse_ids(os.getenv("ADMIN_TELEGRAM_IDS", ""))

# админы всегда имеют доступ
ALLOWED_TELEGRAM_IDS = ALLOWED_TELEGRAM_IDS | ADMIN_TELEGRAM_IDS

# --- проверки ---
if not BOT_TOKEN:
    raise RuntimeError("Не найден BOT_TOKEN в .env")

if not GOOGLE_SERVICE_ACCOUNT_JSON:
    raise RuntimeError("Не найден GOOGLE_SERVICE_ACCOUNT_JSON в .env")

if not SPREADSHEET_ID:
    raise RuntimeError("Не найден SPREADSHEET_ID в .env")

if not ALLOWED_TELEGRAM_IDS:
    raise RuntimeError("ALLOWED_TELEGRAM_IDS пустой. Добавь список разрешённых Telegram ID в .env")

if not ADMIN_TELEGRAM_IDS:
    raise RuntimeError("ADMIN_TELEGRAM_IDS пустой. Добавь Telegram ID админов в .env")

# --- пути ---
BASE_DIR = Path(__file__).resolve().parent.parent
SERVICE_ACCOUNT_PATH = (BASE_DIR / GOOGLE_SERVICE_ACCOUNT_JSON).resolve()

if not SERVICE_ACCOUNT_PATH.exists():
    raise RuntimeError(f"Файл Service Account не найден: {SERVICE_ACCOUNT_PATH}")

# --- имена листов ---
USERS_SHEET = "Users"
COMMON_SHEET = "Общие"
COMMON_PROGRESS_SHEET = "CommonProgress"

# --- заголовки ---
TASK_HEADERS = ["TaskID", "Task", "From", "Due", "Status", "CreatedAt"]
COMMON_PROGRESS_HEADERS = ["TaskID", "Name", "Status", "DoneAt"]

# --- статусы ---
STATUS_TODO = "TODO"
STATUS_DONE = "DONE"
