from __future__ import annotations

import time
from collections import Counter, defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shelf.core.scoring import action_weight, recency_decay
from shelf.core.types import Recommendation
from shelf.storage.models import Event, Item

# Minimum number of *distinct interacting users* an item needs, across the
# whole catalog's densest items, before item-based CF is trusted over
# content similarity. Below this, co-occurrence counts are too noisy.
MIN_CATALOG_INTERACTIONS_FOR_CF = 30
MIN_USER_EVENTS_FOR_PERSONALIZATION = 1


def popularity_strategy(
    session: Session, exclude: set[str], limit: int, category: str | None = None
) -> list[Recommendation]:
    """Cold-start fallback: rank items by recency-weighted interaction volume."""
    now = time.time()
    query = select(Event.item_id, Event.action, Event.weight, Event.ts)
    rows = session.execute(query).all()

    scores: Counter[str] = Counter()
    for item_id, action, weight, ts in rows:
        if item_id in exclude:
            continue
        w = action_weight(action, weight if weight != 1.0 else None)
        scores[item_id] += w * recency_decay(ts, now)

    if category:
        allowed = {
            i.item_id
            for i in session.execute(
                select(Item).where(Item.category == category)
            ).scalars()
        }
        scores = Counter({k: v for k, v in scores.items() if k in allowed})

    ranked = scores.most_common(limit)
    return [
        Recommendation(
            item_id=item_id,
            score=round(_normalize(score, ranked), 4),
            reason="Trending across all users this period",
            strategy="popularity",
        )
        for item_id, score in ranked
    ]


def content_similarity_strategy(
    session: Session, user_id: str, exclude: set[str], limit: int
) -> list[Recommendation]:
    """Thin-history fallback: recommend items sharing tags/category with what
    this user already touched, weighted by tag overlap (Jaccard)."""
    user_item_ids = {
        r[0]
        for r in session.execute(
            select(Event.item_id).where(Event.user_id == user_id)
        ).all()
    }
    if not user_item_ids:
        return []

    items = {i.item_id: i for i in session.execute(select(Item)).scalars()}
    seed_tags: set[str] = set()
    seed_categories: set[str] = set()
    for iid in user_item_ids:
        item = items.get(iid)
        if item:
            seed_tags |= {t.strip() for t in item.tags.split(",") if t.strip()}
            if item.category:
                seed_categories.add(item.category)

    if not seed_tags and not seed_categories:
        return []

    scored: list[tuple[str, float, str]] = []
    for iid, item in items.items():
        if iid in exclude or iid in user_item_ids:
            continue
        tags = {t.strip() for t in item.tags.split(",") if t.strip()}
        overlap = seed_tags & tags
        jaccard = len(overlap) / len(seed_tags | tags) if (seed_tags | tags) else 0.0
        same_category = 0.3 if item.category in seed_categories else 0.0
        score = jaccard + same_category
        if score <= 0:
            continue
        if overlap:
            reason = f"Shares tags ({', '.join(sorted(overlap)[:2])}) with items you've viewed"
        else:
            reason = f"Same category ({item.category}) as items you've viewed"
        scored.append((iid, score, reason))

    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:limit]
    max_score = top[0][1] if top else 1.0
    return [
        Recommendation(
            item_id=iid,
            score=round(min(score / max_score, 1.0), 4),
            reason=reason,
            strategy="content-similarity",
        )
        for iid, score, reason in top
    ]


def item_based_cf_strategy(
    session: Session, user_id: str, exclude: set[str], limit: int
) -> list[Recommendation]:
    """Established-data default: 'users who interacted with X also interacted
    with Y', via a co-occurrence matrix built from event history."""
    now = time.time()
    all_rows = session.execute(
        select(Event.user_id, Event.item_id, Event.action, Event.weight, Event.ts)
    ).all()

    user_items: dict[str, dict[str, float]] = defaultdict(dict)
    for uid, item_id, action, weight, ts in all_rows:
        w = action_weight(action, weight if weight != 1.0 else None) * recency_decay(ts, now)
        user_items[uid][item_id] = user_items[uid].get(item_id, 0.0) + w

    target_items = user_items.get(user_id, {})
    if not target_items:
        return []

    co_occurrence: Counter[str] = Counter()
    co_source: dict[str, str] = {}
    for uid, items in user_items.items():
        if uid == user_id:
            continue
        shared = set(items) & set(target_items)
        if not shared:
            continue
        for candidate_item, candidate_weight in items.items():
            if candidate_item in exclude or candidate_item in target_items:
                continue
            contribution = candidate_weight * sum(target_items[s] for s in shared)
            co_occurrence[candidate_item] += contribution
            if candidate_item not in co_source:
                co_source[candidate_item] = next(iter(shared))

    ranked = co_occurrence.most_common(limit)
    return [
        Recommendation(
            item_id=item_id,
            score=round(_normalize(score, ranked), 4),
            reason=f"Frequently interacted with alongside {co_source[item_id]}",
            strategy="item-based-cf",
        )
        for item_id, score in ranked
    ]


def _normalize(score: float, ranked: list[tuple[str, float]]) -> float:
    if not ranked:
        return 0.0
    max_score = ranked[0][1] or 1.0
    return min(score / max_score, 1.0)


def catalog_density(session: Session) -> dict[str, int]:
    """Rough signal-detection stats used to pick a strategy."""
    total_events = session.execute(select(func.count()).select_from(Event)).scalar_one()
    distinct_users = session.execute(select(func.count(func.distinct(Event.user_id)))).scalar_one()
    distinct_items = session.execute(select(func.count(func.distinct(Event.item_id)))).scalar_one()
    return {
        "total_events": total_events,
        "distinct_users": distinct_users,
        "distinct_items": distinct_items,
    }
