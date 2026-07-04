"""加入購物車：snapup 取 MAC → cart modify，多商品並行，失敗重試"""

import threading
from dataclasses import dataclass, field

from .cancel import cancellable_sleep
from .config import CART_MODIFY_API, SNAPUP_API
from .jsapi import ADD_TO_CART_JS
from .product_info import resolve_store_codes
from .reporter import Reporter
from .timing import now_ms

MAX_RETRIES = 3
RETRY_DELAY_SECS = 0.3


@dataclass
class CartItemResult:
    """單一商品加車的結構化結果（保留最後一次嘗試），供結帳紀錄使用"""

    pid: str
    ok: bool
    sold_out: bool = False
    stage: str = ""  # snapup / modify / error
    prodcount: int | None = None  # 加車後購物車總件數
    prodtotal: int | None = None  # 加車後購物車總金額
    raw_resp: dict = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "ok": self.ok,
            "sold_out": self.sold_out,
            "stage": self.stage,
            "prodcount": self.prodcount,
            "prodtotal": self.prodtotal,
            "raw": self.raw_resp,
            "error": self.error,
        }


def add_to_cart_batch(
    page, product_ids: list[str], stores: dict[str, str]
) -> list[dict]:
    """透過 snapup + cart modify API 將多個商品並行加入購物車

    stores: pid → 實際店碼（RS）。店碼與 ID 前綴可能不同，送錯 RS 時
    modify API 仍回成功，但商品會在購物車頁被靜默移除（見 product_info）。
    回傳每個商品的結果 dict：{pid, ok, soldOut, stage, resp/error}
    """
    items = []
    for pid in product_ids:
        items.append({
            "pid": pid,
            "snapupUrl": SNAPUP_API.format(product_id=pid),
            "cart": {
                "G": [], "A": [], "B": [], "C": [],
                "TB": "24H",
                "TP": 2,
                "T": "ADD",
                "TI": f"{pid}-000",
                "RS": stores[pid],
                "YTQ": 1,
            },
        })
    return page.evaluate(ADD_TO_CART_JS, {"items": items, "modifyApi": CART_MODIFY_API})


def _to_result(res: dict) -> CartItemResult:
    raw = res.get("resp")
    resp: dict = raw if isinstance(raw, dict) else {}
    return CartItemResult(
        pid=res["pid"],
        ok=bool(res.get("ok")),
        sold_out=bool(res.get("soldOut")),
        stage=res.get("stage", ""),
        prodcount=resp.get("PRODCOUNT"),
        prodtotal=resp.get("PRODTOTAL"),
        raw_resp=resp,
        error=str(res.get("error") or ""),
    )


def add_with_retry(
    page,
    product_ids: list[str],
    reporter: Reporter,
    cancel: threading.Event | None = None,
) -> tuple[list[str], list[str], list[CartItemResult]]:
    """並行加入購物車並重試失敗商品（售完不重試）

    回傳 (成功清單, 失敗清單, 每商品最後一次嘗試的結構化結果)
    """
    success_ids: list[str] = []
    pending = list(product_ids)
    last_results: dict[str, CartItemResult] = {}
    # 監控階段已暖快取時為即時；此處是最後保險（動態加入的成員）
    stores = resolve_store_codes(product_ids, reporter)

    for attempt in range(1, MAX_RETRIES + 1):
        results = add_to_cart_batch(page, pending, stores)
        pending = []
        prev_count = None
        for res in results:
            pid = res["pid"]
            last_results[pid] = _to_result(res)
            if res.get("ok"):
                resp = res["resp"]
                reporter.log(
                    f"[{now_ms()}] {pid} 已加入購物車！"
                    f"購物車共 {resp.get('PRODCOUNT')} 件，金額 ${resp.get('PRODTOTAL')}"
                )
                # modify 已序列執行，件數應嚴格遞增；否則表示商品互相覆蓋
                count = resp.get("PRODCOUNT")
                if (
                    prev_count is not None and count is not None
                    and count <= prev_count
                ):
                    reporter.log(
                        f"警告: {pid} 加車後件數未增加（{prev_count} → {count}），"
                        "先前商品可能已被覆蓋，結帳前請確認購物車內容"
                    )
                prev_count = count if count is not None else prev_count
                reporter.product_status(pid, "carted")
                success_ids.append(pid)
            elif res.get("soldOut"):
                reporter.log(f"[{now_ms()}] {pid} 已售完！")
                reporter.product_status(pid, "soldout")
            elif res.get("stage") == "snapup":
                reporter.log(
                    f"[{now_ms()}] {pid} snapup 失敗: {res.get('resp')}"
                    "（若持續失敗，session 可能已過期，請重新執行 login）"
                )
                pending.append(pid)
            else:
                reporter.log(
                    f"[{now_ms()}] {pid} 加入購物車失敗: "
                    f"{res.get('resp') or res.get('error')}"
                )
                pending.append(pid)
        if not pending:
            break
        if attempt < MAX_RETRIES:
            reporter.log(f"重試加入購物車 ({attempt}/{MAX_RETRIES}): {', '.join(pending)}")
            cancellable_sleep(RETRY_DELAY_SECS, cancel)

    for pid in pending:
        reporter.log(f"商品 {pid} 加入購物車失敗")
        reporter.product_status(pid, "failed")

    ordered = [last_results[pid] for pid in product_ids if pid in last_results]
    return success_ids, pending, ordered
