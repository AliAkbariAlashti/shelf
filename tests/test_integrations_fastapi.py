from __future__ import annotations

import time

import pytest

from shelf.integrations import fastapi as shelf_fastapi
from shelf.integrations.sinks import DirectDBSink
from shelf.sdk import ShelfClient


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    shelf_fastapi.reset_client_cache()
    monkeypatch.delenv("SHELF_DIRECT_DB", raising=False)
    monkeypatch.delenv("SHELF_URL", raising=False)
    yield
    shelf_fastapi.reset_client_cache()


def test_get_shelf_defaults_to_http_client():
    client = shelf_fastapi.get_shelf()
    assert isinstance(client, ShelfClient)
    assert client.base_url == "http://localhost:8000"


def test_get_shelf_reads_custom_url(monkeypatch):
    monkeypatch.setenv("SHELF_URL", "http://shelf.internal:9000")
    shelf_fastapi.reset_client_cache()

    client = shelf_fastapi.get_shelf()
    assert client.base_url == "http://shelf.internal:9000"


def test_get_shelf_direct_db_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELF_DIRECT_DB", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/shelf-test.db")
    shelf_fastapi.reset_client_cache()

    client = shelf_fastapi.get_shelf()
    assert isinstance(client, DirectDBSink)


def test_get_shelf_is_cached_across_calls():
    first = shelf_fastapi.get_shelf()
    second = shelf_fastapi.get_shelf()
    assert first is second


def test_direct_db_sink_writes_a_real_event(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/shelf-test.db")

    import importlib

    import shelf.storage.db as db_module

    importlib.reload(db_module)

    sink = DirectDBSink()
    sink.track(user="u1", item="sku_1", action="purchase", ts=time.time())

    from shelf.storage.db import get_session
    from shelf.storage.models import Event

    with get_session() as session:
        rows = session.query(Event).all()
        assert len(rows) == 1
        assert rows[0].user_id == "u1"
        assert rows[0].item_id == "sku_1"
        assert rows[0].action == "purchase"
