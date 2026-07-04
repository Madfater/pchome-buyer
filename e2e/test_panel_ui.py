"""前端控制台的真實瀏覽器 e2e 測試

範圍見 conftest.py 開頭註解：只涵蓋不會啟動 job 的 UI 流程。特別注意「檢查 session」
（live 登入檢查）——只有在已匯入 auth_state 且 30 秒 debounce 過期時才會真的開一個
headless Playwright 瀏覽器連真實 24h.pchome.com.tw，這裡刻意完全不點那顆按鈕。
"""

import json

from playwright.sync_api import expect


def test_add_product_by_bare_id_appears_as_a_card(live_server, page):
    base_url, _container = live_server
    page.goto(base_url)

    page.get_by_role("button", name="＋ 新增任務").click()
    page.get_by_label("商品網址或編號").fill("dgcq39-a900jesmm")
    expect(page.get_by_text("商品編號：DGCQ39-A900JESMM")).to_be_visible()
    page.get_by_role("button", name="新增", exact=True).click()

    expect(page.get_by_text("DGCQ39-A900JESMM")).to_be_visible()
    expect(page.get_by_text("立即監控").first).to_be_visible()


def test_add_product_by_url_with_sale_time_groups_under_that_time(live_server, page):
    base_url, _container = live_server
    page.goto(base_url)

    page.get_by_role("button", name="＋ 新增任務").click()
    page.get_by_label("商品網址或編號").fill("https://24h.pchome.com.tw/prod/DGCQ39-A900JESMM")
    page.get_by_label("開始監測時間（留空表示立即監控）").fill("2026-03-06T12:00")
    page.get_by_role("button", name="新增", exact=True).click()

    expect(page.get_by_text("開賣 2026-03-06 12:00").first).to_be_visible()


def test_invalid_ref_disables_submit_with_an_error_hint(live_server, page):
    base_url, _container = live_server
    page.goto(base_url)

    page.get_by_role("button", name="＋ 新增任務").click()
    page.get_by_label("商品網址或編號").fill("not a valid ref")

    expect(page.get_by_text("無法解析商品編號")).to_be_visible()
    expect(page.get_by_role("button", name="新增", exact=True)).to_be_disabled()


def test_edit_sale_time_moves_card_into_new_group(live_server, page):
    base_url, container = live_server
    container.store.add("DGCQ39-A900JESMM", "")
    page.goto(base_url)

    expect(page.get_by_text("立即監控").first).to_be_visible()
    page.get_by_title("修改開賣時間").click()
    page.get_by_label("開始監測時間（留空表示立即監控）").fill("2026-05-01T09:00")
    page.get_by_role("button", name="儲存").click()

    expect(page.get_by_text("開賣 2026-05-01 09:00").first).to_be_visible()


def test_remove_product_requires_confirmation(live_server, page):
    base_url, container = live_server
    container.store.add("DGCQ39-A900JESMM", "")
    page.goto(base_url)

    expect(page.get_by_text("DGCQ39-A900JESMM")).to_be_visible()
    page.get_by_title("刪除任務").click()
    expect(page.get_by_text("將刪除 DGCQ39-A900JESMM，此操作無法復原。")).to_be_visible()

    # 對話框中同時有「取消」跟確認用的「刪除」，鎖定 dialog 範圍避免點到頁首其他同名按鈕
    page.get_by_role("dialog").get_by_role("button", name="刪除").click()

    expect(page.get_by_text("DGCQ39-A900JESMM")).not_to_be_visible()
    expect(page.get_by_text("尚未新增任務，按「＋ 新增任務」貼上商品網址開始")).to_be_visible()


def test_bulk_select_and_bulk_delete(live_server, page):
    base_url, container = live_server
    container.store.add("A-1", "")
    container.store.add("A-2", "")
    page.goto(base_url)

    page.get_by_role("checkbox", name="選取整組").click()
    expect(page.get_by_text("已選 2 個")).to_be_visible()

    page.get_by_role("button", name="刪除選取（2）").click()
    expect(page.get_by_text("將刪除 2 個未執行的任務，執行中的任務不受影響。此操作無法復原。")).to_be_visible()
    page.get_by_role("dialog").get_by_role("button", name="刪除").click()

    expect(page.get_by_text("尚未新增任務，按「＋ 新增任務」貼上商品網址開始")).to_be_visible()


def test_login_import_shows_success_and_updates_badge(live_server, page):
    base_url, _container = live_server
    page.goto(base_url)

    expect(page.get_by_text("未登入")).to_be_visible()

    page.get_by_role("button", name="登入").click()
    payload = json.dumps({"cookies": [{
        "name": "PCHOME_MEMBER",
        "value": "x",
        "domain": ".pchome.com.tw",
        "path": "/",
        "expires": -1,
        "httpOnly": False,
        "secure": False,
        "sameSite": "Lax",
    }]})
    page.get_by_label("憑證內容（JSON）").fill(payload)
    page.get_by_role("button", name="匯入").click()

    expect(page.get_by_text("匯入成功", exact=False)).to_be_visible()
    page.get_by_role("button", name="關閉").click()
    expect(page.get_by_text("已登入")).to_be_visible()


def test_login_import_rejects_unparseable_payload(live_server, page):
    base_url, _container = live_server
    page.goto(base_url)

    page.get_by_role("button", name="登入").click()
    page.get_by_label("憑證內容（JSON）").fill("not json at all")
    page.get_by_role("button", name="匯入").click()

    expect(page.get_by_text("JSON 解析失敗", exact=False)).to_be_visible()


def test_checkout_record_seeded_directly_is_listed_and_can_be_marked_complete(live_server, page):
    base_url, container = live_server
    container.checkout_store.add(
        gid="2026-03-06_1200#1",
        sale_time="2026-03-06 12:00",
        status="awaiting_payment",
        cart_results=[
            {
                "pid": "DGCQ39-A900JESMM",
                "ok": True,
                "sold_out": False,
                "stage": "",
                "prodcount": 1,
                "prodtotal": 990,
                "raw": None,
                "error": "",
            }
        ],
        payinfo=None,
        log_tail=["加入購物車成功"],
    )
    page.goto(base_url)

    expect(page.get_by_text("成功 1/1 件，$990")).to_be_visible()
    page.get_by_role("button", name="查看詳情").click()

    expect(page.get_by_role("heading", name="結帳詳情")).to_be_visible()
    expect(page.get_by_text("DGCQ39-A900JESMM")).to_be_visible()

    page.get_by_role("button", name="標記完成").click()
    expect(page.get_by_text("（已完成）")).to_be_visible()
    page.get_by_role("button", name="關閉").click()

    expect(page.get_by_role("button", name="清除已完成（1）")).to_be_visible()
    page.get_by_role("button", name="清除已完成（1）").click()
    expect(page.get_by_text("尚無結帳紀錄")).to_be_visible()
