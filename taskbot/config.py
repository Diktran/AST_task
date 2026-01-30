# config.py — единое место конфигурации проекта

import os  # доступ к переменным окружения
from dotenv import load_dotenv  # загрузка .env

# Загружаем .env один раз при импорте config
load_dotenv()

# Читаем настройки
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "").strip()

# Проверки, чтобы сразу увидеть проблему настройки
if not BOT_TOKEN:
    raise RuntimeError("Не найден BOT_TOKEN в .env")
if not GOOGLE_SERVICE_ACCOUNT_JSON:
    raise RuntimeError("Не найден GOOGLE_SERVICE_ACCOUNT_JSON в .env")
if not SPREADSHEET_ID:
    raise RuntimeError("Не найден SPREADSHEET_ID в .env")

# Имена служебных листов
USERS_SHEET = "Users"                 # Name <-> TelegramID
COMMON_SHEET = "Общие"                # общие задачи (хранятся только тут)
COMMON_PROGRESS_SHEET = "CommonProgress"  # прогресс общих задач (кто закрыл)

# Заголовки таблицы задач (для личных листов и для "Общие" одинаковые)
TASK_HEADERS = ["TaskID", "Task", "From", "Due", "Status", "CreatedAt"]

# Заголовки таблицы прогресса общих задач
COMMON_PROGRESS_HEADERS = ["TaskID", "Name", "Status", "DoneAt"]

# Статусы
STATUS_TODO = "TODO"
STATUS_DONE = "DONE"
