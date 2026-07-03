"""登入 session 的建立、儲存、載入與有效性檢查"""

import json
from typing import Callable

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from .config import AUTH_STATE_FILE, CART_URL, HOME_URL


def login_flow(wait_for_user: Callable[[], None]) -> None:
    """開啟有頭瀏覽器導向登入頁，待 wait_for_user() 返回後儲存 session

    wait_for_user 由呼叫端決定阻塞方式：CLI 用 input()，網頁端用 Event.wait()。
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto(HOME_URL)
        page.get_by_role("button", name="登入").click()

        wait_for_user()

        save_auth_state(context)
        browser.close()


def save_auth_state(context) -> None:
    state = context.storage_state()
    AUTH_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def has_auth_state() -> bool:
    return AUTH_STATE_FILE.exists()


def load_auth_state() -> dict:
    return json.loads(AUTH_STATE_FILE.read_text())


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
