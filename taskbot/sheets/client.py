# client.py — создание gspread клиента и безопасный async-вызов через to_thread

import asyncio  # to_thread
import gspread  # Google Sheets
from google.oauth2.service_account import Credentials  # сервисный аккаунт

from taskbot.config import GOOGLE_SERVICE_ACCOUNT_JSON, SPREADSHEET_ID  # настройки


def build_gspread_client() -> gspread.Client:
    """Создаём gspread.Client через Service Account."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
    ]
    creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_JSON, scopes=scopes)
    return gspread.authorize(creds)


# Глобальные объекты, чтобы не создавать при каждом апдейте
_client = build_gspread_client()
_spreadsheet = _client.open_by_key(SPREADSHEET_ID)


def spreadsheet():
    """Возвращаем объект таблицы (Spreadsheet)."""
    return _spreadsheet


async def gs_to_thread(func, *args, **kwargs):
    """
    gspread синхронный, поэтому выполняем в отдельном потоке.
    """
    return await asyncio.to_thread(func, *args, **kwargs)
