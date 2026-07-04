import json

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from pchome.core import session
from pchome.core.config import CART_URL, HOME_URL


class FakePage:
    """模擬 check_session() 需要的三個方法：goto / wait_for_url / url"""

    def __init__(self, redirects_to_login: bool, final_url: str = ""):
        self._redirects_to_login = redirects_to_login
        self.url = final_url
        self.goto_calls: list[str] = []

    def goto(self, url, wait_until=None):
        self.goto_calls.append(url)

    def wait_for_url(self, pattern, timeout=None):
        if not self._redirects_to_login:
            raise PlaywrightTimeout("no redirect within timeout")


class TestHasAuthState:
    def test_true_when_file_exists(self, tmp_path, monkeypatch):
        path = tmp_path / "auth_state.json"
        path.write_text("{}")
        monkeypatch.setattr(session, "AUTH_STATE_FILE", path)
        assert session.has_auth_state() is True

    def test_false_when_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(session, "AUTH_STATE_FILE", tmp_path / "missing.json")
        assert session.has_auth_state() is False


class TestCheckSession:
    def test_redirected_to_login_means_expired(self):
        page = FakePage(redirects_to_login=True)
        assert session.check_session(page) is False
        assert page.goto_calls == [CART_URL]

    def test_no_redirect_and_url_has_no_login_means_valid(self):
        page = FakePage(
            redirects_to_login=False, final_url="https://ecssl.pchome.com.tw/fsrwd/cart"
        )
        assert session.check_session(page) is True

    def test_no_redirect_but_url_still_contains_login_means_expired(self):
        # 邊界情況：wait_for_url 逾時但最終 URL 仍含 login（例如緩慢的用戶端重導向）
        page = FakePage(
            redirects_to_login=False, final_url="https://ecssl.pchome.com.tw/login/x"
        )
        assert session.check_session(page) is False


class FakeLoginPage:
    """模擬 login_flow() 需要的 goto / get_by_role().click()

    calls: 跨所有 fake 物件共用的呼叫序列 log，讓測試能斷言「順序」
    （例如 wait_for_user() 必須發生在 save_auth_state() 之前），
    而不只是斷言「每件事各自發生過一次」。
    """

    def __init__(self, calls: list[str] | None = None):
        self.goto_calls: list[str] = []
        self.clicked: list[tuple[str, str | None]] = []
        self._calls = calls

    def goto(self, url):
        self.goto_calls.append(url)
        if self._calls is not None:
            self._calls.append("goto")

    def get_by_role(self, role, name=None):
        page = self

        class _Locator:
            def click(self):
                page.clicked.append((role, name))
                if page._calls is not None:
                    page._calls.append("click")

        return _Locator()


class FakeContext:
    def __init__(
        self, storage_state_value=None, calls: list[str] | None = None, **kwargs
    ):
        self.pages: list[FakeLoginPage] = []
        self.init_kwargs = kwargs
        self._storage_state_value = storage_state_value or {
            "cookies": [],
            "origins": [],
        }
        self._calls = calls

    def new_page(self):
        page = FakeLoginPage(calls=self._calls)
        self.pages.append(page)
        return page

    def storage_state(self):
        return self._storage_state_value


class FakeBrowser:
    def __init__(self, calls: list[str] | None = None):
        self.contexts: list[FakeContext] = []
        self.closed = False
        self._calls = calls

    def new_context(self, **kwargs):
        ctx = FakeContext(calls=self._calls, **kwargs)
        self.contexts.append(ctx)
        return ctx

    def close(self):
        self.closed = True
        if self._calls is not None:
            self._calls.append("close")


class FakeChromium:
    def __init__(self, calls: list[str] | None = None):
        self.launched: list[FakeBrowser] = []
        self.launch_headless_args: list[bool] = []
        self._calls = calls

    def launch(self, headless=True):
        self.launch_headless_args.append(headless)
        browser = FakeBrowser(calls=self._calls)
        self.launched.append(browser)
        return browser


class FakeP:
    def __init__(self, calls: list[str] | None = None):
        self.chromium = FakeChromium(calls=calls)


