def test_get_settings_returns_defaults(client):
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cvc"] == ""
    assert body["auto_pay"] is False
    assert body["default_interval_secs"] == 0.5
    assert body["max_retries"] == 3


def test_patch_settings_updates_and_persists(client):
    resp = client.patch("/api/settings", json={"cvc": "789", "auto_pay": True})
    assert resp.status_code == 200
    assert resp.json()["cvc"] == "789"
    assert resp.json()["auto_pay"] is True

    resp2 = client.get("/api/settings")
    assert resp2.json()["cvc"] == "789"
    assert resp2.json()["auto_pay"] is True


def test_patch_only_sends_changed_fields(client):
    client.patch("/api/settings", json={"cvc": "111"})
    resp = client.patch("/api/settings", json={"max_retries": 7})
    body = resp.json()
    assert body["cvc"] == "111"
    assert body["max_retries"] == 7


def test_patch_out_of_bounds_value_returns_400(client):
    resp = client.patch("/api/settings", json={"max_retries": 999})
    assert resp.status_code == 400
