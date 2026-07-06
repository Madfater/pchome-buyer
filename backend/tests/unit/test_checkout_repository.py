import mongomock

from pchome.repositories import checkout_repository as checkout_repository_module
from pchome.repositories.checkout_repository import CheckoutRecordRepository


def _db():
    return mongomock.MongoClient()["test"]


def _add(store, **overrides):
    kwargs = dict(
        gid="now#1",
        sale_time="",
        status="awaiting_payment",
        cart_results=[],
        payinfo=None,
        log_tail=[],
    )
    kwargs.update(overrides)
    return store.add(**kwargs)


def test_starts_empty_when_collection_missing():
    store = CheckoutRecordRepository(db=_db())
    assert store.list() == []


def test_add_inserts_newest_first():
    store = CheckoutRecordRepository(db=_db())
    first = _add(store, gid="g1")
    second = _add(store, gid="g2")
    assert [r["gid"] for r in store.list()] == ["g2", "g1"]
    assert first["completed"] is False
    assert second["id"] != first["id"]


def test_add_persists_across_reinstantiation():
    db = _db()
    store = CheckoutRecordRepository(db=db)
    _add(store, gid="g1")
    reloaded = CheckoutRecordRepository(db=db)
    assert [r["gid"] for r in reloaded.list()] == ["g1"]


def test_update_existing_record():
    store = CheckoutRecordRepository(db=_db())
    record = _add(store)
    updated = store.update(record["id"], completed=True, status="success")
    assert updated is not None
    assert updated["completed"] is True
    assert updated["status"] == "success"
    assert store.list()[0]["completed"] is True


def test_update_missing_id_returns_none():
    store = CheckoutRecordRepository(db=_db())
    assert store.update("missing-id", completed=True) is None


def test_clear_completed_removes_only_completed_and_returns_count():
    store = CheckoutRecordRepository(db=_db())
    r1 = _add(store, gid="g1")
    _add(store, gid="g2")
    store.update(r1["id"], completed=True)

    removed = store.clear_completed()

    assert removed == 1
    remaining = store.list()
    assert len(remaining) == 1
    assert remaining[0]["gid"] == "g2"


def test_list_returns_copies_not_live_references():
    store = CheckoutRecordRepository(db=_db())
    _add(store, gid="g1")
    snapshot = store.list()
    snapshot[0]["gid"] = "mutated"
    assert store.list()[0]["gid"] == "g1"


class TestLegacyMigration:
    def test_migrates_from_legacy_json_preserving_newest_first_order(
        self, tmp_path, monkeypatch
    ):
        legacy_file = tmp_path / "checkouts.json"
        legacy_file.write_text(
            '[{"id": "new", "created_at": "2026-01-02T00:00:00", "gid": "g2", '
            '"sale_time": "", "status": "awaiting_payment", "completed": false, '
            '"cart_results": [], "payinfo": null, "log_tail": []}, '
            '{"id": "old", "created_at": "2026-01-01T00:00:00", "gid": "g1", '
            '"sale_time": "", "status": "awaiting_payment", "completed": false, '
            '"cart_results": [], "payinfo": null, "log_tail": []}]'
        )
        monkeypatch.setattr(
            checkout_repository_module, "LEGACY_CHECKOUTS_FILE", legacy_file
        )

        store = CheckoutRecordRepository(db=_db())

        assert [r["gid"] for r in store.list()] == ["g2", "g1"]

    def test_does_not_migrate_when_legacy_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            checkout_repository_module,
            "LEGACY_CHECKOUTS_FILE",
            tmp_path / "does_not_exist.json",
        )
        store = CheckoutRecordRepository(db=_db())
        assert store.list() == []

    def test_does_not_remigrate_once_collection_has_data(self, tmp_path, monkeypatch):
        from bson import ObjectId

        legacy_file = tmp_path / "checkouts.json"
        legacy_file.write_text(
            '[{"id": "stale", "created_at": "2026-01-01T00:00:00", "gid": "gstale", '
            '"sale_time": "", "status": "awaiting_payment", "completed": false, '
            '"cart_results": [], "payinfo": null, "log_tail": []}]'
        )
        monkeypatch.setattr(
            checkout_repository_module, "LEGACY_CHECKOUTS_FILE", legacy_file
        )

        db = _db()
        db["checkouts"].insert_one(
            {
                "_id": "existing",
                "_order": ObjectId(),
                "id": "existing",
                "created_at": "2026-02-01T00:00:00",
                "gid": "existing",
                "sale_time": "",
                "status": "awaiting_payment",
                "completed": False,
                "cart_results": [],
                "payinfo": None,
                "log_tail": [],
            }
        )

        store = CheckoutRecordRepository(db=db)
        assert [r["gid"] for r in store.list()] == ["existing"]
