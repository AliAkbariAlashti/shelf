from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from shelf.core.strategies import (
    MIN_CATALOG_INTERACTIONS_FOR_CF,
    MIN_EVENTS_FOR_MATRIX_FACTORIZATION,
    catalog_density,
    content_similarity_strategy,
    item_based_cf_strategy,
    matrix_factorization_strategy,
    popularity_strategy,
)
from shelf.core.types import RecommendResult
from shelf.storage.models import Event

VALID_STRATEGIES = {
    "auto",
    "popularity",
    "content-similarity",
    "item-based-cf",
    "matrix-factorization",
}


def recommend(
    session: Session,
    user_id: str,
    limit: int = 10,
    exclude: set[str] | None = None,
    category: str | None = None,
    strategy: str = "auto",
) -> RecommendResult:
    exclude = exclude or set()

    if strategy != "auto":
        return _run_pinned(session, strategy, user_id, exclude, limit, category)

    user_event_count = session.execute(
        select(Event.id).where(Event.user_id == user_id).limit(1)
    ).first()
    density = catalog_density(session)

    if not user_event_count:
        items = popularity_strategy(session, exclude, limit, category)
        return RecommendResult(items=items, strategy="popularity", cold_start=True)

    if density["total_events"] < MIN_CATALOG_INTERACTIONS_FOR_CF:
        items = content_similarity_strategy(session, user_id, exclude, limit)
        if items:
            return RecommendResult(items=items, strategy="content-similarity", cold_start=False)
        items = popularity_strategy(session, exclude, limit, category)
        return RecommendResult(items=items, strategy="popularity", cold_start=False)

    if density["total_events"] >= MIN_EVENTS_FOR_MATRIX_FACTORIZATION:
        items = matrix_factorization_strategy(session, user_id, exclude, limit)
        if items:
            return RecommendResult(items=items, strategy="matrix-factorization", cold_start=False)

    items = item_based_cf_strategy(session, user_id, exclude, limit)
    if items:
        return RecommendResult(items=items, strategy="item-based-cf", cold_start=False)

    items = content_similarity_strategy(session, user_id, exclude, limit)
    if items:
        return RecommendResult(items=items, strategy="content-similarity", cold_start=False)

    items = popularity_strategy(session, exclude, limit, category)
    return RecommendResult(items=items, strategy="popularity", cold_start=False)


def _run_pinned(
    session: Session,
    strategy: str,
    user_id: str,
    exclude: set[str],
    limit: int,
    category: str | None,
) -> RecommendResult:
    if strategy == "popularity":
        items = popularity_strategy(session, exclude, limit, category)
    elif strategy == "content-similarity":
        items = content_similarity_strategy(session, user_id, exclude, limit)
    elif strategy == "item-based-cf":
        items = item_based_cf_strategy(session, user_id, exclude, limit)
    elif strategy == "matrix-factorization":
        items = matrix_factorization_strategy(session, user_id, exclude, limit)
    else:
        raise ValueError(f"Unknown strategy: {strategy!r}. Valid: {sorted(VALID_STRATEGIES)}")
    return RecommendResult(items=items, strategy=strategy, cold_start=False)
