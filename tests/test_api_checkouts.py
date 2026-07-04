def _seed_record(container, **overrides):
    kwargs = dict(
        gid="now#1",
        sale_time="",
        status="awaiting_payment",
        cart_results=[],
        payinfo=None,
        log_tail=[],
    )
    kwargs.update(overrides)
    return container.checkout_store.add(**kwargs)


def test_complete_checkout_marks_completed(client, container):
    record = _seed_record(container)

    resp = client.post(f"/api/checkouts/{record['id']}/complete")

    assert resp.status_code == 200
    checkouts = resp.json()["checkouts"]
    assert checkouts[0]["completed"] is True


def test_complete_checkout_publishes_event(client, container):
    record = _seed_record(container)
    q = container.bus.subscribe()

    client.post(f"/api/checkouts/{record['id']}/complete")

    event = q.get_nowait()
    assert event["type"] == "checkout"
    assert event["record"]["id"] == record["id"]


def test_complete_unknown_record_returns_404(client):
    resp = client.post("/api/checkouts/GHOST/complete")
    assert resp.status_code == 404


def test_clear_completed_removes_only_completed(client, container):
    r1 = _seed_record(container, gid="g1")
    _seed_record(container, gid="g2")
    container.checkout_store.update(r1["id"], completed=True)

    resp = client.delete("/api/checkouts/completed")

    assert resp.status_code == 200
    gids = [r["gid"] for r in resp.json()["checkouts"]]
    assert gids == ["g2"]
