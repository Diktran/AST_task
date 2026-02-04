# taskbot/__main__.py
# Точка входа в проект.
#
# Запуск:
#   python -m taskbot bot        -> запускает Telegram-бота (polling)
#   python -m taskbot db_init    -> создаёт таблицы в PostgreSQL (1 раз)
#   python -m taskbot sync_once  -> делает одну синхронизацию outbox -> Google Sheets
#
# Если аргумент не указан:
#   python -m taskbot            -> эквивалент "bot"

from __future__ import annotations

import asyncio  # асинхронный рантайм
import sys      # аргументы командной строки

from aiogram import Bot  # объект бота
from aiogram.enums import ParseMode  # режим разметки

from taskbot.config import BOT_TOKEN  # токен бота из .env / окружения
from taskbot.tg.handlers import build_dispatcher  # сборка роутеров/хендлеров

from aiogram.client.default import DefaultBotProperties

# инициализация БД (создание таблиц)
from taskbot.storage.sql.init_db import init_db

# один прогон синка (outbox -> google sheets)
from taskbot.sync_worker import run_once


async def run_bot() -> None:
    """
    Запускает Telegram-бота в режиме polling.
    """
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))  # создаём бота
    dp = build_dispatcher()  # собираем Dispatcher с роутерами
    await dp.start_polling(bot)  # запускаем long polling


async def main() -> None:
    """
    Разбираем режим запуска и выполняем нужное действие.
    """
    # если аргументов нет -> считаем что это "bot"
    cmd = sys.argv[1].strip().lower() if len(sys.argv) > 1 else "bot"

    if cmd == "bot":
        await run_bot()
        return

    if cmd == "db_init":
        await init_db()
        print("✅ DB init done (tables created).")
        return

    if cmd == "sync_once":
        await run_once()
        print("✅ Sync once done.")
        return

    # если команда неизвестна — выводим подсказку
    print("Unknown command.")
    print("Use one of:")
    print("  python -m taskbot bot")
    print("  python -m taskbot db_init")
    print("  python -m taskbot sync_once")


if __name__ == "__main__":
    # запускаем main() в asyncio loop
    asyncio.run(main())
