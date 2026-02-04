# taskbot/storage/sql/models.py
# Модели таблиц PostgreSQL

from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    String, Integer, BigInteger, DateTime, Text, ForeignKey,
    UniqueConstraint, Index
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Task(Base):
    """
    Личные задачи.
    task_id = автонумерация (id).
    """
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # порядковый номер
    assignee_name: Mapped[str] = mapped_column(String(64), index=True)  # имя вкладки (как раньше)
    task_text: Mapped[str] = mapped_column(Text)
    from_name: Mapped[str] = mapped_column(String(128))
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class CommonTask(Base):
    """
    Общие задачи (одна таблица, без дублей по людям)
    """
    __tablename__ = "common_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # порядковый номер
    task_text: Mapped[str] = mapped_column(Text)
    from_name: Mapped[str] = mapped_column(String(128))
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class CommonProgress(Base):
    """
    Прогресс по общим задачам: кто закрыл.
    UNIQUE(task_id, user_name) — чтобы без дублей.
    """
    __tablename__ = "common_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("common_tasks.id", ondelete="CASCADE"))
    user_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("task_id", "user_name", name="uq_common_progress"),
        Index("ix_common_progress_user", "user_name"),
    )


class Outbox(Base):
    """
    Очередь событий для зеркалирования в Google Sheets.
    sync_worker раз в минуту берёт пачку NOT synced.
    """
    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)   # например TASK_CREATED
    payload_json: Mapped[str] = mapped_column(Text)                   # JSON строка
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
