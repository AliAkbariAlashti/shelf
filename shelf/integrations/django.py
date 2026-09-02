"""Django integration: inherit from `ShelfTrackedModel` instead of
`models.Model` and every row created on that model logs a Shelf event
automatically, via `post_save`. No changes needed in your views, serializers,
or admin — the model itself is the single place that knows it's trackable.

    from shelf.integrations.django import ShelfTrackedModel

    class Purchase(ShelfTrackedModel):
        shelf_user_field = "user_id"
        shelf_item_field = "product_id"
        shelf_action = "purchase"

        user = models.ForeignKey(User, on_delete=models.CASCADE)
        product = models.ForeignKey(Product, on_delete=models.CASCADE)

By default this sends events over HTTP to `SHELF_URL` (falls back to
http://localhost:8000). Set `SHELF_DIRECT_DB = True` in Django settings to
write straight into Shelf's database instead — only correct when this app
and Shelf share the same `DATABASE_URL`.
"""

from __future__ import annotations

from shelf.integrations.sinks import DirectDBSink, EventSink, HTTPSink

try:
    from django.db import models
    from django.db.models.signals import class_prepared, post_save
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "shelf.integrations.django requires Django. Install it with "
        "`pip install shelf-recs[django]`."
    ) from exc

_sink: EventSink | None = None


def _get_sink() -> EventSink:
    global _sink
    if _sink is not None:
        return _sink

    from django.conf import settings

    if getattr(settings, "SHELF_DIRECT_DB", False):
        _sink = DirectDBSink()
    else:
        base_url = getattr(settings, "SHELF_URL", "http://localhost:8000")
        _sink = HTTPSink(base_url=base_url)
    return _sink


def reset_sink() -> None:
    """Drop the cached sink so the next tracked save re-reads settings.
    Mainly useful in tests that swap SHELF_DIRECT_DB / SHELF_URL."""
    global _sink
    _sink = None


class ShelfTrackedModel(models.Model):
    """Base class for any Django model whose rows represent a user/item
    interaction Shelf should learn from (a purchase, a view log, a rating).

    Subclasses must set:
      shelf_user_field: the field on this model holding the user id
      shelf_item_field: the field on this model holding the item id
      shelf_action:     the Shelf action name (e.g. "purchase", "view")

    Optionally:
      shelf_weight_field: a field holding a custom weight, instead of the
                           action's built-in default
    """

    shelf_user_field: str = ""
    shelf_item_field: str = ""
    shelf_action: str = "view"
    shelf_weight_field: str | None = None

    class Meta:
        abstract = True

    @classmethod
    def _shelf_field_names(cls) -> tuple[str, str]:
        if not cls.shelf_user_field or not cls.shelf_item_field:
            raise ValueError(
                f"{cls.__name__} must set shelf_user_field and shelf_item_field "
                "to use ShelfTrackedModel."
            )
        return cls.shelf_user_field, cls.shelf_item_field


def _connect_if_shelf_tracked(sender, **kwargs):
    # class_prepared fires once _meta is fully populated for `sender`, unlike
    # __init_subclass__ which runs before Django's metaclass has replaced the
    # inherited (abstract) _meta with the concrete model's own.
    if issubclass(sender, ShelfTrackedModel) and not sender._meta.abstract:
        post_save.connect(_track_on_save, sender=sender, weak=False)


class_prepared.connect(_connect_if_shelf_tracked)


def _track_on_save(sender, instance, created, **kwargs):
    if not created:
        return

    user_field, item_field = sender._shelf_field_names()
    user_id = getattr(instance, user_field, None)
    item_id = getattr(instance, item_field, None)
    if user_id is None or item_id is None:
        return

    weight = None
    if sender.shelf_weight_field:
        weight = getattr(instance, sender.shelf_weight_field, None)

    _get_sink().track(
        user=str(user_id),
        item=str(item_id),
        action=sender.shelf_action,
        weight=weight,
    )
