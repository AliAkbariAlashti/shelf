from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    import shelf.storage.db as db_module
    import importlib

    importlib.reload(db_module)

    import shelf.api.main as main_module

    importlib.reload(main_module)

    with TestClient(main_module.app) as c:
        yield c

    os.remove(db_path)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_track_and_recommend_roundtrip(client):
    resp = client.post("/v1/events", json={"user": "u1", "item": "sku_a", "action": "purchase"})
    assert resp.status_code == 201

    resp = client.get("/v1/recommend", params={"user": "u2"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["strategy"] == "popularity"
    assert body["cold_start"] is True
    assert any(item["id"] == "sku_a" for item in body["items"])


def test_recommend_requires_user(client):
    resp = client.get("/v1/recommend")
    assert resp.status_code == 422


def test_invalid_strategy_returns_400(client):
    resp = client.get("/v1/recommend", params={"user": "u1", "strategy": "bogus"})
    assert resp.status_code == 400


def test_batch_events(client):
    resp = client.post(
        "/v1/events/batch",
        json={
            "events": [
                {"user": "u1", "item": "a", "action": "view"},
                {"user": "u1", "item": "b", "action": "purchase"},
            ]
        },
    )
    assert resp.status_code == 201
    assert resp.json()["count"] == 2


def test_upsert_item_and_content_similarity(client):
    client.put(
        "/v1/items/sku_a", json={"id": "sku_a", "title": "A", "tags": ["hiking"], "category": "outdoor"}
    )
    client.put(
        "/v1/items/sku_b", json={"id": "sku_b", "title": "B", "tags": ["hiking"], "category": "outdoor"}
    )
    client.post("/v1/events", json={"user": "u1", "item": "sku_a", "action": "view"})

    resp = client.get("/v1/recommend", params={"user": "u1"})
    body = resp.json()
    assert body["strategy"] == "content-similarity"
    assert any(item["id"] == "sku_b" for item in body["items"])
