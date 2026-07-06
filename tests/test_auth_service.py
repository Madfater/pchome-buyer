import json

import mongomock
import pytest

from pchome.repositories.auth_state_repository import AuthStateRepository
from pchome.services import auth_service as auth_service_module
from pchome.services.auth_service import AuthService, _convert_extension_cookie


@pytest.fixture
def store():
    return AuthStateRepository(db=mongomock.MongoClient()["test"])


@pytest.fixture
def svc(store):
    return AuthService(store)


class TestConvertExtensionCookie:
    def test_maps_samesite_values(self):
        base = {"name": "n", "value": "v", "domain": "d", "expirationDate": 1.0}
        assert (
            _convert_extension_cookie({**base, "sameSite": "no_restriction"})[
                "sameSite"
            ]
            == "None"
        )
        assert (
            _convert_extension_cookie({**base, "sameSite": "lax"})["sameSite"] == "Lax"
        )
        assert (
            _convert_extension_cookie({**base, "sameSite": "strict"})["sameSite"]
            == "Strict"
        )
        assert (
            _convert_extension_cookie({**base, "sameSite": "unknown"})["sameSite"]
            == "Lax"
        )

    def test_expiration_date_converted_to_expires(self):
        c = _convert_extension_cookie(
            {"name": "n", "value": "v", "domain": "d", "expirationDate": 1234.5}
        )
        assert c["expires"] == 1234.5
        assert "expirationDate" not in c

    def test_session_cookie_gets_expires_minus_one(self):
        c = _convert_extension_cookie(
            {"name": "n", "value": "v", "domain": "d", "session": True}
        )
        assert c["expires"] == -1

    def test_missing_expiration_date_gets_expires_minus_one(self):
        c = _convert_extension_cookie({"name": "n", "value": "v", "domain": "d"})
        assert c["expires"] == -1

    def test_drops_extension_only_fields(self):
        c = _convert_extension_cookie(
            {
                "name": "n",
                "value": "v",
                "domain": "d",
                "expirationDate": 1.0,
                "storeId": "0",
                "hostOnly": True,
                "session": False,
                "id": 42,
            }
        )
        for field in ("storeId", "hostOnly", "session", "id"):
            assert field not in c

    def test_defaults_path_httponly_secure(self):
        c = _convert_extension_cookie(
            {"name": "n", "value": "v", "domain": "d", "expirationDate": 1.0}
        )
        assert c["path"] == "/"
        assert c["httpOnly"] is False
        assert c["secure"] is False


class TestImportAuth:
    def test_invalid_json_returns_error(self, store, svc):
        result = svc.import_auth("not json")
        assert result.ok is False
        assert "JSON" in result.error
        assert store.get() is None

    def test_unrecognized_format_returns_error(self, svc):
        result = svc.import_auth(json.dumps({"foo": "bar"}))
        assert result.ok is False
        assert "無法辨識格式" in result.error

    def test_storage_state_format_written_as_is(self, store, svc):
        payload = {
            "cookies": [{"name": "a", "value": "1", "domain": "pchome.com.tw"}],
            "origins": [],
        }
        result = svc.import_auth(json.dumps(payload))
        assert result.ok is True
        assert result.format == "storage_state"
        assert result.cookie_count == 1
        assert result.pchome_cookie_count == 1
        assert result.warning == ""
        assert store.get()["cookies"] == payload["cookies"]

    def test_cookie_array_format_converted(self, store, svc):
        payload = [
            {
                "name": "a",
                "value": "1",
                "domain": "24h.pchome.com.tw",
                "expirationDate": 999.0,
                "sameSite": "lax",
            }
        ]
        result = svc.import_auth(json.dumps(payload))
        assert result.ok is True
        assert result.format == "cookie_array"
        assert result.pchome_cookie_count == 1
        written = store.get()
        assert written["cookies"][0]["sameSite"] == "Lax"
        assert written["cookies"][0]["expires"] == 999.0

    def test_no_pchome_cookies_warns(self, svc):
        payload = {
            "cookies": [{"name": "a", "value": "1", "domain": "example.com"}],
            "origins": [],
        }
        result = svc.import_auth(json.dumps(payload))
        assert result.ok is True
        assert result.pchome_cookie_count == 0
        assert "警告" in result.warning

    def test_malformed_cookie_array_returns_error(self, svc):
        result = svc.import_auth(json.dumps([{"no_name": True}]))
        assert result.ok is False
        assert "cookie 陣列格式錯誤" in result.error


class TestStatus:
    def test_status_without_live_uses_cached_state(self, store, svc):
        store.save({"cookies": [], "origins": []})
        result = svc.status(live=False)
        assert result == {
            "has_auth_state": True,
            "session_valid": None,
            "checked_at": None,
        }

    def test_status_live_checks_when_no_auth_state_skips_check(self, monkeypatch, svc):
        calls = []
        monkeypatch.setattr(
            auth_service_module.session,
            "check_session_standalone",
            lambda state: calls.append(1) or True,
        )
        svc.status(live=True)
        assert calls == []

    def test_status_live_checks_once_then_debounces(self, monkeypatch, store, svc):
        store.save({"cookies": [], "origins": []})
        calls = []
        monkeypatch.setattr(
            auth_service_module.session,
            "check_session_standalone",
            lambda state: calls.append(1) or True,
        )
        first = svc.status(live=True)
        second = svc.status(live=True)
        assert calls == [1]
        assert first["session_valid"] is True
        assert second["session_valid"] is True
        assert second["checked_at"] == first["checked_at"]
