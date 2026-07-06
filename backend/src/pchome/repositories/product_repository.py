"""商品卡片清單的持久化（MongoDB `products` collection，一商品一文件，`_id` = 商品編號）

順序不是靠 Mongo 的自然回傳順序（不保證穩定），而是靠明確的 `_order` 欄位：
每次 add() 都寫入一個新產生的 ObjectId，pymongo 在同一個 process 內產生的 ObjectId
保證嚴格遞增，藉此重現舊版「重複 id 覆寫後移到清單最後」的語意，
且 update_sale_time() 不動 _order，維持原位。

meta 是選填的商品展示資訊（名稱/圖片/價格/規格旗標，見 core/product_info.py
的 fetch_product_meta()），純資訊用途，缺欄位或缺 key 不影響任何購買邏輯。
"""

import json

from bson import ObjectId
from pymongo import ASCENDING
from pymongo.database import Database

from ..core.config import LEGACY_PRODUCTS_FILE
from ..infra.mongo import get_db


class ProductRepository:
    def __init__(self, db: Database | None = None):
        self._col = (db if db is not None else get_db())["products"]
        if self._col.count_documents({}, limit=1) == 0:
            self._migrate_from_legacy_file()

    def list(self) -> list[dict]:
        result = []
        for doc in self._col.find().sort("_order", ASCENDING):
            doc.pop("_order", None)
            pid = doc.pop("_id")
            result.append({"id": pid, **doc})
        return result

    def add(self, pid: str, sale_time: str = "", meta: dict | None = None) -> None:
        """新增商品；重複的 id 以新的 sale_time/meta 覆寫，並移到清單最後（新 _order）"""
        self._col.replace_one(
            {"_id": pid},
            {
                "_id": pid,
                "sale_time": sale_time,
                "meta": meta or {},
                "_order": ObjectId(),
            },
            upsert=True,
        )

    def update_sale_time(self, pid: str, sale_time: str) -> bool:
        """更新既有商品的開賣時間（保留清單順序）；不存在回傳 False"""
        result = self._col.update_one({"_id": pid}, {"$set": {"sale_time": sale_time}})
        return result.matched_count > 0

    def remove(self, pid: str) -> None:
        self._col.delete_one({"_id": pid})

    def _migrate_from_legacy_file(self) -> None:
        """collection 第一次建構時若整個空，且舊版 products.json 存在，一次性搬入並保留原順序"""
        try:
            items = json.loads(LEGACY_PRODUCTS_FILE.read_text())
        except Exception:
            return
        docs = []
        for item in items:
            doc = dict(item)
            doc["_id"] = doc.pop("id")
            doc["_order"] = ObjectId()  # 依原清單順序逐一產生，保證遞增
            docs.append(doc)
        if docs:
            self._col.insert_many(docs)
