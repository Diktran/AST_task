# taskbot/sync_worker.py
# sync_worker: раз в минуту берёт outbox и применяет в Google Sheets пачкой.

from __future__ import annotations

import asyncio

from taskbot.storage.sql.outbox import outbox_fetch_batch, outbox_mark_processed, outbox_mark_error
from taskbot.storage.sql.users_repo import users_get_map
from taskbot.sheets.mirror_schema import ensure_base_structure
from taskbot.sheets.mirror_apply import apply_events


async def run_once() -> None:
    # 1) Обеспечим базовую структуру листов (Users/Общие/Progress + листы людей)
    users_map = await users_get_map()
    await ensure_base_structure(list(users_map.keys()))

    # 2) Берём пачку outbox
    batch = await outbox_fetch_batch(limit=200)
    if not batch:
        return

    # 3) Готовим формат для apply_events
    events = [(e.id, e.event_type, e.payload_json) for e in batch]

    # 4) Применяем
    processed_ids: list[int] = []
    for e in batch:
        try:
            await apply_events([(e.id, e.event_type, e.payload_json)])
            processed_ids.append(e.id)
        except Exception as ex:
            await outbox_mark_error(e.id, str(ex))

    # 5) Отмечаем успешные
    await outbox_mark_processed(processed_ids)


async def main_loop() -> None:
    while True:
        try:
            await run_once()
        except Exception as ex:
            # чтобы воркер не умер
            print("SYNC_WORKER ERROR:", ex)
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main_loop())
