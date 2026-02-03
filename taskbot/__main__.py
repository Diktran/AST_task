# __main__.py — точка входа
# python -m taskbot         -> запускает бота
# python -m taskbot archive -> запускает архивирование один раз и выходит

import sys
import asyncio

from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage

from taskbot.config import BOT_TOKEN
from taskbot.tg.handlers import build_dispatcher
from taskbot.sheets.archiver import run_monthly_archive_once


async def _run_bot():
    bot = Bot(token=BOT_TOKEN)
    dp = build_dispatcher()
    await dp.start_polling(bot)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "archive":
        async def _run():
            total = await run_monthly_archive_once()
            print(f"Archived: {total}")
        asyncio.run(_run())
        return

    asyncio.run(_run_bot())


if __name__ == "__main__":
    main()
