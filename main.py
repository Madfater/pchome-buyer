"""PChome 24h 搶購腳本 — 使用 Playwright 瀏覽器自動化"""

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv(Path(__file__).parent / ".env")

AUTH_STATE_FILE = Path(__file__).parent / "auth_state.json"

# PChome API endpoints
DATETIME_API = "https://ecapi.pchome.com.tw/server/v1/datetime"
PROD_BUTTON_API = "https://ecapi-cdn.pchome.com.tw/ecshop/prodapi/v2/prod/button"
SNAPUP_API = "https://ecssl-cart.pchome.com.tw/sys/cflow/ecapi/prod/cart/v1/prod/{product_id}/snapup"
CART_MODIFY_API = "https://ecssl-cart.pchome.com.tw/cart/index.php/prod/modify"
CART_HOST = "https://ecssl-cart.pchome.com.tw/"
PRODUCT_URL = "https://24h.pchome.com.tw/prod/{product_id}"
CART_URL = "https://ecssl.pchome.com.tw/fsrwd/cart"
PAYINFO_URL = "https://ecssl.pchome.com.tw/fsrwd/cart/payinfo"

# 開賣前幾秒切換到全速輪詢（搭配 --sale-time）
FAST_POLL_WINDOW_SECS = 15
# 慢速階段的輪詢間隔倍數
SLOW_POLL_FACTOR = 4
# 伺服器時間 offset / TLS 預熱的重新校正週期（秒）
RESYNC_SECS = 60

# 共用 JSONP helper：url 中的 {CB} 會被替換成一次性的 callback 名稱。
# PChome 的 prod/button、cart modify 皆為 JSONP-only 端點（跨域無 CORS），
# 必須用 <script> 注入呼叫，不能用 fetch。
JSONP_JS = """
(url) => new Promise((resolve, reject) => {
    const cb = '_jsonp_' + Date.now() + '_' + Math.floor(Math.random() * 1e6);
    let timer;
    const cleanup = (s) => { delete window[cb]; clearTimeout(timer); s.remove(); };
    window[cb] = (data) => { cleanup(s); resolve(data); };
    const s = document.createElement('script');
    s.src = url.split('{CB}').join(cb);
    s.onerror = () => { cleanup(s); reject(new Error('JSONP failed')); };
    timer = setTimeout(() => { cleanup(s); reject(new Error('JSONP timeout')); }, 10000);
    document.head.appendChild(s);
})
"""

# 批次加入購物車：每個商品做 snapup fetch → cart modify JSONP，
# 多商品以 Promise.all 並行（MAC 授權碼效期僅 15 秒，兩步必須緊接執行）。
ADD_TO_CART_JS = """
(args) => {
    const jsonp = %s;
    return Promise.all(args.items.map(async (item) => {
        try {
            const snap = await fetch(item.snapupUrl).then(r => r.json());
            if (snap.Status !== 'OK')
                return { pid: item.pid, ok: false, stage: 'snapup', resp: snap };
            const data = { ...item.cart, CAX: snap.MAC, CAXE: snap.MACExpire };
            const ts = Date.now();
            const url = args.modifyApi
                + `?callback={CB}&${ts}`
                + `&data=${encodeURIComponent(JSON.stringify(data))}`
                + `&_=${ts}&_callback={CB}`;
            const resp = await jsonp(url);
            return {
                pid: item.pid,
                ok: resp.PRODADD === '1',
                soldOut: resp.ISSALEOUT === 1,
                stage: 'modify',
                resp,
            };
        } catch (e) {
            return { pid: item.pid, ok: false, stage: 'error', error: String(e) };
        }
    }));
}
""" % JSONP_JS


def now_ms() -> str:
    """毫秒級時間戳，用於事後檢討搶購延遲"""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


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


def get_server_offset(page) -> float:
    """回傳（PChome 伺服器時間 − 本機時間）的秒數差，以 RTT 中點補償"""
    t0 = time.time()
    response = page.evaluate(f"fetch('{DATETIME_API}').then(r => r.json())")
    t1 = time.time()
    server_ts = datetime.strptime(
        response["ServerDTM"], "%Y/%m/%d %H:%M:%S"
    ).timestamp()
    return server_ts - (t0 + t1) / 2


def check_session(page) -> bool:
    """檢查登入 session 是否仍有效（前往購物車頁，過期會被導向登入頁）"""
    page.goto(CART_URL, wait_until="domcontentloaded")
    try:
        page.wait_for_url("**/login/**", timeout=3000)
        return False
    except PlaywrightTimeout:
        return "login" not in page.url


