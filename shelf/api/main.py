from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from shelf import __version__
from shelf.api.schemas import (
    EventBatchIn,
    EventIn,
    ItemIn,
    RecommendationOut,
    RecommendResponseOut,
)
from shelf.core.engine import VALID_STRATEGIES, recommend
from shelf.storage.db import get_session, init_db
from shelf.storage.models import Event, Item


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Shelf",
    description="A drop-in recommendation API for teams without a data science team.",
    version=__version__,
    lifespan=lifespan,
)


def db_session():
    with get_session() as session:
        yield session


@app.get("/")
def root():
    return {"name": "shelf", "version": __version__, "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/v1/events", status_code=201)
def track_event(event: EventIn, session: Session = Depends(db_session)):
    row = Event(
        user_id=event.user,
        item_id=event.item,
        action=event.action,
        weight=event.weight if event.weight is not None else 1.0,
        ts=event.ts if event.ts is not None else time.time(),
    )
    session.add(row)
    return {"status": "recorded"}


@app.post("/v1/events/batch", status_code=201)
def track_events_batch(batch: EventBatchIn, session: Session = Depends(db_session)):
    now = time.time()
    rows = [
        Event(
            user_id=e.user,
            item_id=e.item,
            action=e.action,
            weight=e.weight if e.weight is not None else 1.0,
            ts=e.ts if e.ts is not None else now,
        )
        for e in batch.events
    ]
    session.add_all(rows)
    return {"status": "recorded", "count": len(rows)}


@app.put("/v1/items/{item_id}", status_code=200)
def upsert_item(item_id: str, item: ItemIn, session: Session = Depends(db_session)):
    existing = session.get(Item, item_id)
    tags_str = ",".join(item.tags)
    if existing:
        existing.title = item.title
        existing.tags = tags_str
        existing.category = item.category
    else:
        session.add(Item(item_id=item_id, title=item.title, tags=tags_str, category=item.category))
    return {"status": "ok"}


@app.get("/v1/recommend", response_model=RecommendResponseOut)
def get_recommendations(
    user: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
    exclude: str | None = Query(None, description="Comma-separated item ids to exclude"),
    category: str | None = Query(None),
    strategy: str = Query("auto"),
    session: Session = Depends(db_session),
):
    if strategy not in VALID_STRATEGIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy '{strategy}'. Valid values: {sorted(VALID_STRATEGIES)}",
        )
    exclude_set = {i.strip() for i in exclude.split(",") if i.strip()} if exclude else set()

    result = recommend(
        session=session,
        user_id=user,
        limit=limit,
        exclude=exclude_set,
        category=category,
        strategy=strategy,
    )
    return RecommendResponseOut(
        items=[
            RecommendationOut(id=r.item_id, score=r.score, reason=r.reason)
            for r in result.items
        ],
        strategy=result.strategy,
        cold_start=result.cold_start,
    )
