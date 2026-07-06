"""登入狀態管理：匯入 cookie / storage_state、檢查 session 有效性

遠端部署時無法在伺服器上開有頭瀏覽器登入，改為在本機登入後把
Playwright storage_state（瀏覽器 devtools 匯出）或瀏覽器擴充功能
（Cookie-Editor / EditThisCookie）匯出的 cookie 陣列貼到控制台匯入，
存進 AuthStateRepository（MongoDB）。
"""

import json
import threading
import time
from dataclasses import dataclass

from ..core import session
from ..repositories.auth_state_repository import AuthStateRepository

# 擴充功能匯出的 sameSite 值 → Playwright 接受的值
_SAMESITE_MAP = {
    "no_restriction": "None",
    "none": "None",
    "lax": "Lax",
    "strict": "Strict",
}
# 擴充功能特有、Playwright 不認得的欄位
_DROP_FIELDS = {"storeId", "hostOnly", "session", "id"}

_LIVE_CHECK_DEBOUNCE_SECS = 30


@dataclass
class ImportResult:
    ok: bool
    format: str = ""  # storage_state / cookie_array
    cookie_count: int = 0
    pchome_cookie_count: int = 0
    warning: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "format": self.format,
            "cookie_count": self.cookie_count,
            "pchome_cookie_count": self.pchome_cookie_count,
            "warning": self.warning,
            "error": self.error,
        }


class AuthService:
    def __init__(self, store: AuthStateRepository | None = None):
        self._store = store if store is not None else AuthStateRepository()
        self._lock = threading.Lock()
        self._last_check_ts: float = 0.0
        self._last_check_result: bool | None = None

    # ---- 匯入 ----

    def import_auth(self, payload: str) -> ImportResult:
        """匯入登入憑證，自動辨識格式並存入 AuthStateRepository"""
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            return ImportResult(ok=False, error=f"JSON 解析失敗: {e}")

        if isinstance(data, dict) and isinstance(data.get("cookies"), list):
            state = {
                "cookies": data["cookies"],
                "origins": data.get("origins", []),
            }
            fmt = "storage_state"
        elif isinstance(data, list):
            try:
                cookies = [_convert_extension_cookie(c) for c in data]
            except (TypeError, KeyError) as e:
                return ImportResult(ok=False, error=f"cookie 陣列格式錯誤: {e!r}")
            state = {"cookies": cookies, "origins": []}
            fmt = "cookie_array"
        else:
            return ImportResult(
                ok=False,
                error="無法辨識格式：請貼上 auth_state.json 內容，"
                "或瀏覽器擴充功能匯出的 cookie 陣列",
            )

        pchome_count = sum(
            1 for c in state["cookies"] if "pchome.com.tw" in c.get("domain", "")
        )
        warning = (
            ""
            if pchome_count
            else "警告：找不到任何 pchome.com.tw 的 cookie，登入可能無效"
        )

        self._store.save(state)
        with self._lock:
            self._last_check_ts = 0.0  # 新憑證，快取失效
            self._last_check_result = None

        return ImportResult(
            ok=True,
            format=fmt,
            cookie_count=len(state["cookies"]),
            pchome_cookie_count=pchome_count,
            warning=warning,
        )

    # ---- 狀態 ----

    def status(self, live: bool = False) -> dict:
        """登入狀態；live=True 時開 headless 瀏覽器實測（30 秒 debounce）"""
        state = self._store.get()
        if live and state is not None:
            with self._lock:
                stale = time.time() - self._last_check_ts > _LIVE_CHECK_DEBOUNCE_SECS
            if stale:
                valid = session.check_session_standalone(state)
                with self._lock:
                    self._last_check_ts = time.time()
                    self._last_check_result = valid
        with self._lock:
            return {
                "has_auth_state": state is not None,
                "session_valid": self._last_check_result,
                "checked_at": self._last_check_ts or None,
            }


def _convert_extension_cookie(c: dict) -> dict:
    """把瀏覽器擴充功能匯出的 cookie 轉為 Playwright storage_state 格式"""
    cookie = {k: v for k, v in c.items() if k not in _DROP_FIELDS}
    cookie["name"] = c["name"]
    cookie["value"] = c["value"]
    cookie["domain"] = c["domain"]
    cookie["path"] = c.get("path", "/")

    if c.get("session") or "expirationDate" not in c:
        cookie["expires"] = -1
    else:
        cookie["expires"] = float(c["expirationDate"])
    cookie.pop("expirationDate", None)

    raw_samesite = str(c.get("sameSite") or "").lower()
    cookie["sameSite"] = _SAMESITE_MAP.get(raw_samesite, "Lax")

    cookie.setdefault("httpOnly", False)
    cookie.setdefault("secure", False)
    return cookie