def wait_for_sale(
    page, product_ids: list[str], interval: float, sale_ts: float | None = None
) -> list[str]:
    """輪詢等待多個商品開賣，回傳可購買的商品 ID 列表

    使用 prod/button API 偵測 ButtonType 狀態：
    ForSale=可購買, NotReady=尚未開賣, SoldOut=已售完。
    任一商品開賣即結束等待；全部售完則回傳空列表。

    有指定 sale_ts（開賣時間）時分段輪詢：開賣前 FAST_POLL_WINDOW_SECS 秒
    才切到全速 interval，之前以 interval*SLOW_POLL_FACTOR 慢速輪詢。
    """
    # 先導向任一商品頁面，確保 cookie 正確（snapup API 需要從站內呼叫）
    page.goto(
        PRODUCT_URL.format(product_id=product_ids[0]),
        wait_until="domcontentloaded",
    )

    # 只在啟動時對時一次，之後用本機時間 + offset 推算，避免每輪多一次往返
    offset = get_server_offset(page)
    last_sync = time.time()
    last_warm = 0.0
    print(f"PChome 伺服器時間: {datetime.fromtimestamp(time.time() + offset):%Y/%m/%d %H:%M:%S}"
          f"（與本機差 {offset:+.2f} 秒）")
    if sale_ts is not None:
        print(f"開賣時間: {datetime.fromtimestamp(sale_ts):%Y/%m/%d %H:%M:%S}"
              f"，前 {FAST_POLL_WINDOW_SECS} 秒起全速輪詢")
    print(f"監控 {len(product_ids)} 個商品...")

    ids_param = ",".join(product_ids)
    button_url = f"{PROD_BUTTON_API}&id={ids_param}&_callback={{CB}}"
    reported_sold_out: set[str] = set()

    while True:
        # 用 button API 併行查詢所有商品的 ButtonType 狀態（JSONP 端點）
        # ButtonType: "ForSale"=可購買, "NotReady"=尚未開賣, "SoldOut"=已售完
        btn_results = page.evaluate(JSONP_JS, button_url)
        # btn_results 是陣列，每個元素有 Id, ButtonType, Qty 欄位
        status_map = {
            item["Id"].rsplit("-", 1)[0]: item for item in btn_results
        }

        ready = [
            pid for pid in product_ids
            if status_map.get(pid, {}).get("ButtonType") == "ForSale"
        ]
        sold_out = [
            pid for pid in product_ids
            if status_map.get(pid, {}).get("ButtonType") == "SoldOut"
        ]
        for pid in sold_out:
            if pid not in reported_sold_out:
                reported_sold_out.add(pid)
                print(f"\n[{now_ms()}] 已售完: {pid}")

        if ready:
            qty_info = ", ".join(
                f"{pid}(剩 {status_map[pid].get('Qty', '?')} 件)" for pid in ready
            )
            print(f"\n[{now_ms()}] {len(ready)} 個商品可購買: {qty_info}")
            return ready

        if len(sold_out) == len(product_ids):
            print(f"\n[{now_ms()}] 所有商品皆已售完，結束監控")
            return []

        now = time.time()

        # 每 RESYNC_SECS 秒重新對時一次，並預熱與購物車主機的 TLS 連線，
        # 讓開賣瞬間的 snapup 呼叫免付握手成本
        if now - last_sync >= RESYNC_SECS:
            offset = get_server_offset(page)
            last_sync = now
        if now - last_warm >= RESYNC_SECS:
            page.evaluate(
                f"fetch('{CART_HOST}', {{mode: 'no-cors', cache: 'no-store'}})"
                ".catch(() => {})"
            )
            last_warm = now

        # 分段輪詢：離開賣還久就放慢，接近開賣才全速
        cur_interval = interval
        if sale_ts is not None and (sale_ts - (now + offset)) > FAST_POLL_WINDOW_SECS:
            cur_interval = interval * SLOW_POLL_FACTOR

        server_now = datetime.fromtimestamp(now + offset)
        statuses = " ".join(
            f"{pid.split('-')[-1]}={status_map.get(pid, {}).get('ButtonType', '?')}"
            for pid in product_ids
        )
        print(
            f"\r尚未開賣 | 伺服器時間: {server_now:%H:%M:%S} | {statuses}",
            end="", flush=True,
        )
        time.sleep(random.uniform(cur_interval * 0.5, cur_interval * 1.5))


def add_to_cart_batch(page, product_ids: list[str]) -> list[dict]:
    """透過 snapup + cart modify API 將多個商品並行加入購物車

    回傳每個商品的結果 dict：{pid, ok, soldOut, stage, resp/error}
    """
    items = []
    for pid in product_ids:
        # 從商品 ID 解析店鋪代碼（如 DGCQ39-A900JESMM → RS=DGCQ39, TI=DGCQ39-A900JESMM-000）
        items.append({
            "pid": pid,
            "snapupUrl": SNAPUP_API.format(product_id=pid),
            "cart": {
                "G": [], "A": [], "B": [], "C": [],
                "TB": "24H",
                "TP": 2,
                "T": "ADD",
                "TI": f"{pid}-000",
                "RS": pid.split("-")[0],
                "YTQ": 1,
            },
        })
    return page.evaluate(ADD_TO_CART_JS, {"items": items, "modifyApi": CART_MODIFY_API})


