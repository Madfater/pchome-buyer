"""結帳：跳轉付款頁、自動填 CVC、可選自動點擊確認付款，並擷取結帳資訊"""

from dataclasses import dataclass, field

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from .config import CART_URL, PAYINFO_URL, get_cvc, is_auto_pay
from .reporter import Reporter
from .timing import now_ms

# 多組 selector fallback，頁面改版時較不易失效
CVC_SELECTOR = ", ".join([
    'input[placeholder="CVC"]',
    'input[name*="cvc" i]',
    'input[id*="cvc" i]',
    'input[autocomplete="cc-csc"]',
])

# 結帳資訊擷取（best-effort）：payinfo 頁面結構未定版，逐一嘗試
_TOTAL_SELECTORS = [
    "[class*='total'] [class*='price']",
    "[class*='totalPrice']",
    "[class*='amount']",
]
_ITEM_ROW_SELECTORS = [
    "[class*='prodList'] [class*='item']",
    "[class*='cartItem']",
    "[class*='orderItem']",
]
_RAW_TEXT_CAP = 2000


@dataclass
class CheckoutInfo:
    """結帳頁擷取結果；擷取失敗時至少保有 url 與頁面文字"""

    url: str = ""
    cvc_filled: bool = False
    auto_pay_clicked: bool = False
    items: list[dict] = field(default_factory=list)  # [{name, price, qty}]
    total: str = ""
    raw_text: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "cvc_filled": self.cvc_filled,
            "auto_pay_clicked": self.auto_pay_clicked,
            "items": self.items,
            "total": self.total,
            "raw_text": self.raw_text,
            "error": self.error,
        }


def go_to_checkout(page, reporter: Reporter) -> CheckoutInfo:
    """跳轉到結帳頁面，自動填寫 CVC 並可選自動付款，回傳擷取的結帳資訊"""
    info = CheckoutInfo()
    reporter.log("正在前往結帳頁面...")
    page.goto(CART_URL, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except PlaywrightTimeout:
        pass
    page.goto(PAYINFO_URL, wait_until="domcontentloaded")
    info.url = page.url
    reporter.log(f"已跳轉至: {page.url}")

    try:
        page.wait_for_selector(CVC_SELECTOR, timeout=10000)
    except PlaywrightTimeout:
        reporter.log("未找到 CVC 欄位，可能頁面結構有變，請手動完成結帳")
        _capture_payinfo(page, info)
        return info

    cvc = get_cvc()
    if cvc:
        page.locator(CVC_SELECTOR).first.fill(cvc)
        info.cvc_filled = True
        reporter.log("已自動填入信用卡安全碼")
    else:
        reporter.log("未設定 CVC，請手動填寫安全碼（設定 .env 中的 CVC）")

    _capture_payinfo(page, info)

    if is_auto_pay():
        pay_btn = page.locator("button:has-text('確認付款')").first
        reporter.log("即將自動點擊「確認付款」...")
        pay_btn.click(timeout=15000)  # click 會自動等待按鈕可見且 enabled
        info.auto_pay_clicked = True
        reporter.log(f"[{now_ms()}] 已點擊確認付款！")
    else:
        reporter.log("AUTO_PAY 未啟用，請手動點擊「確認付款」")
    return info


def _capture_payinfo(page, info: CheckoutInfo) -> None:
    """擷取 payinfo 頁面的訂單資訊；任何失敗都不能影響付款流程"""
    try:
        info.raw_text = page.locator("body").inner_text(timeout=3000)[:_RAW_TEXT_CAP]
    except Exception as e:
        info.error = f"raw_text: {e!r}"
        return

    try:
        for sel in _TOTAL_SELECTORS:
            loc = page.locator(sel)
            if loc.count():
                text = loc.first.inner_text(timeout=1000).strip()
                if text:
                    info.total = text
                    break
        for sel in _ITEM_ROW_SELECTORS:
            rows = page.locator(sel)
            n = min(rows.count(), 20)
            if not n:
                continue
            for i in range(n):
                text = rows.nth(i).inner_text(timeout=1000).strip()
                if text:
                    info.items.append({"name": text.split("\n")[0], "raw": text[:300]})
            if info.items:
                break
    except Exception as e:
        # 結構化擷取失敗不算致命，raw_text 已保底
        info.error = f"structured: {e!r}"
