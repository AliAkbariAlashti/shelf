# Shelf

[![PyPI](https://img.shields.io/pypi/v/shelf-recs.svg)](https://pypi.org/project/shelf-recs/)
[![CI](https://github.com/AliAkbariAlashti/shelf/actions/workflows/ci.yml/badge.svg)](https://github.com/AliAkbariAlashti/shelf/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A drop-in recommendation API for teams without a data science bench.

Most teams have the data for recommendations — page views, cart adds, purchases,
ratings — but not someone whose job is turning that into a model. Shelf takes the
events you're already logging and returns a ranked, **explained** list of items.
It picks the algorithm for you and tells you which one it used.

```
POST /v1/events        → log a user/item interaction
GET  /v1/recommend      → get ranked, explained recommendations
```

## Why

Recommendation libraries (`implicit`, `LightFM`, `Surprise`) assume you already
know which algorithm fits your data, how to handle users with zero history, and
how to retrain on a schedule. Shelf collapses that decision: it looks at your
event volume and falls back automatically:

| Your data looks like...              | Shelf uses                | 
|---------------------------------------|----------------------------|
| A brand-new user, no history           | **popularity** — recency-weighted trending items |
| A thin catalog or sparse history       | **content-similarity** — tag/category overlap |
| Established interaction history        | **item-based CF** — "people who did X also did Y" |

Every recommendation returned includes a `reason` string safe to show directly
in your UI: *"Frequently bought alongside Trail Jacket."*

> Matrix factorization for high-volume, dense catalogs is planned for a future
> release — see [Roadmap](#roadmap). Shelf does not fake it in the meantime.

## Quickstart

```bash
pip install shelf-recs
shelf seed      # populates shelf.db with a small sample catalog + events
shelf serve     # runs on http://localhost:8000
```

Or with Docker:

```bash
docker compose up --build
```

Then:

```bash
curl -X POST http://localhost:8000/v1/events \
  -H "Content-Type: application/json" \
  -d '{"user": "user_42", "item": "sku_trail_jacket", "action": "purchase"}'

curl "http://localhost:8000/v1/recommend?user=user_42&limit=5"
```

## Python SDK

```python
from shelf.sdk import ShelfClient

shelf = ShelfClient("http://localhost:8000")

shelf.track(user="user_42", item="sku_trail_jacket", action="purchase")

result = shelf.recommend(user="user_42", limit=5)
for item in result["items"]:
    print(item["id"], "-", item["reason"])
```

No SDK required — it's a REST API. Call it from any language.

## API

### `POST /v1/events`
Log a single interaction.

```json
{"user": "user_42", "item": "sku_1", "action": "purchase", "weight": null, "ts": null}
```

`action` is one of `view`, `click`, `cart`, `wishlist`, `rate`, `purchase`,
`dismiss` — each has a built-in weight, or pass your own via `weight`.

### `POST /v1/events/batch`
Same shape, wrapped in `{"events": [...]}`, for bulk backfills.

### `PUT /v1/items/{item_id}`
Optional catalog metadata (`title`, `tags`, `category`) used by the
content-similarity fallback. Skip this if you only care about the
popularity and CF strategies.

### `GET /v1/recommend`

| param      | required | description |
|------------|----------|-------------|
| `user`     | yes      | user id to recommend for |
| `limit`    | no       | max items, default 10 |
| `exclude`  | no       | comma-separated item ids to omit (e.g. items already in cart) |
| `category` | no       | restrict popularity fallback to one category |
| `strategy` | no       | `auto` (default), or pin one of `popularity`, `content-similarity`, `item-based-cf` |

Response:

```json
{
  "items": [
    {"id": "sku_gaiters", "score": 0.94, "reason": "Frequently interacted with alongside sku_trail_jacket"}
  ],
  "strategy": "item-based-cf",
  "cold_start": false,
  "generated_at": 1788370000.12
}
```

## Configuration

| env var         | default            | purpose |
|-----------------|--------------------|---------|
| `DATABASE_URL`  | `sqlite:///shelf.db` | any SQLAlchemy URL; use Postgres in production |
| `SHELF_DB_PATH` | `shelf.db`          | shortcut for the default SQLite file path |

## When Shelf is the wrong tool

- **Fewer than ~500 weekly active users** — a plain "most popular" query beats
  any model, and Shelf's popularity strategy already covers that. You don't
  need the rest of it.
- **One static rule is enough** ("show items in the same category") — that's
  a query, not a recommender.
- **You need sub-5ms P99 at extreme scale** and already run ML infra —
  Shelf optimizes for zero-setup, not for out-competing a tuned in-house stack.
- **You need regulatory explainability** beyond a human-readable reason string.

## Roadmap

- [ ] Matrix factorization strategy for high-volume, dense catalogs
- [ ] Session-based (sequential) recommendations for anonymous/pre-login users
- [ ] Postgres-backed nightly retraining job for the CF co-occurrence matrix
- [ ] JS/TS SDK

## Development

```bash
pip install -e ".[dev]"
pytest -q
ruff check .
```

## License

MIT — see [LICENSE](LICENSE).
