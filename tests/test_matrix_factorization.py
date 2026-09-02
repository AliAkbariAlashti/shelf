from __future__ import annotations

import time

from shelf.core import mf_cache
from shelf.core.engine import recommend
from shelf.core.matrix_factorization import fit_als
from shelf.core.strategies import MIN_EVENTS_FOR_MATRIX_FACTORIZATION
from shelf.storage.models import Event


def test_fit_als_returns_none_on_insufficient_data():
    assert fit_als({("u1", "a"): 1.0}) is None


def test_fit_als_ranks_same_cluster_item_above_other_cluster():
    interactions = {}
    for i in range(15):
        interactions[(f"cluster1_{i}", "a")] = 4.0
        interactions[(f"cluster1_{i}", "b")] = 4.0
        interactions[(f"cluster1_{i}", "e")] = 4.0
        interactions[(f"cluster2_{i}", "c")] = 4.0
        interactions[(f"cluster2_{i}", "d")] = 4.0

    # A target user in cluster 1 who hasn't touched "e" yet.
    interactions[("target", "a")] = 4.0
    interactions[("target", "b")] = 4.0

    model = fit_als(interactions, seed=1)
    assert model is not None

    ranked = model.recommend("target", exclude={"a", "b"}, limit=4)
    ranked_ids = [item_id for item_id, _ in ranked]
    assert ranked_ids[0] == "e"


def test_mf_cache_reuses_model_for_same_event_count():
    mf_cache.clear()
    calls = {"count": 0}

    def fit_fn():
        calls["count"] += 1
        return fit_als({("u1", "a"): 1.0, ("u2", "b"): 1.0})

    mf_cache.get_or_fit(event_count=10, fit_fn=fit_fn)
    mf_cache.get_or_fit(event_count=10, fit_fn=fit_fn)
    assert calls["count"] == 1

    mf_cache.get_or_fit(event_count=11, fit_fn=fit_fn)
    assert calls["count"] == 2


def test_engine_escalates_to_matrix_factorization_at_high_volume(session):
    now = time.time()
    n_users = 20
    # Every other user has bought both "a" and "b"; the target user has only
    # bought "a" so far, so "b" is a genuine gap for the model to fill.
    for i in range(1, n_users):
        session.add(Event(user_id=f"user_{i}", item_id="a", action="purchase", ts=now))
        session.add(Event(user_id=f"user_{i}", item_id="b", action="purchase", ts=now))
    session.add(Event(user_id="user_0", item_id="a", action="purchase", ts=now))
    # Pad with filler events on other items so total_events crosses the MF
    # threshold without changing the a/b preference signal much.
    filler_needed = MIN_EVENTS_FOR_MATRIX_FACTORIZATION - (2 * n_users - 1)
    for i in range(filler_needed):
        session.add(Event(user_id=f"filler_{i}", item_id="z", action="view", ts=now))
    session.commit()

    result = recommend(session, user_id="user_0", limit=5)

    assert result.strategy == "matrix-factorization"
    assert any(r.item_id == "b" for r in result.items)
    assert all(r.reason for r in result.items)


def test_matrix_factorization_excludes_items_user_already_has(session):
    now = time.time()
    n_users = 20
    for i in range(n_users):
        session.add(Event(user_id=f"user_{i}", item_id="a", action="purchase", ts=now))
        session.add(Event(user_id=f"user_{i}", item_id="b", action="purchase", ts=now))
    filler_needed = MIN_EVENTS_FOR_MATRIX_FACTORIZATION - (n_users * 2)
    for i in range(filler_needed):
        session.add(Event(user_id=f"filler_{i}", item_id="z", action="view", ts=now))
    session.commit()

    # No explicit `exclude` passed — the strategy itself must keep a user's
    # own already-interacted items out of their own recommendations.
    result = recommend(session, user_id="user_0", limit=5, strategy="matrix-factorization")

    ids = [r.item_id for r in result.items]
    assert "a" not in ids
    assert "b" not in ids
