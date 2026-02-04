# taskbot/storage/sql/db.py
# Подключение к PostgreSQL (async SQLAlchemy)

from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from taskbot.config import DATABASE_URL

# Создаём engine один раз на процесс
engine = create_async_engine(
    DATABASE_URL,
    echo=False,          # можно True для дебага SQL
    pool_pre_ping=True,  # проверка соединения
)

# Фабрика сессий
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
