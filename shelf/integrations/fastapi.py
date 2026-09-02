"""FastAPI integration: a `Depends`-based dependency that hands your route a
ready-to-use Shelf client, configured from environment variables once.

    from fastapi import Depends
    from shelf.integrations.fastapi import get_shelf
    from shelf.sdk import ShelfClient

    @app.post("/purchase")
    def purchase(item_id: str, user_id: str, shelf: ShelfClient = Depends(get_shelf)):
        # ... your existing purchase logic ...
        shelf.track(user=user_id, item=item_id, action="purchase")
        return {"status": "ok"}

Configuration (env vars, read once at first use):
  SHELF_URL        base URL of a running Shelf server (default http://localhost:8000)
  SHELF_DIRECT_DB  if "true", write straight into Shelf's database instead of
                   over HTTP — only correct when this app and Shelf share the
                   same DATABASE_URL

`get_shelf` always returns something with `.track(...)`. When direct-DB mode
is off it's a real `ShelfClient`, so `.recommend(...)` is also available for
calling Shelf's `/v1/recommend` from inside a route.
"""

from __future__ import annotations

import os
from functools import lru_cache

from shelf.integrations.sinks import DirectDBSink
from shelf.sdk import ShelfClient


@lru_cache(maxsize=1)
def _client() -> ShelfClient | DirectDBSink:
    if os.environ.get("SHELF_DIRECT_DB", "").lower() in ("1", "true", "yes"):
        return DirectDBSink()
    base_url = os.environ.get("SHELF_URL", "http://localhost:8000")
    return ShelfClient(base_url=base_url)


def get_shelf() -> ShelfClient | DirectDBSink:
    """FastAPI dependency: `shelf: ShelfClient = Depends(get_shelf)`."""
    return _client()


def reset_client_cache() -> None:
    """Drop the cached client so the next call re-reads env vars. Mainly
    useful in tests that toggle SHELF_DIRECT_DB / SHELF_URL."""
    _client.cache_clear()
