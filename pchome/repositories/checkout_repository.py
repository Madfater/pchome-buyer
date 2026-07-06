"""結帳紀錄的持久化（MongoDB `checkouts` collection，一筆結帳一文件，`_id` = 紀錄 id）

排序同樣靠明確的 `_order` 欄位（ObjectId，process 內保證遞增），由新到舊排序，
不依賴 Mongo 自然順序或 created_at 字串（同一秒內新增多筆時字串排序不足以分出先後）。
"""

# class 內的 list 方法會遮蔽內建 list，型別註記需延遲求值
from __future__ import annotations

import json
import uuid
from datetime import datetime

from bson import ObjectId
from pymongo import DESCENDING, ReturnDocument
from pymongo.database import Database

from ..core.config import LEGACY_CHECKOUTS_FILE
from ..infra.mongo import get_db


class CheckoutRecordRepository:
    def __init__(self, db: Database | None = None):
        self._col = (db if db is not None else get_db())["checkouts"]
        if self._col.count_documents({}, limit=1) == 0:
            self._migrate_from_legacy_file()

    def list(self) -> list[dict]:
        result = []
        for doc in self._col.find().sort("_order", DESCENDING):
            doc.pop("_id", None)
            doc.pop("_order", None)
            result.append(doc)
        return result

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
        self._col.insert_one({"_id": record["id"], "_order": ObjectId(), **record})
        return dict(record)

    def update(self, record_id: str, **fields) -> dict | None:
        """更新紀錄欄位，回傳更新後的紀錄；找不到回傳 None"""
        doc = self._col.find_one_and_update(
            {"_id": record_id},
            {"$set": fields},
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            return None
        doc.pop("_id", None)
        doc.pop("_order", None)
        return doc

    def clear_completed(self) -> int:
        result = self._col.delete_many({"completed": True})
        return result.deleted_count

    def _migrate_from_legacy_file(self) -> None:
        try:
            records = json.loads(LEGACY_CHECKOUTS_FILE.read_text())
        except Exception:
            return
        docs = []
        # 舊檔新到舊排列；反轉後逐一產生遞增 ObjectId，_order DESCENDING 排序後仍是新到舊
        for record in reversed(records):
            docs.append({"_id": record["id"], "_order": ObjectId(), **record})
        if docs:
            self._col.insert_many(docs)
