# client.py — создание gspread клиента и безопасный async-вызов через to_thread

import asyncio  # to_thread
import gspread  # Google Sheets
from google.oauth2.service_account import Credentials  # сервисный аккаунт

from taskbot.config import SERVICE_ACCOUNT_PATH, SPREADSHEET_ID  # абсолютный путь и ID таблицы


def build_gspread_client() -> gspread.Client:
    """Создаём gspread.Client через Service Account."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
    ]  # необходимые права

    # Загружаем креды по абсолютному пути (не зависит от Working directory)
    creds = Credentials.from_service_account_file(str(SERVICE_ACCOUNT_PATH), scopes=scopes)

    return gspread.authorize(creds)  # возвращаем авторизованный клиент


# Создаём клиента один раз
_client = build_gspread_client()

# Открываем таблицу один раз
_spreadsheet = _client.open_by_key(SPREADSHEET_ID)


def spreadsheet():
    """Возвращаем объект таблицы (Spreadsheet)."""
    return _spreadsheet


async def gs_to_thread(func, *args, **kwargs):
    """
    gspread синхронный, поэтому выполняем в отдельном потоке,
    чтобы не блокировать Telegram-бота.
    """
    return await asyncio.to_thread(func, *args, **kwargs)
