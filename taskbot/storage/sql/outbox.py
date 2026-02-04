# taskbot/storage/sql/outbox.py
# Запись событий в outbox

from __future__ import annotations

import json
from datetime import datetime
from sqlalchemy import select, update
from taskbot.storage.sql.db import SessionLocal
from taskbot.storage.sql.models import Outbox


async def outbox_add(event_type: str, payload: dict) -> None:
    """
    Кладём событие в outbox. payload сериализуем в JSON.
    """
    async with SessionLocal() as session:
        session.add(Outbox(event_type=event_type, payload_json=json.dumps(payload, ensure_ascii=False)))
        await session.commit()


async def outbox_fetch_batch(limit: int = 200) -> list[Outbox]:
    """
    Берём пачку необработанных событий.
    """
    async with SessionLocal() as session:
        q = select(Outbox).where(Outbox.processed_at.is_(None)).order_by(Outbox.id).limit(limit)
        res = await session.execute(q)
        return list(res.scalars().all())


async def outbox_mark_processed(ids: list[int]) -> None:
    """
    Отмечаем события обработанными (processed_at=now)
    """
    if not ids:
        return
    async with SessionLocal() as session:
        await session.execute(
            update(Outbox)
            .where(Outbox.id.in_(ids))
            .values(processed_at=datetime.utcnow(), error=None)
        )
        await session.commit()


async def outbox_mark_error(event_id: int, error: str) -> None:
    """
    Записываем ошибку (событие останется не processed — можно потом обработать вручную/повторно)
    """
    async with SessionLocal() as session:
        await session.execute(
            update(Outbox).where(Outbox.id == event_id).values(error=error)
        )
        await session.commit()
