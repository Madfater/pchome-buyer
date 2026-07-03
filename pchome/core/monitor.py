"""開賣監控：輪詢 prod/button API 直到任一商品可購買"""

import random
import threading
import time
from datetime import datetime

from .cancel import JobCancelled, cancellable_sleep, check_cancel
from .config import (
    CART_HOST,
    FAST_POLL_WINDOW_SECS,
    PROD_BUTTON_API,
    PRODUCT_URL,
    RESYNC_SECS,
    SLOW_POLL_FACTOR,
)
from .jsapi import JSONP_JS
from .membership import GroupMembership
from .reporter import Reporter
from .timing import get_server_offset, now_ms

# ButtonType → 卡片狀態
_BUTTON_TO_CARD = {"ForSale": "forsale", "SoldOut": "soldout"}


def wait_for_sale(
    page,
    membership: GroupMembership,
    interval: float,
    sale_ts: float | None,
    reporter: Reporter,
    cancel: threading.Event | None = None,
) -> list[str]:
    """輪詢等待多個商品開賣，回傳可購買的商品 ID 列表

    使用 prod/button API 偵測 ButtonType 狀態：
    ForSale=可購買, NotReady=尚未開賣, SoldOut=已售完。
    任一商品開賣即結束等待；全部售完則回傳空列表。

    成員集每輪重新讀取（監控期間可加入/退出）；成員清空視同取消。

    有指定 sale_ts（開賣時間）時分段輪詢：開賣前 FAST_POLL_WINDOW_SECS 秒
    才切到全速 interval，之前以 interval*SLOW_POLL_FACTOR 慢速輪詢。
    """
    initial_ids = membership.active_ids()
    if not initial_ids:
        raise JobCancelled()

    # 先導向任一商品頁面，確保 cookie 正確（snapup API 需要從站內呼叫）
    page.goto(
        PRODUCT_URL.format(product_id=initial_ids[0]),
        wait_until="domcontentloaded",
    )

    # 只在啟動時對時一次，之後用本機時間 + offset 推算，避免每輪多一次往返
    offset = get_server_offset(page)
    last_sync = time.time()
    last_warm = 0.0
    reporter.log(
        f"PChome 伺服器時間: {datetime.fromtimestamp(time.time() + offset):%Y/%m/%d %H:%M:%S}"
        f"（與本機差 {offset:+.2f} 秒）"
    )
    if sale_ts is not None:
        reporter.log(
            f"開賣時間: {datetime.fromtimestamp(sale_ts):%Y/%m/%d %H:%M:%S}"
            f"，前 {FAST_POLL_WINDOW_SECS} 秒起全速輪詢"
        )
    reporter.log(f"監控 {len(initial_ids)} 個商品...")

    reported_sold_out: set[str] = set()
    last_card_status: dict[str, str] = {}

    while True:
        check_cancel(cancel)

        # 成員集每輪重新讀取：監控中加入的商品自動納入批次查詢
        product_ids = membership.active_ids()
        if not product_ids:
            raise JobCancelled()

        ids_param = ",".join(product_ids)
        button_url = f"{PROD_BUTTON_API}&id={ids_param}&_callback={{CB}}"

        # 用 button API 併行查詢所有商品的 ButtonType 狀態（JSONP 端點）
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
                reporter.log(f"[{now_ms()}] 已售完: {pid}")

        # 卡片狀態只在變化時通知，避免灌爆事件流
        for pid in product_ids:
            btype = status_map.get(pid, {}).get("ButtonType")
            card = _BUTTON_TO_CARD.get(btype, "monitoring")
            if last_card_status.get(pid) != card:
                last_card_status[pid] = card
                qty = status_map.get(pid, {}).get("Qty", "")
                reporter.product_status(pid, card, f"剩 {qty} 件" if qty != "" else "")

        if ready:
            qty_info = ", ".join(
                f"{pid}(剩 {status_map[pid].get('Qty', '?')} 件)" for pid in ready
            )
            reporter.log(f"[{now_ms()}] {len(ready)} 個商品可購買: {qty_info}")
            return ready

        if len(sold_out) == len(product_ids):
            reporter.log(f"[{now_ms()}] 所有商品皆已售完，結束監控")
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
        reporter.progress(f"尚未開賣 | 伺服器時間: {server_now:%H:%M:%S} | {statuses}")
        # 間隔隨機化 ±50%，避免固定頻率的輪詢特徵
        cancellable_sleep(random.uniform(cur_interval * 0.5, cur_interval * 1.5), cancel)
