"""商品資訊查詢：解析商品實際所屬店碼（cart modify 的 RS 欄位）

商品 ID 的前綴不一定是實際店碼（如 DBAJ8S-A900AJDA7 實際屬於 DBAJ8U）。
cart modify 送錯 RS 時 API 仍回報成功（PRODADD=1、件數金額都會累計），
但商品會在購物車頁載入驗證時被 PChome 靜默移除，導致「回報成功卻掉單」。
因此加車前必須以商品 API 查出真實店碼；查詢結果以行程期間的記憶體快取保存，
搶購當下（成員已凍結、MAC 效期 15 秒）通常是快取命中，不增加延遲。
"""

import json
import threading
import urllib.request

from .config import PROD_INFO_API
from .reporter import Reporter

_REQUEST_TIMEOUT_SECS = 5

_cache: dict[str, str] = {}
_lock = threading.Lock()


def _fallback(pid: str) -> str:
    """查詢失敗時退回原本的推導方式：ID 前綴"""
    return pid.split("-")[0]


def _fetch_stores(product_ids: list[str]) -> dict[str, str]:
    """批次呼叫商品 API，回傳 pid → 店碼（僅含查詢成功者）"""
    ids = ",".join(f"{pid}-000" for pid in product_ids)
    req = urllib.request.Request(
        PROD_INFO_API.format(ids=ids),
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://24h.pchome.com.tw/"},
    )
    with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT_SECS) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, dict):  # 查無商品時 API 回傳 list
        return {}
    stores: dict[str, str] = {}
    for pid in product_ids:
        store = (data.get(f"{pid}-000") or {}).get("Store")
        if store:
            stores[pid] = store
    return stores


def resolve_store_codes(
    product_ids: list[str], reporter: Reporter | None = None
) -> dict[str, str]:
    """回傳每個商品的實際店碼；查詢失敗的商品退回 ID 前綴並記 log

    結果會被快取，可在監控開始前預先呼叫以暖快取。
    """
    with _lock:
        missing = [pid for pid in product_ids if pid not in _cache]
        if missing:
            try:
                fetched = _fetch_stores(missing)
            except Exception as e:
                fetched = {}
                if reporter:
                    reporter.log(f"店碼查詢失敗（{e}），改用商品 ID 前綴，商品可能無法結帳")
            for pid, store in fetched.items():
                if store != _fallback(pid) and reporter:
                    reporter.log(f"{pid} 實際店碼為 {store}（與 ID 前綴 {_fallback(pid)} 不同）")
                _cache[pid] = store
        # 查詢失敗者不寫入快取（下次呼叫會重試），本次以 ID 前綴退回
        return {pid: _cache.get(pid, _fallback(pid)) for pid in product_ids}
