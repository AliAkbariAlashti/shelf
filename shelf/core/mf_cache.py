"""In-memory cache for fitted ALS models, keyed by a cheap fingerprint of the
event table. ALS training scans the full interaction history, so retraining
on every /v1/recommend call would make matrix factorization unusable past a
trivial amount of data. This cache retrains only when the underlying event
count (a proxy for "the data changed enough to matter") has moved.
"""

from __future__ import annotations

import time

from shelf.core.matrix_factorization import ALSModel

_TTL_SECONDS = 300


class _CacheEntry:
    __slots__ = ("event_count", "fitted_at", "model")

    def __init__(self, model: ALSModel | None, event_count: int):
        self.model = model
        self.event_count = event_count
        self.fitted_at = time.time()


_cache: _CacheEntry | None = None


def get_or_fit(event_count: int, fit_fn) -> ALSModel | None:
    """Return a cached model if the event count and TTL still hold; otherwise
    call `fit_fn()` to retrain and cache the result."""
    global _cache
    now = time.time()
    if (
        _cache is not None
        and _cache.event_count == event_count
        and now - _cache.fitted_at < _TTL_SECONDS
    ):
        return _cache.model

    model = fit_fn()
    _cache = _CacheEntry(model=model, event_count=event_count)
    return model


def clear() -> None:
    global _cache
    _cache = None
