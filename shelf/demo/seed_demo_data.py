"""Populate a local Shelf database with a small sample catalog and event
history, so `shelf serve` has something to recommend from immediately."""

from __future__ import annotations

import random
import time

from shelf.storage.db import get_session, init_db
from shelf.storage.models import Event, Item

CATALOG = [
    ("sku_trail_jacket", "Trail Rain Jacket", "outerwear,waterproof,hiking", "apparel"),
    ("sku_base_layer", "Merino Base Layer", "thermal,hiking,layering", "apparel"),
    ("sku_trek_poles", "Carbon Trekking Poles", "hiking,gear,lightweight", "gear"),
    ("sku_gaiters", "Waterproof Gaiters", "waterproof,hiking,accessory", "apparel"),
    ("sku_rain_cover", "Pack Rain Cover", "waterproof,gear,accessory", "gear"),
    ("sku_espresso_grinder", "Espresso Grinder", "coffee,kitchen,manual", "kitchen"),
    ("sku_grinder_pro", "Espresso Grinder Pro", "coffee,kitchen,electric", "kitchen"),
    ("sku_milk_frother", "Precision Milk Frother", "coffee,kitchen,accessory", "kitchen"),
    ("sku_pour_kettle", "Pour-Over Kettle", "coffee,kitchen,manual", "kitchen"),
    ("sku_cleaning_tabs", "Espresso Cleaning Tablets", "coffee,kitchen,maintenance", "kitchen"),
    ("sku_desk_lamp", "Warm White Desk Lamp", "desk,lighting,office", "office"),
    ("sku_monitor_riser", "Bamboo Monitor Riser", "desk,office,ergonomic", "office"),
    ("sku_cable_tray", "Cable Management Tray", "desk,office,accessory", "office"),
    ("sku_desk_mat", "Under-Desk Mat", "desk,office,ergonomic", "office"),
]

ACTIONS = ["view", "view", "view", "cart", "purchase"]


def seed() -> None:
    init_db()
    now = time.time()
    with get_session() as session:
        for item_id, title, tags, category in CATALOG:
            session.merge(Item(item_id=item_id, title=title, tags=tags, category=category))

        rng = random.Random(42)
        users = [f"user_{i}" for i in range(1, 41)]
        for user in users:
            n_events = rng.randint(2, 8)
            basket = rng.sample(CATALOG, k=min(n_events, len(CATALOG)))
            for i, (item_id, *_rest) in enumerate(basket):
                action = rng.choice(ACTIONS)
                ts = now - rng.randint(0, 20) * 3600
                session.add(Event(user_id=user, item_id=item_id, action=action, ts=ts))

    print(f"Seeded {len(CATALOG)} items and events for {len(users)} users.")


if __name__ == "__main__":
    seed()