class FakeSyncPlaywright:
    """取代 `sync_playwright()`：`with sync_playwright() as p` 換成 fake p"""

    def __init__(self, calls: list[str] | None = None):
        self.p = FakeP(calls=calls)

    def __call__(self):
        return self

    def __enter__(self):
        return self.p

    def __exit__(self, *a):
        return False


class TestLoginFlow:
    def test_navigates_clicks_login_waits_then_saves_state(self, monkeypatch, tmp_path):
        calls: list[str] = []
        fake_pw = FakeSyncPlaywright(calls=calls)
        monkeypatch.setattr(session, "sync_playwright", fake_pw)
        auth_file = tmp_path / "auth_state.json"
        monkeypatch.setattr(session, "AUTH_STATE_FILE", auth_file)

        # session.save_auth_state 是模組全域名稱，login_flow 內部呼叫時是即時查找，
        # 換成會記錄呼叫時間點、但仍委派給原函式的包裝版本，藉此驗證呼叫順序
        original_save_auth_state = session.save_auth_state

        def logged_save_auth_state(context):
            calls.append("save")
            return original_save_auth_state(context)

        monkeypatch.setattr(session, "save_auth_state", logged_save_auth_state)

        def wait_for_user():
            calls.append("wait")

        session.login_flow(wait_for_user)

        # 順序斷言：goto → click → wait_for_user() → save_auth_state() → close()
        # 這條會抓到「等使用者登入前就先存檔」這種錯誤，光靠各自獨立的旗標測不出來
        assert calls == ["goto", "click", "wait", "save", "close"]

        assert fake_pw.p.chromium.launch_headless_args == [False]
        browser = fake_pw.p.chromium.launched[0]
        page = browser.contexts[0].pages[0]
        assert page.goto_calls == [HOME_URL]
        assert page.clicked == [("button", "登入")]
        assert browser.closed is True
        assert json.loads(auth_file.read_text()) == {"cookies": [], "origins": []}


class TestSaveAuthState:
    def test_writes_storage_state_as_json(self, monkeypatch, tmp_path):
        auth_file = tmp_path / "auth_state.json"
        monkeypatch.setattr(session, "AUTH_STATE_FILE", auth_file)

        class FakeCtx:
            def storage_state(self):
                return {"cookies": [{"name": "a"}], "origins": []}

        session.save_auth_state(FakeCtx())

        assert json.loads(auth_file.read_text())["cookies"] == [{"name": "a"}]


class TestCheckSessionStandalone:
    def test_returns_false_without_launching_playwright_when_no_auth_state(
        self, monkeypatch
    ):
        monkeypatch.setattr(session, "has_auth_state", lambda: False)

        def boom():
            raise AssertionError("不該在沒有 auth state 時啟動瀏覽器")

        monkeypatch.setattr(session, "sync_playwright", boom)

        assert session.check_session_standalone() is False

    def test_launches_headless_context_with_auth_state_and_delegates(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(session, "has_auth_state", lambda: True)
        auth_file = tmp_path / "auth_state.json"
        monkeypatch.setattr(session, "AUTH_STATE_FILE", auth_file)
        fake_pw = FakeSyncPlaywright()
        monkeypatch.setattr(session, "sync_playwright", fake_pw)
        received_pages = []

        def fake_check_session(page):
            received_pages.append(page)
            return True

        monkeypatch.setattr(session, "check_session", fake_check_session)

        result = session.check_session_standalone()

        assert result is True
        assert fake_pw.p.chromium.launch_headless_args == [True]
        browser = fake_pw.p.chromium.launched[0]
        ctx = browser.contexts[0]
        assert ctx.init_kwargs.get("storage_state") == auth_file
        assert received_pages == ctx.pages
        assert browser.closed is True

    def test_closes_browser_even_if_check_session_raises(self, monkeypatch, tmp_path):
        monkeypatch.setattr(session, "has_auth_state", lambda: True)
        monkeypatch.setattr(session, "AUTH_STATE_FILE", tmp_path / "auth_state.json")
        fake_pw = FakeSyncPlaywright()
        monkeypatch.setattr(session, "sync_playwright", fake_pw)

        def boom_check_session(page):
            raise RuntimeError("boom")

        monkeypatch.setattr(session, "check_session", boom_check_session)

        with pytest.raises(RuntimeError):
            session.check_session_standalone()

        assert fake_pw.p.chromium.launched[0].closed is True
