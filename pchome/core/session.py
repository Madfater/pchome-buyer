"""登入 session 的建立、儲存、載入與有效性檢查"""

import json

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from .config import AUTH_STATE_FILE, CART_URL


def save_auth_state(context) -> None:
    state = context.storage_state()
    AUTH_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def has_auth_state() -> bool:
    return AUTH_STATE_FILE.exists()


def check_session(page) -> bool:
    """檢查登入 session 是否仍有效（前往購物車頁，過期會被導向登入頁）

    注意：snapup/cart modify 不需登入也能呼叫，登入只在結帳時強制，
    所以必須在監控開始前主動檢查，避免開賣瞬間才發現 session 過期。
    """
    page.goto(CART_URL, wait_until="domcontentloaded")
    try:
        page.wait_for_url("**/login/**", timeout=3000)
        return False
    except PlaywrightTimeout:
        return "login" not in page.url


def check_session_standalone() -> bool:
    """開短命 headless 瀏覽器檢查 session 有效性，供 auth 狀態端點使用"""
    if not has_auth_state():
        return False
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(storage_state=AUTH_STATE_FILE)
            page = context.new_page()
            return check_session(page)
        finally:
            browser.close()
