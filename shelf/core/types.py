from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Recommendation:
    item_id: str
    score: float
    reason: str
    strategy: str


@dataclass(frozen=True)
class RecommendResult:
    items: list[Recommendation]
    strategy: str
    cold_start: bool
