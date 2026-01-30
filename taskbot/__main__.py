# __main__.py позволяет запускать проект командой:
# python -m taskbot

import asyncio  # для запуска async main()

from taskbot.tg.handlers import build_dispatcher  # сборка роутеров/хендлеров
from taskbot.config import BOT_TOKEN  # токен из конфигурации
from aiogram import Bot  # объект Telegram-бота

from taskbot.sheets.schema import ensure_base_structure  # создание структуры в Sheets


async def main() -> None:
    # Создаём объект бота с токеном
    bot = Bot(token=BOT_TOKEN)

    # На старте гарантируем структуру Google Sheets (Users/Общие/CommonProgress)
    await ensure_base_structure()

    # Собираем dispatcher и запускаем polling
    dp = build_dispatcher()
    await dp.start_polling(bot)


if __name__ == "__main__":
    # Запускаем async программу
    asyncio.run(main())
