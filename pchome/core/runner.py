"""完整搶購流程的協調者：等待啟動 → 開瀏覽器 → 檢查 session → 監控 → 加車 → 結帳

CLI 與網頁控制台共用此模組；差異只在注入的 Reporter、cancel 事件與 hold 行為。
"""

# threading.Lock 是工廠函式而非類別，型別註記需延遲求值
from __future__ import annotations

import threading
import time
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from playwright.sync_api import sync_playwright

from . import session
from .cancel import JobCancelled, cancellable_sleep
from .cart import CartItemResult, add_with_retry
from .checkout import CheckoutInfo, go_to_checkout
from .config import AUTH_STATE_FILE, DEFAULT_INTERVAL_SECS, DEFAULT_LEAD_SECS, PRODUCT_URL
from .membership import GroupMembership
from .monitor import wait_for_sale
from .product_info import resolve_store_codes
from .reporter import Reporter


@dataclass
class JobConfig:
    product_ids: list[str]
    sale_ts: float | None = None
    interval: float = DEFAULT_INTERVAL_SECS
    lead: float = DEFAULT_LEAD_SECS
    headless: bool = True


@dataclass
class JobResult:
    # success / sold_out / cart_failed / session_expired / not_logged_in / cancelled
    status: str
    success_ids: list[str] = field(default_factory=list)
    cart_results: list[CartItemResult] = field(default_factory=list)
    checkout: CheckoutInfo | None = None

    @property
    def ok(self) -> bool:
        return self.status == "success"


def run_snapup_job(
    cfg: JobConfig,
    reporter: Reporter,
    *,
    membership: GroupMembership | None = None,
    checkout_lock: threading.Lock | None = None,
    cancel: threading.Event | None = None,
    hold: Callable[[JobResult], None] | None = None,
) -> JobResult:
    """執行一次完整搶購流程

    membership: run-group 的可變成員集；未提供時（CLI）以 cfg.product_ids 建立靜態成員。
    checkout_lock: 多 job 並行時序列化「加車→結帳」階段（帳號購物車是全域的）。
    cancel: 設定後流程在下一個等待點中止。
    hold: 結帳頁就緒後以暫定結果呼叫（阻塞期間瀏覽器保持開啟），
          CLI 阻塞在 input()、網頁端阻塞在 Event.wait() 並先寫入結帳紀錄。
    """
    if membership is None:
        membership = GroupMembership(cfg.product_ids)

    if not session.has_auth_state():
        reporter.log("錯誤: 尚未登入！請先執行 login 或在控制台匯入 cookie")
        return JobResult("not_logged_in")

    _log_header(cfg, reporter)

    try:
        reporter.phase("lead_wait")
        _wait_until_lead(cfg, reporter, cancel)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=cfg.headless)
            try:
                context = browser.new_context(storage_state=AUTH_STATE_FILE)
                page = context.new_page()

                # 開跑前先確認 session 有效，避免等到開賣才發現要重新登入
                reporter.phase("checking_session")
                reporter.log("檢查登入狀態...")
                if not session.check_session(page):
                    reporter.log("錯誤: 登入 session 已過期！請重新登入")
                    return JobResult("session_expired")
                reporter.log("登入狀態有效")

                # 預先查出實際店碼（RS）並暖快取，開賣瞬間加車不必再等查詢
                resolve_store_codes(membership.active_ids(), reporter)

                reporter.phase("monitoring")
                reporter.log("開始監控商品狀態...")
                ready_ids = wait_for_sale(
                    page, membership, cfg.interval, cfg.sale_ts, reporter, cancel
                )
                if not ready_ids:
                    return JobResult("sold_out")

                with checkout_lock or nullcontext():
                    # 凍結成員集：加車開始後退出的成員不再影響本組
                    reporter.phase("carting")
                    final_ids = [pid for pid in ready_ids if pid in membership.freeze()]
                    if not final_ids:
                        raise JobCancelled()

                    success_ids, _failed, cart_results = add_with_retry(
                        page, final_ids, reporter, cancel
                    )
                    if not success_ids:
                        reporter.log("所有商品加入購物車失敗！")
                        return JobResult("cart_failed", cart_results=cart_results)

                    reporter.log(f"成功加入 {len(success_ids)}/{len(final_ids)} 個商品")
                    reporter.phase("checkout")
                    checkout_info = go_to_checkout(page, reporter)

                result = JobResult(
                    "success", success_ids,
                    cart_results=cart_results, checkout=checkout_info,
                )
                if hold:
                    reporter.phase("holding")
                    hold(result)
                return result
            finally:
                browser.close()
    except JobCancelled:
        reporter.log("任務已取消")
        return JobResult("cancelled")


def _log_header(cfg: JobConfig, reporter: Reporter) -> None:
    reporter.log(f"目標商品 ({len(cfg.product_ids)} 個):")
    for pid in cfg.product_ids:
        reporter.log(f"  - {pid}  {PRODUCT_URL.format(product_id=pid)}")
    reporter.log(f"輪詢間隔: {cfg.interval} 秒")
    reporter.log(f"無頭模式: {'是' if cfg.headless else '否'}")
    reporter.log("-" * 50)


def _wait_until_lead(
    cfg: JobConfig, reporter: Reporter, cancel: threading.Event | None
) -> None:
    """距開賣超過 lead 秒時先睡眠，到開賣前 lead 秒才開始監控（原 schedule.sh 的職責）"""
    if cfg.sale_ts is None:
        return
    start_ts = cfg.sale_ts - cfg.lead
    if start_ts - time.time() <= 0:
        return

    reporter.log(
        f"開賣時間: {datetime.fromtimestamp(cfg.sale_ts):%Y-%m-%d %H:%M:%S}，"
        f"{datetime.fromtimestamp(start_ts):%H:%M:%S} 啟動監控（提前 {cfg.lead:.0f} 秒）"
    )
    while True:
        remaining = start_ts - time.time()
        if remaining <= 0:
            break
        reporter.progress(f"等待啟動中，剩 {int(remaining)} 秒")
        cancellable_sleep(min(remaining, 1.0), cancel)
    reporter.log("到達啟動時間，開始執行搶購流程")
