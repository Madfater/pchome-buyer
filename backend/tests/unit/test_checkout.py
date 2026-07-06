from playwright.sync_api import TimeoutError as PlaywrightTimeout

from pchome.core.checkout import (
    CVC_SELECTOR,
    _ITEM_ROW_SELECTORS,
    _TOTAL_SELECTORS,
    go_to_checkout,
)
from pchome.core.reporter import Reporter


class FakeReporter(Reporter):
    def __init__(self):
        self.logs: list[str] = []

    def log(self, msg: str) -> None:
        self.logs.append(msg)


class FakeLocator:
    def __init__(self, count=0, texts=None):
        self._count = count
        self.texts = texts or []
        self.fill_calls: list[str] = []
        self.click_calls: list[int | None] = []

    @property
    def first(self):
        return self

    def count(self):
        return self._count

    def fill(self, value):
        self.fill_calls.append(value)

    def click(self, timeout=None):
        self.click_calls.append(timeout)

    def inner_text(self, timeout=None):
        return self.texts[0] if self.texts else ""

    def nth(self, i):
        return FakeLocator(count=1, texts=[self.texts[i]])


class BoomLocator(FakeLocator):
    """inner_text() 一律拋錯，模擬結帳頁擷取失敗"""

    def inner_text(self, timeout=None):
        raise RuntimeError("boom")


class BoomCountLocator(FakeLocator):
    """count() 拋錯，模擬結構化擷取失敗（但 raw_text 已保底成功）"""

    def count(self):
        raise RuntimeError("boom")


class FakePage:
    def __init__(
        self,
        *,
        cvc_found=True,
        body_locator=None,
        total_locator=None,
        item_locator=None,
    ):
        self.url = "https://ecssl.pchome.com.tw/fsrwd/cart/payinfo"
        self.goto_calls: list[str] = []
        self._cvc_found = cvc_found
        self.cvc_locator = FakeLocator(count=1)
        self.pay_locator = FakeLocator(count=1)
        self.body_locator = body_locator or FakeLocator(count=1, texts=["訂單內容"])
        self._total_locator = total_locator or FakeLocator(count=0)
        self._item_locator = item_locator or FakeLocator(count=0)

    def goto(self, url, wait_until=None):
        self.goto_calls.append(url)
        self.url = url

    def wait_for_load_state(self, state, timeout=None):
        pass

    def wait_for_selector(self, selector, timeout=None):
        if not self._cvc_found:
            raise PlaywrightTimeout("cvc not found")

    def locator(self, selector):
        if selector == CVC_SELECTOR:
            return self.cvc_locator
        if "確認付款" in selector:
            return self.pay_locator
        if selector == "body":
            return self.body_locator
        if selector == _TOTAL_SELECTORS[0]:
            return self._total_locator
        if selector == _ITEM_ROW_SELECTORS[0]:
            return self._item_locator
        return FakeLocator(count=0)


class TestCvcField:
    def test_missing_cvc_field_returns_early_but_still_captures(self):
        reporter = FakeReporter()
        page = FakePage(cvc_found=False)

        info = go_to_checkout(page, reporter)

        assert info.cvc_filled is False
        assert info.raw_text == "訂單內容"
        assert any("未找到 CVC 欄位" in line for line in reporter.logs)

    def test_fills_cvc_when_configured(self):
        reporter = FakeReporter()
        page = FakePage()

        info = go_to_checkout(page, reporter, cvc="123")

        assert page.cvc_locator.fill_calls == ["123"]
        assert info.cvc_filled is True
        assert any("已自動填入信用卡安全碼" in line for line in reporter.logs)

    def test_skips_fill_when_cvc_not_configured(self):
        reporter = FakeReporter()
        page = FakePage()

        info = go_to_checkout(page, reporter)

        assert page.cvc_locator.fill_calls == []
        assert info.cvc_filled is False
        assert any("未設定 CVC" in line for line in reporter.logs)


class TestAutoPay:
    def test_clicks_pay_button_when_auto_pay_enabled(self):
        reporter = FakeReporter()
        page = FakePage()

        info = go_to_checkout(page, reporter, cvc="123", auto_pay=True)

        assert page.pay_locator.click_calls == [15000]
        assert info.auto_pay_clicked is True
        assert any("已點擊確認付款" in line for line in reporter.logs)

    def test_does_not_click_when_auto_pay_disabled(self):
        reporter = FakeReporter()
        page = FakePage()

        info = go_to_checkout(page, reporter, cvc="123")

        assert page.pay_locator.click_calls == []
        assert info.auto_pay_clicked is False
        assert any("自動付款未啟用" in line for line in reporter.logs)


class TestCapturePayinfo:
    def test_extracts_total_and_items(self):
        page = FakePage(
            total_locator=FakeLocator(count=1, texts=["NT$999"]),
            item_locator=FakeLocator(count=2, texts=["商品A\n數量1", "商品B\n數量2"]),
        )

        info = go_to_checkout(page, FakeReporter())

        assert info.total == "NT$999"
        assert info.items == [
            {"name": "商品A", "raw": "商品A\n數量1"},
            {"name": "商品B", "raw": "商品B\n數量2"},
        ]
        assert info.error == ""

    def test_raw_text_failure_does_not_interrupt_payment_flow(self):
        page = FakePage(body_locator=BoomLocator())

        info = go_to_checkout(page, FakeReporter(), cvc="123", auto_pay=True)

        assert info.raw_text == ""
        assert "raw_text" in info.error
        # 擷取失敗不能中斷付款流程（CLAUDE.md 不變量 #10）
        assert info.cvc_filled is True
        assert info.auto_pay_clicked is True

    def test_structured_capture_failure_keeps_raw_text(self):
        page = FakePage(total_locator=BoomCountLocator())

        info = go_to_checkout(page, FakeReporter())

        assert info.raw_text == "訂單內容"
        assert "structured" in info.error

    def test_no_matching_selectors_leaves_total_and_items_empty(self):
        info = go_to_checkout(FakePage(), FakeReporter())
        assert info.total == ""
        assert info.items == []
        assert info.error == ""
