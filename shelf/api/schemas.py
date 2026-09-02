from __future__ import annotations

import time

from pydantic import BaseModel, Field


class EventIn(BaseModel):
    user: str = Field(..., min_length=1)
    item: str = Field(..., min_length=1)
    action: str = Field(default="view")
    weight: float | None = None
    ts: float | None = None


class EventBatchIn(BaseModel):
    events: list[EventIn]


class ItemIn(BaseModel):
    id: str
    title: str = ""
    tags: list[str] = Field(default_factory=list)
    category: str = ""


class RecommendationOut(BaseModel):
    id: str
    score: float
    reason: str


class RecommendResponseOut(BaseModel):
    items: list[RecommendationOut]
    strategy: str
    cold_start: bool
    generated_at: float = Field(default_factory=time.time)
