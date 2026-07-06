import mongomock
from bson import ObjectId

from pchome.repositories import product_repository as product_repository_module
from pchome.repositories.product_repository import ProductRepository


def _db():
    return mongomock.MongoClient()["test"]


def test_starts_empty_when_collection_missing():
    store = ProductRepository(db=_db())
    assert store.list() == []


def test_add_appends_and_persists():
    db = _db()
    store = ProductRepository(db=db)
    store.add("A", "2026-03-06 12:00")
    assert store.list() == [{"id": "A", "sale_time": "2026-03-06 12:00", "meta": {}}]

    reloaded = ProductRepository(db=db)
    assert reloaded.list() == [{"id": "A", "sale_time": "2026-03-06 12:00", "meta": {}}]


def test_add_defaults_sale_time_to_empty_string():
    store = ProductRepository(db=_db())
    store.add("A")
    assert store.list() == [{"id": "A", "sale_time": "", "meta": {}}]


def test_add_duplicate_id_overwrites_sale_time_and_moves_to_end():
    store = ProductRepository(db=_db())
    store.add("A", "10:00")
    store.add("B", "11:00")
    store.add("A", "12:00")
    assert store.list() == [
        {"id": "B", "sale_time": "11:00", "meta": {}},
        {"id": "A", "sale_time": "12:00", "meta": {}},
    ]


def test_update_sale_time_preserves_order():
    store = ProductRepository(db=_db())
    store.add("A", "10:00")
    store.add("B", "11:00")
    assert store.update_sale_time("A", "20:00") is True
    assert store.list() == [
        {"id": "A", "sale_time": "20:00", "meta": {}},
        {"id": "B", "sale_time": "11:00", "meta": {}},
    ]


def test_update_sale_time_missing_id_returns_false():
    store = ProductRepository(db=_db())
    assert store.update_sale_time("MISSING", "20:00") is False


def test_remove_drops_item():
    store = ProductRepository(db=_db())
    store.add("A")
    store.add("B")
    store.remove("A")
    assert store.list() == [{"id": "B", "sale_time": "", "meta": {}}]


def test_list_returns_copies_not_live_references():
    store = ProductRepository(db=_db())
    store.add("A", "10:00")
    snapshot = store.list()
    snapshot[0]["sale_time"] = "mutated"
    assert store.list()[0]["sale_time"] == "10:00"


def test_add_with_meta_persists_it():
    db = _db()
    store = ProductRepository(db=db)
    store.add("A", "10:00", {"name": "測試商品", "price": 100})
    assert store.list() == [
        {"id": "A", "sale_time": "10:00", "meta": {"name": "測試商品", "price": 100}}
    ]
    reloaded = ProductRepository(db=db)
    assert reloaded.list()[0]["meta"] == {"name": "測試商品", "price": 100}


def test_add_without_meta_defaults_to_empty_dict():
    store = ProductRepository(db=_db())
    store.add("A")
    assert store.list() == [{"id": "A", "sale_time": "", "meta": {}}]


def test_list_tolerates_legacy_items_without_meta_key():
    db = _db()
    db["products"].insert_one({"_id": "A", "sale_time": "", "_order": ObjectId()})
    store = ProductRepository(db=db)
    assert store.list() == [{"id": "A", "sale_time": ""}]


class TestLegacyMigration:
    def test_migrates_from_legacy_json_on_first_use(self, tmp_path, monkeypatch):
        legacy_file = tmp_path / "products.json"
        legacy_file.write_text(
            '[{"id": "A", "sale_time": "10:00", "meta": {}}, '
            '{"id": "B", "sale_time": "11:00", "meta": {}}]'
        )
        monkeypatch.setattr(
            product_repository_module, "LEGACY_PRODUCTS_FILE", legacy_file
        )

        store = ProductRepository(db=_db())

        assert store.list() == [
            {"id": "A", "sale_time": "10:00", "meta": {}},
            {"id": "B", "sale_time": "11:00", "meta": {}},
        ]

    def test_does_not_migrate_when_legacy_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            product_repository_module,
            "LEGACY_PRODUCTS_FILE",
            tmp_path / "does_not_exist.json",
        )
        store = ProductRepository(db=_db())
        assert store.list() == []

    def test_does_not_remigrate_once_collection_has_data(self, tmp_path, monkeypatch):
        legacy_file = tmp_path / "products.json"
        legacy_file.write_text('[{"id": "STALE", "sale_time": "", "meta": {}}]')
        monkeypatch.setattr(
            product_repository_module, "LEGACY_PRODUCTS_FILE", legacy_file
        )

        db = _db()
        db["products"].insert_one(
            {"_id": "EXISTING", "sale_time": "", "meta": {}, "_order": ObjectId()}
        )

        store = ProductRepository(db=db)
        assert [item["id"] for item in store.list()] == ["EXISTING"]
