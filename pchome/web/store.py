"""商品卡片清單的持久化（products.json）"""

import json
import threading
from pathlib import Path


class ProductStore:
    """執行緒安全的商品清單：[{id, sale_time}]，sale_time 空字串表示立即監控"""

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        self._items: list[dict] = (
            json.loads(path.read_text()) if path.exists() else []
        )

    def list(self) -> list[dict]:
        with self._lock:
            return [dict(item) for item in self._items]

    def add(self, pid: str, sale_time: str = "") -> None:
        """新增商品；重複的 id 以新的 sale_time 覆寫"""
        with self._lock:
            self._items = [i for i in self._items if i["id"] != pid]
            self._items.append({"id": pid, "sale_time": sale_time})
            self._save()

    def remove(self, pid: str) -> None:
        with self._lock:
            self._items = [i for i in self._items if i["id"] != pid]
            self._save()

    def _save(self) -> None:
        self._path.write_text(
            json.dumps(self._items, ensure_ascii=False, indent=2)
        )
