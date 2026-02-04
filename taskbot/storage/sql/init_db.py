# taskbot/storage/sql/init_db.py
# Создание таблиц (однократно)

from __future__ import annotations

import asyncio
from taskbot.storage.sql.db import engine
from taskbot.storage.sql.models import Base


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(init_db())
