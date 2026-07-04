from pchome.services.product_store import ProductStore


def test_starts_empty_when_file_missing(tmp_path):
    store = ProductStore(tmp_path / "products.json")
    assert store.list() == []


def test_add_appends_and_persists(tmp_path):
    path = tmp_path / "products.json"
    store = ProductStore(path)
    store.add("A", "2026-03-06 12:00")
    assert store.list() == [{"id": "A", "sale_time": "2026-03-06 12:00", "meta": {}}]

    reloaded = ProductStore(path)
    assert reloaded.list() == [{"id": "A", "sale_time": "2026-03-06 12:00", "meta": {}}]


def test_add_defaults_sale_time_to_empty_string(tmp_path):
    store = ProductStore(tmp_path / "products.json")
    store.add("A")
    assert store.list() == [{"id": "A", "sale_time": "", "meta": {}}]


def test_add_duplicate_id_overwrites_sale_time_and_moves_to_end(tmp_path):
    store = ProductStore(tmp_path / "products.json")
    store.add("A", "10:00")
    store.add("B", "11:00")
    store.add("A", "12:00")
    assert store.list() == [
        {"id": "B", "sale_time": "11:00", "meta": {}},
        {"id": "A", "sale_time": "12:00", "meta": {}},
    ]


def test_update_sale_time_preserves_order(tmp_path):
    store = ProductStore(tmp_path / "products.json")
    store.add("A", "10:00")
    store.add("B", "11:00")
    assert store.update_sale_time("A", "20:00") is True
    assert store.list() == [
        {"id": "A", "sale_time": "20:00", "meta": {}},
        {"id": "B", "sale_time": "11:00", "meta": {}},
    ]


def test_update_sale_time_missing_id_returns_false(tmp_path):
    store = ProductStore(tmp_path / "products.json")
    assert store.update_sale_time("MISSING", "20:00") is False


def test_remove_drops_item(tmp_path):
    store = ProductStore(tmp_path / "products.json")
    store.add("A")
    store.add("B")
    store.remove("A")
    assert store.list() == [{"id": "B", "sale_time": "", "meta": {}}]


def test_list_returns_copies_not_live_references(tmp_path):
    store = ProductStore(tmp_path / "products.json")
    store.add("A", "10:00")
    snapshot = store.list()
    snapshot[0]["sale_time"] = "mutated"
    assert store.list()[0]["sale_time"] == "10:00"


def test_add_with_meta_persists_it(tmp_path):
    path = tmp_path / "products.json"
    store = ProductStore(path)
    store.add("A", "10:00", {"name": "測試商品", "price": 100})
    assert store.list() == [
        {"id": "A", "sale_time": "10:00", "meta": {"name": "測試商品", "price": 100}}
    ]
    reloaded = ProductStore(path)
    assert reloaded.list()[0]["meta"] == {"name": "測試商品", "price": 100}


def test_add_without_meta_defaults_to_empty_dict(tmp_path):
    store = ProductStore(tmp_path / "products.json")
    store.add("A")
    assert store.list() == [{"id": "A", "sale_time": "", "meta": {}}]


def test_list_tolerates_legacy_items_without_meta_key(tmp_path):
    path = tmp_path / "products.json"
    path.write_text('[{"id": "A", "sale_time": ""}]')
    store = ProductStore(path)
    assert store.list() == [{"id": "A", "sale_time": ""}]
