"""PChome 24h 搶購腳本 — 使用 Playwright 瀏覽器自動化"""

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv(Path(__file__).parent / ".env")

AUTH_STATE_FILE = Path(__file__).parent / "auth_state.json"

# PChome API endpoints
DATETIME_API = "https://ecapi.pchome.com.tw/server/v1/datetime"
PROD_BUTTON_API = "https://ecapi-cdn.pchome.com.tw/ecshop/prodapi/v2/prod/button"
SNAPUP_API = "https://ecssl-cart.pchome.com.tw/sys/cflow/ecapi/prod/cart/v1/prod/{product_id}/snapup"
PRODUCT_URL = "https://24h.pchome.com.tw/prod/{product_id}"
CART_URL = "https://ecssl.pchome.com.tw/fsrwd/cart"
PAYINFO_URL = "https://ecssl.pchome.com.tw/fsrwd/cart/payinfo"


def cmd_login(args):
    """開啟瀏覽器讓使用者手動登入，完成後儲存 session"""
    print("正在開啟瀏覽器，請手動登入 PChome...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # 導向登入頁面
        page.goto("https://24h.pchome.com.tw/")
        page.get_by_role("button", name="登入").click()

        # 等待使用者手動登入完成（偵測頁面上出現「顧客中心」或使用者關閉登入視窗）
        print("請在瀏覽器中完成登入...")
        print("登入完成後，按 Enter 鍵儲存 session...")
        input()

        # 儲存登入狀態
        state = context.storage_state()
        AUTH_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        print(f"登入狀態已儲存至 {AUTH_STATE_FILE}")

        browser.close()


def get_server_time(page) -> str:
    """取得 PChome 伺服器時間"""
    response = page.evaluate(
        f"fetch('{DATETIME_API}').then(r => r.json())"
    )
    return response.get("ServerDTM", "")


def wait_for_sale(page, product_ids: list[str], interval: float) -> list[str]:
    """輪詢等待多個商品開賣，回傳可購買的商品 ID 列表

    使用 prod/button API 偵測 ButtonType 狀態：
    ForSale=可購買, NotReady=尚未開賣, SoldOut=已售完。
    任一商品開賣即結束等待，回傳所有可購買的商品。
    """
    # 先導向任一商品頁面，確保 cookie 正確（API 需要同源）
    page.goto(
        PRODUCT_URL.format(product_id=product_ids[0]),
        wait_until="domcontentloaded",
    )

    server_time = get_server_time(page)
    print(f"PChome 伺服器時間: {server_time}")
    print(f"監控 {len(product_ids)} 個商品...")

    while True:
        # 用 button API 併行查詢所有商品的 ButtonType 狀態（JSONP 端點）
        # ButtonType: "ForSale"=可購買, "NotReady"=尚未開賣, "SoldOut"=已售完
        ids_param = ",".join(product_ids)
        btn_results = page.evaluate(
            """
            (idsParam) => new Promise((resolve, reject) => {
                const cb = 'jsonp_chk_' + Date.now();
                window[cb] = (data) => { delete window[cb]; resolve(data); };
                const s = document.createElement('script');
                s.src = `%s&id=${idsParam}&_callback=${cb}`;
                s.onerror = () => { delete window[cb]; reject('JSONP failed'); };
                document.head.appendChild(s);
                setTimeout(() => { delete window[cb]; reject('timeout'); }, 10000);
            })
            """ % PROD_BUTTON_API,
            ids_param,
        )
        # btn_results 是陣列，每個元素有 Id, ButtonType 欄位
        status_map = {
            item["Id"].rsplit("-", 1)[0]: item["ButtonType"]
            for item in btn_results
        }
        ready = [
            pid for pid in product_ids
            if status_map.get(pid) == "ForSale"
        ]
        sold_out = [
            pid for pid in product_ids
            if status_map.get(pid) == "SoldOut"
        ]
        if sold_out:
            print(f"\n已售完: {', '.join(sold_out)}")

        if ready:
            print(f"\n{len(ready)} 個商品可購買: {', '.join(ready)}")
            return ready

        server_time = get_server_time(page)
        print(
            f"\r尚未開賣 | 伺服器時間: {server_time} | 監控中...",
            end="", flush=True,
        )
        time.sleep(random.uniform(interval * 0.5, interval * 1.5))


def add_to_cart(page, product_id: str) -> bool:
    """透過 snapup + cart modify API 加入購物車"""
    # Step 1: 呼叫 snapup API 取得授權碼 (MAC)
    snapup_url = SNAPUP_API.format(product_id=product_id)
    snapup_result = page.evaluate(
        f"fetch('{snapup_url}').then(r => r.json())"
    )
    print(f"Snapup API 回應: {snapup_result}")

    if snapup_result.get("Status") != "OK":
        print(f"Snapup 失敗: {snapup_result}")
        return False

    mac = snapup_result["MAC"]
    mac_expire = snapup_result["MACExpire"]
    # 從商品 ID 解析店鋪代碼（如 DGCQ39-A900JESMM → RS=DGCQ39, TI=DGCQ39-A900JESMM-000）
    store_id = product_id.split("-")[0]

    # Step 2: 呼叫 cart modify API 實際加入購物車
    cart_data = json.dumps({
        "G": [], "A": [], "B": [], "C": [],
        "TB": "24H",
        "TP": 2,
        "T": "ADD",
        "TI": f"{product_id}-000",
        "RS": store_id,
        "YTQ": 1,
        "CAX": mac,
        "CAXE": mac_expire,
    }, ensure_ascii=False)

    # cart modify API 是 JSONP 端點，需用 script injection 呼叫（無法用 fetch 跨域）
    modify_result = page.evaluate(
        """
        (cartData) => new Promise((resolve, reject) => {
            const cbName = 'jsonp_addcart_' + Date.now();
            const ts = Date.now();
            window[cbName] = (data) => {
                delete window[cbName];
                resolve(data);
            };
            const script = document.createElement('script');
            script.src = `https://ecssl-cart.pchome.com.tw/cart/index.php/prod/modify`
                + `?callback=${cbName}&${ts}`
                + `&data=${encodeURIComponent(cartData)}`
                + `&_=${ts}&_callback=${cbName}`;
            script.onerror = () => { delete window[cbName]; reject('JSONP request failed'); };
            document.head.appendChild(script);
            setTimeout(() => { delete window[cbName]; reject('JSONP timeout'); }, 10000);
        })
        """,
        cart_data,
    )
    print(f"Cart Modify 回應: {modify_result}")

    if modify_result.get("PRODADD") == "1":
        print(f"商品已加入購物車！購物車共 {modify_result.get('PRODCOUNT')} 件，"
              f"金額 ${modify_result.get('PRODTOTAL')}")
        return True
    if modify_result.get("ISSALEOUT") == 1:
        print("商品已售完！")
        return False

    return False


def go_to_checkout(page):
    """跳轉到結帳頁面，自動填寫 CVC 並可選自動付款"""
    print("正在前往結帳頁面...")
    page.goto(CART_URL, wait_until="domcontentloaded")
    time.sleep(1)
    page.goto(PAYINFO_URL, wait_until="domcontentloaded")
    print(f"已跳轉至: {page.url}")

    # 等待付款資料頁面載入
    try:
        page.wait_for_selector('input[placeholder="CVC"]', timeout=10000)
    except PlaywrightTimeout:
        print("未找到 CVC 欄位，可能頁面結構有變")
        return

    # 填入信用卡安全碼
    cvc = os.getenv("CVC", "")
    if cvc:
        page.fill('input[placeholder="CVC"]', cvc)
        print("已自動填入信用卡安全碼")
    else:
        print("未設定 CVC，請手動填寫安全碼（設定 .env 中的 CVC）")

    # 自動確認付款
    auto_pay = os.getenv("AUTO_PAY", "false").lower() == "true"
    if auto_pay:
        pay_btn = page.locator("button:has-text('確認付款')").first
        print("即將自動點擊「確認付款」...")
        pay_btn.click()
        print("已點擊確認付款！")
    else:
        print("AUTO_PAY 未啟用，請手動點擊「確認付款」")


def cmd_buy(args):
    """搶購商品（支援多個商品 ID）"""
    product_ids = args.product_ids
    headless = args.headless
    interval = args.interval

    if not AUTH_STATE_FILE.exists():
        print("錯誤: 尚未登入！請先執行 `python main.py login` 進行登入")
        sys.exit(1)

    print(f"目標商品 ({len(product_ids)} 個):")
    for pid in product_ids:
        print(f"  - {pid}  {PRODUCT_URL.format(product_id=pid)}")
    print(f"輪詢間隔: {interval} 秒")
    print(f"無頭模式: {'是' if headless else '否'}")
    print("-" * 50)

    auth_state = json.loads(AUTH_STATE_FILE.read_text())

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(storage_state=auth_state)
        page = context.new_page()

        # 等待任一商品開賣
        print("開始監控商品狀態...")
        ready_ids = wait_for_sale(page, product_ids, interval)

        # 逐一加入購物車
        success_ids = []
        for pid in ready_ids:
            print(f"\n--- 加入購物車: {pid} ---")
            max_retries = 3
            for attempt in range(max_retries):
                if add_to_cart(page, pid):
                    success_ids.append(pid)
                    break
                print(f"重試加入購物車 ({attempt + 1}/{max_retries})...")
                time.sleep(0.3)
            else:
                print(f"商品 {pid} 加入購物車失敗")

        if not success_ids:
            print("\n所有商品加入購物車失敗！")
            browser.close()
            sys.exit(1)

        print(f"\n成功加入 {len(success_ids)}/{len(ready_ids)} 個商品")

        # 前往結帳
        go_to_checkout(page)

        # 保持瀏覽器開啟，讓使用者手動完成結帳
        print("\n瀏覽器保持開啟中，完成結帳後按 Enter 關閉...")
        input()
        browser.close()


def main():
    parser = argparse.ArgumentParser(description="PChome 24h 搶購腳本")
    subparsers = parser.add_subparsers(dest="command", help="可用指令")

    # login 指令
    subparsers.add_parser("login", help="開啟瀏覽器手動登入，儲存 session")

    # buy 指令
    buy_parser = subparsers.add_parser("buy", help="搶購指定商品")
    buy_parser.add_argument("product_ids", nargs="+", help="商品編號，可指定多個 (如 DGCQ39-A900JESMM DGCQ39-A900JL925)")
    buy_parser.add_argument("--headless", action="store_true", help="無頭模式（不顯示瀏覽器）")
    buy_parser.add_argument("--interval", type=float, default=0.5, help="輪詢間隔秒數（預設 0.5）")

    args = parser.parse_args()

    if args.command == "login":
        cmd_login(args)
    elif args.command == "buy":
        cmd_buy(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
