from __future__ import annotations

import requests


class Recommendation(dict):
    """A single recommended item. Behaves like a dict; also exposes attrs."""

    @property
    def id(self) -> str:
        return self["id"]

    @property
    def score(self) -> float:
        return self["score"]

    @property
    def reason(self) -> str:
        return self["reason"]


class ShelfClient:
    """Thin HTTP client for a Shelf server.

    Example:
        shelf = ShelfClient("http://localhost:8000")
        shelf.track(user="user_1", item="sku_1", action="purchase")
        result = shelf.recommend(user="user_1", limit=5)
        for item in result["items"]:
            print(item["id"], item["reason"])
    """

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def track(
        self,
        user: str,
        item: str,
        action: str = "view",
        weight: float | None = None,
    ) -> dict:
        payload = {"user": user, "item": item, "action": action}
        if weight is not None:
            payload["weight"] = weight
        resp = requests.post(f"{self.base_url}/v1/events", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def track_batch(self, events: list[dict]) -> dict:
        resp = requests.post(
            f"{self.base_url}/v1/events/batch", json={"events": events}, timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.json()

    def upsert_item(
        self, item_id: str, title: str = "", tags: list[str] | None = None, category: str = ""
    ) -> dict:
        payload = {"id": item_id, "title": title, "tags": tags or [], "category": category}
        resp = requests.put(
            f"{self.base_url}/v1/items/{item_id}", json=payload, timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.json()

    def recommend(
        self,
        user: str,
        limit: int = 10,
        exclude: list[str] | None = None,
        category: str | None = None,
        strategy: str = "auto",
    ) -> dict:
        params: dict = {"user": user, "limit": limit, "strategy": strategy}
        if exclude:
            params["exclude"] = ",".join(exclude)
        if category:
            params["category"] = category
        resp = requests.get(f"{self.base_url}/v1/recommend", params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()
