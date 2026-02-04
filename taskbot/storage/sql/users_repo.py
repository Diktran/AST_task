# taskbot/storage/sql/users_repo.py
# Пользователи в SQL

from __future__ import annotations

from sqlalchemy import select, delete
from taskbot.storage.sql.db import SessionLocal
from taskbot.storage.sql.models import User
from taskbot.storage.sql.outbox import outbox_add


async def users_get_map() -> dict[str, int]:
    async with SessionLocal() as session:
        res = await session.execute(select(User))
        users = res.scalars().all()
        return {u.name: int(u.telegram_id) for u in users}


async def users_list() -> list[tuple[str, int]]:
    async with SessionLocal() as session:
        res = await session.execute(select(User))
        users = res.scalars().all()
        return [(u.name, int(u.telegram_id)) for u in users]


async def users_get_by_telegram_id(telegram_id: int) -> str | None:
    async with SessionLocal() as session:
        res = await session.execute(select(User).where(User.telegram_id == telegram_id))
        u = res.scalar_one_or_none()
        return u.name if u else None


async def users_get_by_name(name: str) -> int | None:
    async with SessionLocal() as session:
        res = await session.execute(select(User).where(User.name == name))
        u = res.scalar_one_or_none()
        return int(u.telegram_id) if u else None


async def users_upsert(name: str, telegram_id: int) -> None:
    """
    Регистрируем пользователя. Если name существует -> обновляем tid.
    Если tid существует -> обновляем name (но handlers это обычно запрещает).
    """
    async with SessionLocal() as session:
        res = await session.execute(select(User).where(User.telegram_id == telegram_id))
        u_by_tid = res.scalar_one_or_none()

        res = await session.execute(select(User).where(User.name == name))
        u_by_name = res.scalar_one_or_none()

        if u_by_tid:
            u_by_tid.name = name
        elif u_by_name:
            u_by_name.telegram_id = telegram_id
        else:
            session.add(User(name=name, telegram_id=telegram_id))

        await session.commit()

    # зеркалим в Google (воркером)
    await outbox_add("USER_UPSERT", {"name": name, "telegram_id": telegram_id})


async def users_delete_by_telegram_id(telegram_id: int) -> str | None:
    async with SessionLocal() as session:
        res = await session.execute(select(User).where(User.telegram_id == telegram_id))
        u = res.scalar_one_or_none()
        if not u:
            return None
        name = u.name
        await session.execute(delete(User).where(User.telegram_id == telegram_id))
        await session.commit()

    await outbox_add("USER_DELETE", {"name": name, "telegram_id": telegram_id})
    return name


async def users_delete_by_name(name: str) -> int | None:
    async with SessionLocal() as session:
        res = await session.execute(select(User).where(User.name == name))
        u = res.scalar_one_or_none()
        if not u:
            return None
        tid = int(u.telegram_id)
        await session.execute(delete(User).where(User.name == name))
        await session.commit()

    await outbox_add("USER_DELETE", {"name": name, "telegram_id": tid})
    return tid
