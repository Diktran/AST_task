# taskbot/sheets/mirror_client.py
# Клиент Google Sheets ТОЛЬКО для записи (зеркало)

from __future__ import annotations

import asyncio
from functools import partial
from typing import Callable, Any

import gspread
from google.oauth2.service_account import Credentials

from taskbot.config import SERVICE_ACCOUNT_PATH, SPREADSHEET_ID


def build_gspread_client() -> gspread.Client:
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_PATH, scopes=scopes)
    return gspread.authorize(creds)


_client = build_gspread_client()
_spreadsheet = _client.open_by_key(SPREADSHEET_ID)


def spreadsheet():
    return _spreadsheet


async def to_thread(fn: Callable[..., Any], *args, **kwargs) -> Any:
    """
    Чтобы gspread (синхронный) не блокировал event loop.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(fn, *args, **kwargs))
