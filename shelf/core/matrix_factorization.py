"""Implicit-feedback matrix factorization via Alternating Least Squares.

A from-scratch NumPy implementation of the Hu/Koren/Volinsky (2008) implicit
ALS algorithm, so Shelf's high-volume strategy doesn't require a compiled
dependency (`implicit`) just to ship a default. Swap this module out for a
faster backend later without touching the engine's selection logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Confidence scaling: confidence = 1 + ALPHA * interaction_weight.
# Higher alpha trusts strong interactions (purchases) more relative to weak
# ones (views) when fitting latent factors.
ALPHA = 20.0
N_FACTORS = 24
N_ITERATIONS = 12
REGULARIZATION = 0.1


@dataclass
class ALSModel:
    user_index: dict[str, int]
    item_index: dict[str, int]
    item_ids: list[str] = field(repr=False)
    user_factors: np.ndarray = field(repr=False)
    item_factors: np.ndarray = field(repr=False)

    def recommend(
        self, user_id: str, exclude: set[str], limit: int
    ) -> list[tuple[str, float]]:
        uidx = self.user_index.get(user_id)
        if uidx is None:
            return []
        scores = self.item_factors @ self.user_factors[uidx]
        ranked_idx = np.argsort(-scores)

        results: list[tuple[str, float]] = []
        for idx in ranked_idx:
            item_id = self.item_ids[idx]
            if item_id in exclude:
                continue
            results.append((item_id, float(scores[idx])))
            if len(results) >= limit:
                break
        return results

    def nearest_item(self, item_id: str, exclude: set[str]) -> str | None:
        """Item whose latent factors are closest to `item_id` — used to give
        an implicit-factor recommendation a concrete, human-readable anchor."""
        idx = self.item_index.get(item_id)
        if idx is None:
            return None
        vec = self.item_factors[idx]
        sims = self.item_factors @ vec
        for candidate_idx in np.argsort(-sims):
            candidate_id = self.item_ids[candidate_idx]
            if candidate_id != item_id and candidate_id not in exclude:
                return candidate_id
        return None


def fit_als(
    interactions: dict[tuple[str, str], float],
    n_factors: int = N_FACTORS,
    n_iterations: int = N_ITERATIONS,
    regularization: float = REGULARIZATION,
    alpha: float = ALPHA,
    seed: int = 0,
) -> ALSModel | None:
    """Fit implicit ALS on a sparse (user_id, item_id) -> weight mapping.

    Returns None if there isn't enough data to fit anything meaningful
    (fewer than 2 users or 2 items) — callers should fall back to another
    strategy in that case.
    """
    users = sorted({u for u, _ in interactions})
    items = sorted({i for _, i in interactions})
    if len(users) < 2 or len(items) < 2:
        return None

    user_index = {u: i for i, u in enumerate(users)}
    item_index = {i: idx for idx, i in enumerate(items)}

    n_users, n_items = len(users), len(items)
    confidence = np.ones((n_users, n_items), dtype=np.float64)
    preference = np.zeros((n_users, n_items), dtype=np.float64)

    for (u, i), weight in interactions.items():
        ui, ii = user_index[u], item_index[i]
        confidence[ui, ii] += alpha * max(weight, 0.0)
        preference[ui, ii] = 1.0

    rng = np.random.default_rng(seed)
    user_factors = rng.normal(scale=0.01, size=(n_users, n_factors))
    item_factors = rng.normal(scale=0.01, size=(n_items, n_factors))
    reg_matrix = regularization * np.eye(n_factors)

    for _ in range(n_iterations):
        item_gram = item_factors.T @ item_factors
        for u in range(n_users):
            c_u = confidence[u]
            weighted_items = item_factors * (c_u[:, None])
            a = item_gram + item_factors.T @ ((c_u - 1)[:, None] * item_factors) + reg_matrix
            b = weighted_items.T @ preference[u]
            user_factors[u] = np.linalg.solve(a, b)

        user_gram = user_factors.T @ user_factors
        for i in range(n_items):
            c_i = confidence[:, i]
            weighted_users = user_factors * (c_i[:, None])
            a = user_gram + user_factors.T @ ((c_i - 1)[:, None] * user_factors) + reg_matrix
            b = weighted_users.T @ preference[:, i]
            item_factors[i] = np.linalg.solve(a, b)

    return ALSModel(
        user_index=user_index,
        item_index=item_index,
        item_ids=items,
        user_factors=user_factors,
        item_factors=item_factors,
    )
