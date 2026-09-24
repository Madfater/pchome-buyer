"""對真實 PostgreSQL 跑 repository 的關鍵語意（單元測試用的是 in-memory SQLite）。

預設跳過；設定 PCHOME_TEST_DATABASE_URL（指向可丟棄的測試 DB，四張表會被清空）才會跑：
  PCHOME_TEST_DATABASE_URL=postgresql+psycopg://pchome:pchome@localhost:5432/pchome_test \
    uv run pytest tests/integration/test_repositories_postgres.py
"""

import os

import pytest
import sqlalchemy as sa

from pchome.infra.db import make_engine, metadata
from pchome.repositories import settings_repository as settings_repository_module
from pchome.repositories.auth_state_repository import AuthStateRepository
from pchome.repositories.checkout_repository import CheckoutRecordRepository
from pchome.repositories.product_repository import ProductRepository
from pchome.repositories.settings_repository import SettingsRepository

_URL = os.getenv("PCHOME_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not _URL, reason="PCHOME_TEST_DATABASE_URL 未設定")


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings_repository_module, "LEGACY_ENV_FILE", tmp_path / "does_not_exist.env"
    )
    assert _URL is not None
    eng = make_engine(_URL)
    with eng.begin() as conn:
        for table in reversed(metadata.sorted_tables):
            conn.execute(sa.delete(table))
    yield eng
    eng.dispose()


def test_products_order_semantics(engine):
    store = ProductRepository(engine=engine)
    store.add("A", "10:00", {"name": "甲"})
    store.add("B", "11:00")
    store.add("A", "12:00")
    assert store.update_sale_time("B", "13:00") is True
    assert store.list() == [
        {"id": "B", "sale_time": "13:00", "meta": {}},
        {"id": "A", "sale_time": "12:00", "meta": {}},
    ]
    store.remove("B")
    assert [p["id"] for p in ProductRepository(engine=engine).list()] == ["A"]


def test_checkouts_newest_first_update_and_clear(engine):
    store = CheckoutRecordRepository(engine=engine)
    kwargs = dict(
        sale_time="", status="awaiting_payment", cart_results=[], log_tail=["x"]
    )
    r1 = store.add(gid="g1", payinfo=None, **kwargs)
    store.add(gid="g2", payinfo={"amount": 1}, **kwargs)
    assert [r["gid"] for r in store.list()] == ["g2", "g1"]
    updated = store.update(r1["id"], completed=True)
    assert updated is not None and updated["completed"] is True
    assert store.update("missing", completed=True) is None
    assert store.clear_completed() == 1
    assert [r["gid"] for r in store.list()] == ["g2"]


def test_settings_seed_and_update(engine):
    store = SettingsRepository(engine=engine)
    assert store.get()["max_retries"] == 3
    store.update({"cvc": "123", "auto_pay": True})
    reopened = SettingsRepository(engine=engine).get()
    assert reopened["cvc"] == "123" and reopened["auto_pay"] is True


def test_auth_state_roundtrip(engine):
    store = AuthStateRepository(engine=engine)
    assert store.get() is None
    store.save({"cookies": [{"name": "a"}], "origins": []})
    store.save({"cookies": [{"name": "b"}], "origins": []})
    assert AuthStateRepository(engine=engine).get() == {
        "cookies": [{"name": "b"}],
        "origins": [],
    }
