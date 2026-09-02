from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shelf.core import mf_cache
from shelf.storage.models import Base


@pytest.fixture(autouse=True)
def _clear_mf_cache():
    mf_cache.clear()
    yield
    mf_cache.clear()


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()
