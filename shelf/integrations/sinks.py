"""Where a tracked event actually goes: a running Shelf server over HTTP, or
directly into Shelf's own database when it's embedded in the same process.

Both the Django and FastAPI integrations are written against `EventSink`
rather than against `ShelfClient` directly, so a dev can switch from HTTP to
direct-DB mode (or the reverse) without touching their models or routes.
"""

from __future__ import annotations

import time
from typing import Protocol


class EventSink(Protocol):
    def track(
        self,
        user: str,
        item: str,
        action: str,
        weight: float | None = None,
        ts: float | None = None,
    ) -> None: ...


class HTTPSink:
    """Sends events to a running Shelf server. The default — works whether
    Shelf lives in this process, another container, or a managed instance."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 5.0):
        from shelf.sdk import ShelfClient

        self._client = ShelfClient(base_url=base_url, timeout=timeout)

    def track(
        self,
        user: str,
        item: str,
        action: str,
        weight: float | None = None,
        ts: float | None = None,
    ) -> None:
        self._client.track(user=user, item=item, action=action, weight=weight)


class DirectDBSink:
    """Writes straight into Shelf's own database, bypassing HTTP entirely.

    Only correct when this process shares Shelf's `DATABASE_URL` — e.g. a
    Django app and a Shelf server pointed at the same Postgres instance, or
    a single process that embeds both. Skips network overhead and lets
    tracking happen inside the same DB transaction as the write that
    triggered it.
    """

    def __init__(self):
        from shelf.storage.db import get_session, init_db
        from shelf.storage.models import Event

        init_db()
        self._get_session = get_session
        self._Event = Event

    def track(
        self,
        user: str,
        item: str,
        action: str,
        weight: float | None = None,
        ts: float | None = None,
    ) -> None:
        with self._get_session() as session:
            session.add(
                self._Event(
                    user_id=user,
                    item_id=item,
                    action=action,
                    weight=weight if weight is not None else 1.0,
                    ts=ts if ts is not None else time.time(),
                )
            )
