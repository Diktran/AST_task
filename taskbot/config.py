# config.py — единое место конфигурации проекта

import os  # доступ к переменным окружения
from pathlib import Path  # удобная работа с путями
from dotenv import load_dotenv  # загрузка .env

# Загружаем .env один раз при импорте config
load_dotenv()

# Читаем настройки из окружения
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()  # токен Telegram-бота
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()  # путь к json ключу
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "").strip()  # ID гугл-таблицы

# === Белый список Telegram ID (ВАЖНО) ===
# Формат в .env:
# ALLOWED_TELEGRAM_IDS=123,456,789
_ALLOWED_RAW = os.getenv("ALLOWED_TELEGRAM_IDS", "").strip()

def _parse_allowed_ids(raw: str) -> set[int]:
    """
    Парсим строку вида "123,456" в set({123,456}).
    Пустая строка => пустой set.
    """
    if not raw:
        return set()
    parts = [p.strip() for p in raw.split(",")]  # делим по запятым и чистим пробелы
    result: set[int] = set()  # итоговый набор
    for p in parts:
        if not p:
            continue
        result.add(int(p))  # преобразуем в int
    return result

ALLOWED_TELEGRAM_IDS: set[int] = _parse_allowed_ids(_ALLOWED_RAW)  # whitelist

# --- Проверки конфигурации ---
if not BOT_TOKEN:
    raise RuntimeError("Не найден BOT_TOKEN в .env")

if not GOOGLE_SERVICE_ACCOUNT_JSON:
    raise RuntimeError("Не найден GOOGLE_SERVICE_ACCOUNT_JSON в .env")

if not SPREADSHEET_ID:
    raise RuntimeError("Не найден SPREADSHEET_ID в .env")

# Если whitelist пустой — это опасно (бот будет открыт всем).
# Я делаю строго: если ты включил механику whitelist, то он должен быть заполнен.
# Если хочешь режим "без ограничений" — скажи, я ослаблю.
if not ALLOWED_TELEGRAM_IDS:
    raise RuntimeError(
        "ALLOWED_TELEGRAM_IDS пустой или не задан в .env. "
        "Добавь список разрешённых Telegram ID, иначе бот будет открыт всем."
    )

# --- Пути проекта ---
# BASE_DIR = корень проекта (там лежат .env и service_account.json)
BASE_DIR = Path(__file__).resolve().parent.parent

# Делаем абсолютный путь к JSON ключу (чтобы не зависеть от Working directory)
SERVICE_ACCOUNT_PATH = (BASE_DIR / GOOGLE_SERVICE_ACCOUNT_JSON).resolve()

# Проверяем, что ключ реально существует
if not SERVICE_ACCOUNT_PATH.exists():
    raise RuntimeError(f"Файл Service Account не найден: {SERVICE_ACCOUNT_PATH}")

# --- Имена служебных листов ---
USERS_SHEET = "Users"  # Name <-> TelegramID
COMMON_SHEET = "Общие"  # общие задачи
COMMON_PROGRESS_SHEET = "CommonProgress"  # прогресс общих задач

# --- Заголовки таблиц ---
TASK_HEADERS = ["TaskID", "Task", "From", "Due", "Status", "CreatedAt"]
COMMON_PROGRESS_HEADERS = ["TaskID", "Name", "Status", "DoneAt"]

# --- Статусы ---
STATUS_TODO = "TODO"
STATUS_DONE = "DONE"
