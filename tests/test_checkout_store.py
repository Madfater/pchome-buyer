from pchome.services.checkout_store import CheckoutRecordStore


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


def test_starts_empty_when_file_missing(tmp_path):
    store = CheckoutRecordStore(tmp_path / "checkouts.json")
    assert store.list() == []


def test_add_inserts_newest_first(tmp_path):
    store = CheckoutRecordStore(tmp_path / "checkouts.json")
    first = _add(store, gid="g1")
    second = _add(store, gid="g2")
    assert [r["gid"] for r in store.list()] == ["g2", "g1"]
    assert first["completed"] is False
    assert second["id"] != first["id"]


def test_add_persists_to_disk(tmp_path):
    path = tmp_path / "checkouts.json"
    store = CheckoutRecordStore(path)
    _add(store, gid="g1")
    reloaded = CheckoutRecordStore(path)
    assert [r["gid"] for r in reloaded.list()] == ["g1"]


def test_update_existing_record(tmp_path):
    store = CheckoutRecordStore(tmp_path / "checkouts.json")
    record = _add(store)
    updated = store.update(record["id"], completed=True, status="success")
    assert updated is not None
    assert updated["completed"] is True
    assert updated["status"] == "success"
    assert store.list()[0]["completed"] is True


def test_update_missing_id_returns_none(tmp_path):
    store = CheckoutRecordStore(tmp_path / "checkouts.json")
    assert store.update("missing-id", completed=True) is None


def test_clear_completed_removes_only_completed_and_returns_count(tmp_path):
    store = CheckoutRecordStore(tmp_path / "checkouts.json")
    r1 = _add(store, gid="g1")
    _add(store, gid="g2")
    store.update(r1["id"], completed=True)

    removed = store.clear_completed()

    assert removed == 1
    remaining = store.list()
    assert len(remaining) == 1
    assert remaining[0]["gid"] == "g2"


def test_list_returns_copies_not_live_references(tmp_path):
    store = CheckoutRecordStore(tmp_path / "checkouts.json")
    _add(store, gid="g1")
    snapshot = store.list()
    snapshot[0]["gid"] = "mutated"
    assert store.list()[0]["gid"] == "g1"
