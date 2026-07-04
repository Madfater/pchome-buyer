import json

import pytest

from pchome.services import auth_service as auth_service_module
from pchome.services.auth_service import AuthService, _convert_extension_cookie


@pytest.fixture(autouse=True)
def isolated_auth_state_file(tmp_path, monkeypatch):
    """絕不可讓測試寫到真實 auth_state.json（見 CLAUDE.md 致命不變量 #7）"""
    fake_path = tmp_path / "auth_state.json"
    monkeypatch.setattr(auth_service_module, "AUTH_STATE_FILE", fake_path)
    return fake_path


class TestConvertExtensionCookie:
    def test_maps_samesite_values(self):
        base = {"name": "n", "value": "v", "domain": "d", "expirationDate": 1.0}
        assert _convert_extension_cookie({**base, "sameSite": "no_restriction"})[
            "sameSite"
        ] == "None"
        assert _convert_extension_cookie({**base, "sameSite": "lax"})["sameSite"] == "Lax"
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
    def test_invalid_json_returns_error(self, isolated_auth_state_file):
        result = AuthService().import_auth("not json")
        assert result.ok is False
        assert "JSON" in result.error
        assert not isolated_auth_state_file.exists()

    def test_unrecognized_format_returns_error(self, isolated_auth_state_file):
        result = AuthService().import_auth(json.dumps({"foo": "bar"}))
        assert result.ok is False
        assert "無法辨識格式" in result.error

    def test_storage_state_format_written_as_is(self, isolated_auth_state_file):
        payload = {
            "cookies": [{"name": "a", "value": "1", "domain": "pchome.com.tw"}],
            "origins": [],
        }
        result = AuthService().import_auth(json.dumps(payload))
        assert result.ok is True
        assert result.format == "storage_state"
        assert result.cookie_count == 1
        assert result.pchome_cookie_count == 1
        assert result.warning == ""
        written = json.loads(isolated_auth_state_file.read_text())
        assert written["cookies"] == payload["cookies"]

    def test_cookie_array_format_converted(self, isolated_auth_state_file):
        payload = [
            {
                "name": "a",
                "value": "1",
                "domain": "24h.pchome.com.tw",
                "expirationDate": 999.0,
                "sameSite": "lax",
            }
        ]
        result = AuthService().import_auth(json.dumps(payload))
        assert result.ok is True
        assert result.format == "cookie_array"
        assert result.pchome_cookie_count == 1
        written = json.loads(isolated_auth_state_file.read_text())
        assert written["cookies"][0]["sameSite"] == "Lax"
        assert written["cookies"][0]["expires"] == 999.0

    def test_no_pchome_cookies_warns(self, isolated_auth_state_file):
        payload = {
            "cookies": [{"name": "a", "value": "1", "domain": "example.com"}],
            "origins": [],
        }
        result = AuthService().import_auth(json.dumps(payload))
        assert result.ok is True
        assert result.pchome_cookie_count == 0
        assert "警告" in result.warning

    def test_malformed_cookie_array_returns_error(self, isolated_auth_state_file):
        result = AuthService().import_auth(json.dumps([{"no_name": True}]))
        assert result.ok is False
        assert "cookie 陣列格式錯誤" in result.error


class TestStatus:
    def test_status_without_live_uses_cached_state(self, monkeypatch):
        monkeypatch.setattr(auth_service_module.session, "has_auth_state", lambda: True)
        svc = AuthService()
        result = svc.status(live=False)
        assert result == {
            "has_auth_state": True,
            "session_valid": None,
            "checked_at": None,
        }

    def test_status_live_checks_when_no_auth_state_skips_check(self, monkeypatch):
        monkeypatch.setattr(
            auth_service_module.session, "has_auth_state", lambda: False
        )
        calls = []
        monkeypatch.setattr(
            auth_service_module.session,
            "check_session_standalone",
            lambda: calls.append(1) or True,
        )
        AuthService().status(live=True)
        assert calls == []

    def test_status_live_checks_once_then_debounces(self, monkeypatch):
        monkeypatch.setattr(auth_service_module.session, "has_auth_state", lambda: True)
        calls = []
        monkeypatch.setattr(
            auth_service_module.session,
            "check_session_standalone",
            lambda: calls.append(1) or True,
        )
        svc = AuthService()
        first = svc.status(live=True)
        second = svc.status(live=True)
        assert calls == [1]
        assert first["session_valid"] is True
        assert second["session_valid"] is True
        assert second["checked_at"] == first["checked_at"]
