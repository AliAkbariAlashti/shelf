from __future__ import annotations

import time

from shelf.core.engine import recommend
from shelf.storage.models import Event, Item


def test_new_user_gets_popularity_cold_start(session):
    session.add(Item(item_id="a", title="A", tags="x", category="cat1"))
    session.add(Event(user_id="u1", item_id="a", action="purchase", ts=time.time()))
    session.commit()

    result = recommend(session, user_id="brand_new_user", limit=5)

    assert result.strategy == "popularity"
    assert result.cold_start is True
    assert any(r.item_id == "a" for r in result.items)


def test_thin_catalog_falls_back_to_content_similarity(session):
    session.add(Item(item_id="a", title="A", tags="hiking,gear", category="outdoor"))
    session.add(Item(item_id="b", title="B", tags="hiking,poles", category="outdoor"))
    session.add(Item(item_id="c", title="C", tags="coffee,kitchen", category="kitchen"))
    session.add(Event(user_id="u1", item_id="a", action="view", ts=time.time()))
    session.commit()

    result = recommend(session, user_id="u1", limit=5)

    assert result.strategy == "content-similarity"
    ids = [r.item_id for r in result.items]
    assert "b" in ids
    assert "c" not in ids
    assert result.items[0].reason


def test_established_data_uses_item_based_cf(session):
    now = time.time()
    # Build enough events to cross the CF density threshold, with clear
    # co-occurrence: every other user who bought "a" also bought "b". The
    # target user has only bought "a" so far, so "b" is a genuine gap to fill.
    for i in range(1, 40):
        uid = f"user_{i}"
        session.add(Event(user_id=uid, item_id="a", action="purchase", ts=now))
        session.add(Event(user_id=uid, item_id="b", action="purchase", ts=now))
    session.add(Event(user_id="user_0", item_id="a", action="purchase", ts=now))
    session.commit()

    result = recommend(session, user_id="user_0", limit=5)

    assert result.strategy == "item-based-cf"
    assert any(r.item_id == "b" for r in result.items)


def test_pinned_strategy_is_honored(session):
    session.add(Item(item_id="a", title="A", tags="x", category="cat1"))
    session.add(Event(user_id="u1", item_id="a", action="view", ts=time.time()))
    session.commit()

    result = recommend(session, user_id="u1", limit=5, strategy="popularity")

    assert result.strategy == "popularity"
    assert result.cold_start is False


def test_exclude_removes_items_from_results(session):
    session.add(Event(user_id="u1", item_id="a", action="purchase", ts=time.time()))
    session.add(Event(user_id="u2", item_id="a", action="purchase", ts=time.time()))
    session.commit()

    result = recommend(session, user_id="new_user", limit=5, exclude={"a"})

    assert all(r.item_id != "a" for r in result.items)


def test_every_recommendation_has_a_reason(session):
    for i in range(5):
        session.add(Event(user_id=f"user_{i}", item_id="a", action="view", ts=time.time()))
    session.commit()

    result = recommend(session, user_id="brand_new_user", limit=5)

    assert all(r.reason for r in result.items)