def go_to_checkout(page):
    """跳轉到結帳頁面，自動填寫 CVC 並可選自動付款"""
    print("正在前往結帳頁面...")
    page.goto(CART_URL, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except PlaywrightTimeout:
        pass
    page.goto(PAYINFO_URL, wait_until="domcontentloaded")
    print(f"已跳轉至: {page.url}")

    # 等待付款資料頁面載入（多組 selector fallback，頁面改版時較不易失效）
    cvc_selector = ", ".join([
        'input[placeholder="CVC"]',
        'input[name*="cvc" i]',
        'input[id*="cvc" i]',
        'input[autocomplete="cc-csc"]',
    ])
    try:
        page.wait_for_selector(cvc_selector, timeout=10000)
    except PlaywrightTimeout:
        print("未找到 CVC 欄位，可能頁面結構有變，請手動完成結帳")
        return

    # 填入信用卡安全碼
    cvc = os.getenv("CVC", "")
    if cvc:
        page.locator(cvc_selector).first.fill(cvc)
        print("已自動填入信用卡安全碼")
    else:
        print("未設定 CVC，請手動填寫安全碼（設定 .env 中的 CVC）")

    # 自動確認付款
    auto_pay = os.getenv("AUTO_PAY", "false").lower() == "true"
    if auto_pay:
        pay_btn = page.locator("button:has-text('確認付款')").first
        print("即將自動點擊「確認付款」...")
        pay_btn.click(timeout=15000)  # click 會自動等待按鈕可見且 enabled
        print(f"[{now_ms()}] 已點擊確認付款！")
    else:
        print("AUTO_PAY 未啟用，請手動點擊「確認付款」")


def parse_sale_time(value: str) -> float:
    """解析開賣時間字串為本機 timestamp"""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt).timestamp()
        except ValueError:
            continue
    print(f'錯誤: 無法解析開賣時間 "{value}"（格式: "YYYY-MM-DD HH:MM"）')
    sys.exit(1)


def cmd_buy(args):
    """搶購商品（支援多個商品 ID）"""
    product_ids = args.product_ids
    headless = args.headless
    interval = args.interval
    sale_ts = parse_sale_time(args.sale_time) if args.sale_time else None

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

        # 開跑前先確認 session 有效，避免等到開賣才發現要重新登入
        print("檢查登入狀態...")
        if not check_session(page):
            print("錯誤: 登入 session 已過期！請重新執行 `python main.py login`")
            browser.close()
            sys.exit(1)
        print("登入狀態有效")

        # 等待任一商品開賣
        print("開始監控商品狀態...")
        ready_ids = wait_for_sale(page, product_ids, interval, sale_ts)
        if not ready_ids:
            browser.close()
            sys.exit(1)

        # 並行加入購物車，失敗的商品重試（售完不重試）
        success_ids: list[str] = []
        pending = ready_ids
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            results = add_to_cart_batch(page, pending)
            pending = []
            for res in results:
                pid = res["pid"]
                if res.get("ok"):
                    resp = res["resp"]
                    print(f"[{now_ms()}] {pid} 已加入購物車！"
                          f"購物車共 {resp.get('PRODCOUNT')} 件，金額 ${resp.get('PRODTOTAL')}")
                    success_ids.append(pid)
                elif res.get("soldOut"):
                    print(f"[{now_ms()}] {pid} 已售完！")
                elif res.get("stage") == "snapup":
                    print(f"[{now_ms()}] {pid} snapup 失敗: {res.get('resp')}"
                          "（若持續失敗，session 可能已過期，請重新執行 login）")
                    pending.append(pid)
                else:
                    print(f"[{now_ms()}] {pid} 加入購物車失敗: "
                          f"{res.get('resp') or res.get('error')}")
                    pending.append(pid)
            if not pending:
                break
            if attempt < max_retries:
                print(f"重試加入購物車 ({attempt}/{max_retries}): {', '.join(pending)}")
                time.sleep(0.3)
        for pid in pending:
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
    buy_parser.add_argument("--sale-time", help='開賣時間 "YYYY-MM-DD HH:MM"；指定後開賣前才全速輪詢')

    args = parser.parse_args()

    if args.command == "login":
        cmd_login(args)
    elif args.command == "buy":
        cmd_buy(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
