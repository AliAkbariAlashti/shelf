from __future__ import annotations

import time

from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    item_id: Mapped[str] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(32))
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    ts: Mapped[float] = mapped_column(Float, default=time.time, index=True)

    __table_args__ = (Index("ix_events_user_item", "user_id", "item_id"),)


class Item(Base):
    """Optional catalog metadata, used by the content-similarity fallback."""

    __tablename__ = "items"

    item_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    tags: Mapped[str] = mapped_column(String(1024), default="")  # comma-separated
    category: Mapped[str] = mapped_column(String(128), default="")
