from __future__ import annotations

import django
import pytest
from django.conf import settings

if not settings.configured:
    settings.configure(
        INSTALLED_APPS=["django.contrib.contenttypes", "django.contrib.auth", "tests"],
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        USE_TZ=True,
    )
    django.setup()

from django.db import connection, models

from shelf.integrations import django as shelf_django


class Purchase(shelf_django.ShelfTrackedModel):
    shelf_user_field = "user_id"
    shelf_item_field = "product_id"
    shelf_action = "purchase"

    user_id = models.CharField(max_length=64)
    product_id = models.CharField(max_length=64)

    class Meta:
        app_label = "tests"


class RatedReview(shelf_django.ShelfTrackedModel):
    shelf_user_field = "user_id"
    shelf_item_field = "product_id"
    shelf_action = "rate"
    shelf_weight_field = "stars"

    user_id = models.CharField(max_length=64)
    product_id = models.CharField(max_length=64)
    stars = models.FloatField()

    class Meta:
        app_label = "tests"


@pytest.fixture(scope="module", autouse=True)
def _django_db():
    with connection.schema_editor() as editor:
        editor.create_model(Purchase)
        editor.create_model(RatedReview)
    yield


@pytest.fixture(autouse=True)
def _reset_sink(monkeypatch):
    shelf_django.reset_sink()
    monkeypatch.delenv("SHELF_DIRECT_DB", raising=False)
    yield
    shelf_django.reset_sink()


class _FakeSink:
    def __init__(self):
        self.events = []

    def track(self, user, item, action, weight=None, ts=None):
        self.events.append(
            {"user": user, "item": item, "action": action, "weight": weight}
        )


def test_creating_a_tracked_row_fires_an_event(monkeypatch):
    fake_sink = _FakeSink()
    monkeypatch.setattr(shelf_django, "_get_sink", lambda: fake_sink)

    Purchase.objects.create(user_id="u1", product_id="sku_1")

    assert fake_sink.events == [
        {"user": "u1", "item": "sku_1", "action": "purchase", "weight": None}
    ]


def test_updating_an_existing_row_does_not_refire(monkeypatch):
    fake_sink = _FakeSink()
    monkeypatch.setattr(shelf_django, "_get_sink", lambda: fake_sink)

    purchase = Purchase.objects.create(user_id="u1", product_id="sku_1")
    fake_sink.events.clear()

    purchase.product_id = "sku_2"
    purchase.save()

    assert fake_sink.events == []


def test_custom_weight_field_is_passed_through(monkeypatch):
    fake_sink = _FakeSink()
    monkeypatch.setattr(shelf_django, "_get_sink", lambda: fake_sink)

    RatedReview.objects.create(user_id="u1", product_id="sku_1", stars=4.5)

    assert fake_sink.events == [
        {"user": "u1", "item": "sku_1", "action": "rate", "weight": 4.5}
    ]


def test_get_sink_defaults_to_http():
    from shelf.integrations.sinks import HTTPSink

    sink = shelf_django._get_sink()
    assert isinstance(sink, HTTPSink)


def test_get_sink_respects_direct_db_setting(monkeypatch, tmp_path):
    from shelf.integrations.sinks import DirectDBSink

    monkeypatch.setattr(settings, "SHELF_DIRECT_DB", True, raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/shelf-django-test.db")

    sink = shelf_django._get_sink()
    assert isinstance(sink, DirectDBSink)
