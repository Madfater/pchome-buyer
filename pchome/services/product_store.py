"""商品卡片清單的持久化（products.json）"""

import json
import threading
from pathlib import Path


class ProductStore:
    """執行緒安全的商品清單：[{id, sale_time, meta}]，sale_time 空字串表示立即監控

    meta 是選填的商品展示資訊（名稱/圖片/價格/規格旗標，見 core/product_info.py
    的 fetch_product_meta()），純資訊用途，缺欄位或缺 key 不影響任何購買邏輯。
    """

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        self._items: list[dict] = json.loads(path.read_text()) if path.exists() else []

    def list(self) -> list[dict]:
        with self._lock:
            return [dict(item) for item in self._items]

    def add(self, pid: str, sale_time: str = "", meta: dict | None = None) -> None:
        """新增商品；重複的 id 以新的 sale_time/meta 覆寫"""
        with self._lock:
            self._items = [i for i in self._items if i["id"] != pid]
            self._items.append({"id": pid, "sale_time": sale_time, "meta": meta or {}})
            self._save()

    def update_sale_time(self, pid: str, sale_time: str) -> bool:
        """更新既有商品的開賣時間（保留清單順序）；不存在回傳 False"""
        with self._lock:
            for item in self._items:
                if item["id"] == pid:
                    item["sale_time"] = sale_time
                    self._save()
                    return True
            return False

    def remove(self, pid: str) -> None:
        with self._lock:
            self._items = [i for i in self._items if i["id"] != pid]
            self._save()

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._items, ensure_ascii=False, indent=2))
