import json

from pchome.services import auth_service as auth_service_module


def test_import_valid_storage_state(client):
    payload = {
        "cookies": [{"name": "a", "value": "1", "domain": "pchome.com.tw"}],
        "origins": [],
    }
    resp = client.post("/api/auth/import", json={"payload": json.dumps(payload)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["format"] == "storage_state"
    assert body["pchome_cookie_count"] == 1


def test_import_invalid_json_returns_400(client):
    resp = client.post("/api/auth/import", json={"payload": "not json"})
    assert resp.status_code == 400
    assert "JSON" in resp.json()["detail"]


def test_status_without_live_reports_no_auth_state_initially(client):
    resp = client.get("/api/auth/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_auth_state"] is False
    assert body["session_valid"] is None


def test_status_reflects_auth_state_after_import(client):
    payload = {
        "cookies": [{"name": "a", "value": "1", "domain": "pchome.com.tw"}],
        "origins": [],
    }
    client.post("/api/auth/import", json={"payload": json.dumps(payload)})

    resp = client.get("/api/auth/status")

    assert resp.json()["has_auth_state"] is True


def test_status_live_without_auth_state_skips_real_browser_check(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        auth_service_module.session,
        "check_session_standalone",
        lambda state: calls.append(1) or True,
    )
    resp = client.get("/api/auth/status", params={"live": "true"})
    assert resp.status_code == 200
    assert calls == []  # 沒有 auth state 時不該打真實瀏覽器檢查


def test_status_live_with_auth_state_uses_mocked_check(client, monkeypatch):
    payload = {
        "cookies": [{"name": "a", "value": "1", "domain": "pchome.com.tw"}],
        "origins": [],
    }
    client.post("/api/auth/import", json={"payload": json.dumps(payload)})

    monkeypatch.setattr(
        auth_service_module.session, "check_session_standalone", lambda state: True
    )
    resp = client.get("/api/auth/status", params={"live": "true"})

    assert resp.status_code == 200
    assert resp.json()["session_valid"] is True
