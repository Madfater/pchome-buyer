"""結帳紀錄的持久化（checkouts.json）"""

# class 內的 list 方法會遮蔽內建 list，型別註記需延遲求值
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path


class CheckoutRecordStore:
    """執行緒安全的結帳紀錄清單，新紀錄插在最前面"""

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        self._records: list[dict] = (
            json.loads(path.read_text()) if path.exists() else []
        )

    def list(self) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._records]

    def add(
        self,
        *,
        gid: str,
        sale_time: str,
        status: str,
        cart_results: list[dict],
        payinfo: dict | None,
        log_tail: list[str],
    ) -> dict:
        record = {
            "id": uuid.uuid4().hex,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "gid": gid,
            "sale_time": sale_time,
            "status": status,
            "completed": False,
            "cart_results": cart_results,
            "payinfo": payinfo,
            "log_tail": log_tail,
        }
        with self._lock:
            self._records.insert(0, record)
            self._save()
        return dict(record)

    def update(self, record_id: str, **fields) -> dict | None:
        """更新紀錄欄位，回傳更新後的紀錄；找不到回傳 None"""
        with self._lock:
            for r in self._records:
                if r["id"] == record_id:
                    r.update(fields)
                    self._save()
                    return dict(r)
        return None

    def clear_completed(self) -> int:
        with self._lock:
            before = len(self._records)
            self._records = [r for r in self._records if not r.get("completed")]
            self._save()
            return before - len(self._records)

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._records, ensure_ascii=False, indent=2))
