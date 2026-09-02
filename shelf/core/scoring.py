from __future__ import annotations

import math
import time

# Action weights: how strongly each event type signals preference.
ACTION_WEIGHTS: dict[str, float] = {
    "view": 1.0,
    "click": 1.0,
    "cart": 2.5,
    "wishlist": 2.0,
    "rate": 3.0,
    "purchase": 4.0,
    "dismiss": -2.0,
}

# Half-life (in seconds) for recency decay: a 14-day-old event counts for
# half as much as one from right now.
RECENCY_HALF_LIFE_SECONDS = 14 * 24 * 3600


def action_weight(action: str, explicit_weight: float | None = None) -> float:
    if explicit_weight is not None:
        return explicit_weight
    return ACTION_WEIGHTS.get(action, 1.0)


def recency_decay(event_ts: float, now: float | None = None) -> float:
    now = now if now is not None else time.time()
    age = max(0.0, now - event_ts)
    return math.pow(0.5, age / RECENCY_HALF_LIFE_SECONDS)
