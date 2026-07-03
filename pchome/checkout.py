"""結帳：跳轉付款頁、自動填 CVC、可選自動點擊確認付款"""

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


def go_to_checkout(page, reporter: Reporter) -> None:
    """跳轉到結帳頁面，自動填寫 CVC 並可選自動付款"""
    reporter.log("正在前往結帳頁面...")
    page.goto(CART_URL, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except PlaywrightTimeout:
        pass
    page.goto(PAYINFO_URL, wait_until="domcontentloaded")
    reporter.log(f"已跳轉至: {page.url}")

    try:
        page.wait_for_selector(CVC_SELECTOR, timeout=10000)
    except PlaywrightTimeout:
        reporter.log("未找到 CVC 欄位，可能頁面結構有變，請手動完成結帳")
        return

    cvc = get_cvc()
    if cvc:
        page.locator(CVC_SELECTOR).first.fill(cvc)
        reporter.log("已自動填入信用卡安全碼")
    else:
        reporter.log("未設定 CVC，請手動填寫安全碼（設定 .env 中的 CVC）")

    if is_auto_pay():
        pay_btn = page.locator("button:has-text('確認付款')").first
        reporter.log("即將自動點擊「確認付款」...")
        pay_btn.click(timeout=15000)  # click 會自動等待按鈕可見且 enabled
        reporter.log(f"[{now_ms()}] 已點擊確認付款！")
    else:
        reporter.log("AUTO_PAY 未啟用，請手動點擊「確認付款」")
