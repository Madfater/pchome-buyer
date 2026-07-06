"""登入 session 的有效性檢查"""

from typing import cast

from playwright.sync_api import StorageState, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from .config import CART_URL


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


def check_session_standalone(storage_state: dict) -> bool:
    """開短命 headless 瀏覽器檢查 session 有效性，供 auth 狀態端點使用

    storage_state 由呼叫端（services 層）從 AuthStateRepository 取得後傳入；
    core/ 本身不碰持久化。
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                storage_state=cast(StorageState, storage_state)
            )
            page = context.new_page()
            return check_session(page)
        finally:
            browser.close()
